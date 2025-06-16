#!/usr/bin/env python3
"""
socialbot.py
Main runner for SocialBot:
  - Periodically fetch RSS feeds  
  - Generate AI comments   
  - Dispatch new items to Telegram, Bluesky, and LinkedIn  
  - Respect quiet/mute time windows  
  - Schedule next run according to a cron expression  
Usage:
    # Show version and exit
    python socialbot.py --version
    # Run with default INFO‑level logging
    python socialbot.py --config ./settings.json
    # Run with DEBUG‑level logging
    python socialbot.py --config ./settings.json --debug
"""

import argparse
import logging
import asyncio
from datetime import datetime

from croniter import croniter

from utils.readjson import JSONReader
from utils.utils import MuteTimeChecker
from rssfeeders.rssfeeders import RSSFeeders
from gpt.get_ai_model import Model
from senders.senders import SocialSender

__version__ = "0.0.24"

# ------------------------------------------------------------------------------
# Module‐level logging configuration
# ------------------------------------------------------------------------------
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def main():
    """
    Main entry point for SocialBot.
      1. Parse command-line arguments and load configuration.
      2. Configure logging and scheduling (cron).
      3. Load RSS feeds and previously seen items.
      4. Identify new feed items and (optionally) generate AI comments.
      5. Dispatch new items to Telegram, Bluesky, and LinkedIn.
      6. Respect mute/quiet time windows.
      7. Sleep until the next scheduled execution.

    Command-line arguments:
      --version              Show program version and exit.
      -c, --config           Path to configuration file (default: ./settings.json).
      --debug                Enable DEBUG-level logging (default: INFO).

    Config file options (settings.json):
      settings:
        feeds_file           Path to RSS feeds file (default: ./feeds.json).
        log_file             Path to history/log file.
        cron                 Cron expression for scheduling runs.
        days_of_retention    Number of days to keep old items.
        mute:
          from               Mute window start time (HH:MM).
          to                 Mute window end time (HH:MM).
        log_level            Override log level for the runner.
      ai:
        ai_comment_max_chars Max characters for AI-generated comments.
        ai_comment_language  Language code for AI comments ("en", "it", ...).
        ai_base_url          Base URL for the AI API (default: https://api.openai.com/v1).
        ai_model             GPT model to use (or "auto" for automatic selection).
        ai_key               OpenAI API key.

    Returns:
      None
    """

    # --- Parse command‐line arguments ------------------------------------------
    parser = argparse.ArgumentParser(description="SocialBot main runner")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program version and exit.",
    )
    parser.add_argument(
        "-c", "--config",
        dest="config_path",
        default="./settings.json",
        help="Path to configuration file (default: ./settings.json)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable DEBUG-level logging (default is INFO).",
    )
    args = parser.parse_args()

    # --- Configure root logger ------------------------------------------------
    logging.basicConfig(format=LOG_FORMAT)
    logger = logging.getLogger(__name__)
    # Start with INFO or DEBUG based on CLI
    logger.setLevel(logging.DEBUG if args.debug else logging.INFO)

    # --- Load initial config to see if config itself overrides log_level -------
    reader_tmp = JSONReader(args.config_path, logger=logger)
    if not args.debug:
        cfg_level = reader_tmp.get_value("settings", {}).get("log_level", "INFO").upper()
        logger.setLevel(getattr(logging, cfg_level, logging.INFO))

    # --- Recreate reader with final logger level -------------------------------
    reader = JSONReader(args.config_path, logger=logger)

    # --- Read important settings from config ----------------------------------
    feeds_path = reader.get_value(
        "settings", {}
    ).get("feeds_file", "/opt/github/03_Script/Python/socialbot/feeds.json")
    logfile = reader.get_value("settings", {}).get("log_file", "/var/log/socialbot.log")
    cron_expr = reader.get_value("settings", {}).get("cron", "0 * * * *")
    retention_days = reader.get_value("settings", {}).get("days_of_retention", None)

    ai_max_chars = reader.get_value("ai", {}).get("ai_comment_max_chars", 160)
    ai_lang = reader.get_value("ai", {}).get("ai_comment_language", "en")
    ai_base_url = reader.get_value("ai", {}).get("ai_base_url", "https://api.openai.com/v1")
    gpt_model = reader.get_value("ai", {}).get("ai_model", "gpt-4.1-nano")
    ai_key = reader.get_value("ai", {}).get("ai_key", None)

    mute_from = reader.get_value("settings", {}).get("mute", {}).get("from", "00:00")
    mute_to = reader.get_value("settings", {}).get("mute", {}).get("to", "00:00")
    mute_checker = MuteTimeChecker(mute_from, mute_to, logger=logger)

    # --- Auto‑select GPT model if requested -----------------------------------
    if gpt_model == "auto":
        logger.info("AI model set to 'auto', selecting cheapest GPT model …")
        # gpt_model = GPTModelSelector(ai_key, logger).get_cheapest_gpt_model()
        raw = Model.fetch_raw_models(logger)
        models = Model.process_models(raw, logger)
        cheapest_model = Model.find_cheapest_model(models, logger, filter_str="openai")
        gpt_model = cheapest_model.id
        gpt_in_price = cheapest_model.prompt_price
        gpt_out_price = cheapest_model.completion_price
    else:
        gpt_in_price = 0
        gpt_out_price = 0

    # --- Startup logging -------------------------------------------------------
    logger.info("Starting SocialBot – version %s", __version__)
    logger.debug("Config file path: %s", args.config_path)
    logger.info("Feeds file path: %s", feeds_path)
    logger.info("Log file (history) path: %s", logfile)
    logger.info("Cron schedule for updates: %s", cron_expr)
    logger.info(
        "Mute window from %s to %s → is_mute_time=%s",
        mute_from, mute_to, mute_checker.is_mute_time()
    )
    logger.info("Retention days: %s", retention_days)
    logger.info("AI Base Url: %s", ai_base_url)
    logger.info(
        "AI model: %s - $%.2f/M input tokens | $%.2f/M output tokens",
        gpt_model,
        round(gpt_in_price * 1_000_000, 2),
        round(gpt_out_price * 1_000_000, 2)
    )
    logger.info("AI comment max chars: %s", ai_max_chars)
    logger.info("AI comment language: %s", ai_lang)

    # --- Main fetch→post→sleep loop -------------------------------------------
    try:
        sleep_time = 40.0

        async def _worker_loop():
            nonlocal sleep_time

            while True:
                # Load history and feeds for this cycle
                history_reader = JSONReader(logfile, create=True, logger=logger)
                seen_items = history_reader.get_data() or []
                feeds_reader = JSONReader(feeds_path, logger=logger)
                all_feeds = feeds_reader.get_data() or []
                # Ensure all feed entries have the necessary keys
                for feed in all_feeds:
                    feed.setdefault("link", "")
                    feed.setdefault("datetime", "")
                    feed.setdefault("description", "")
                    feed.setdefault("title", "")
                    feed.setdefault("ai-comment", "")
                # Check if we are currently within the mute window
                mute_flag = mute_checker.is_mute_time()
                rss = RSSFeeders(
                    all_feeds,
                    seen_items,
                    retention_days=retention_days,
                    base_url=ai_base_url,
                    logger=logger,
                    mutetime=mute_flag
                )
                new_items, updated_history = rss.get_new_feeders(
                    ai_key,
                    gpt_model,
                    ai_max_chars,
                    ai_lang
                )

                if new_items:
                    logger.info("Found %d new items – launching asynchronous dispatch…", len(new_items))

                    async def _process_item(item):
                        sender = SocialSender(reader, logger)
                        # send in parallel to all configured channels
                        await asyncio.gather(
                            sender.send_to_telegram(item, mute_flag),
                            sender.send_to_bluesky(item, mute_flag),
                            sender.send_to_linkedin(item, mute_flag, sleep_time=sleep_time),
                        )

                    # create concurrent tasks for each new item
                    tasks = [asyncio.create_task(_process_item(it)) for it in new_items]
                    await asyncio.gather(*tasks)

                    # save updated history
                    history_reader.set_data(updated_history)
                    logger.debug("Updated history written to %s", logfile)
                else:
                    logger.info("No new RSS items found this cycle.")

                # compute next run time using cron schedule
                cron_iter = croniter(cron_expr, datetime.now())
                next_run = cron_iter.get_next(datetime)
                sleep_time = (next_run - datetime.now()).total_seconds()
                if sleep_time < 0:
                    logger.warning("Negative sleep_time (%.1f); resetting to zero", sleep_time)
                    sleep_time = 0.0
                logger.info("Sleeping %d minutes until the next cycle…", int(sleep_time / 60))
                await asyncio.sleep(sleep_time)

        # lancio l'event loop
        asyncio.run(_worker_loop())
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received – shutting down SocialBot.")


if __name__ == "__main__":
    main()