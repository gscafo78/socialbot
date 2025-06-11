#!/usr/bin/env python3
"""
socialbot.py

Main runner for SocialBot:
  - Periodically fetches RSS feeds  
  - Generates AI comments   
  - Dispatches new items to Telegram, Bluesky, and LinkedIn  
  - Honors quiet/mute schedules  
  - Schedules next run based on a cron expression  

Usage:
    # Show version and exit
    python socialbot.py --version

    # Run with default INFO‑level logging
    python socialbot.py --config ./settings.json

    # Run with DEBUG‑level logging
    python socialbot.py --config ./settings.json --debug
"""

import argparse
import json
import logging
import random
import time
from datetime import datetime

from croniter import croniter

from utils.readjson import JSONReader
from utils.utils import MuteTimeChecker
from rssfeeders.rssfeeders import RSSFeeders
# from gpt.getmodel import GPTModelSelector
from gpt.get_ai_model import Model
from senders.senders import SocialSender

__version__ = "0.0.21"

# ------------------------------------------------------------------------------
# Module‐level logging configuration
# ------------------------------------------------------------------------------
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def main():
    """
    Main entry point for SocialBot.

    - Parses command-line arguments and loads configuration files.
    - Sets up logging and scheduling (cron).
    - Loads RSS feeds and previously seen items.
    - Detects new RSS items and (optionally) generates AI comments.
    - Dispatches new items to Telegram, Bluesky, and LinkedIn via SocialSender.
    - Honors mute/quiet time windows.
    - Sleeps until the next scheduled run.

    Args (from argparse and config):
        --version              Show program version and exit.
        -c, --config           Path to configuration file (default: ./settings.json).
        --debug                Enable DEBUG-level logging (default is INFO).

    Config file options (settings.json):
        feeds_file             Path to feeds file (default: ./feeds.json).
        log_file               Path to log/history file.
        cron                   Cron expression for scheduling.
        days_of_retention      How many days to keep old items.
        mute.from              Start time for mute window (HH:MM).
        mute.to                End time for mute window (HH:MM).
        ai_comment_max_chars   Max chars for AI-generated comments.
        ai_comment_language    Language for AI comments ("en", "it", ...).
        ai_base_url            Base URL for AI API (default: https://api.openai.com/v1).
        ai_model               GPT model to use (or "auto" for cheapest).
        ai_key                 OpenAI API key.

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
        # Initial dummy sleep_time (in seconds) before random backoff
        sleep_time = 40.0

        while True:
            # Load history of already‑processed items
            history_reader = JSONReader(logfile, create=True, logger=logger)
            seen_items = history_reader.get_data() or []
            logger.debug("Loaded %d historical items from %s", len(seen_items), logfile)

            # Load configured RSS feeds
            feeds_reader = JSONReader(feeds_path, logger=logger)
            all_feeds = feeds_reader.get_data() or []
            logger.debug("Configured RSS feeds: %s", all_feeds)

            # Ensure feeds have all required keys
            for feed in all_feeds:
                feed.setdefault("link", "")
                feed.setdefault("datetime", "")
                feed.setdefault("description", "")
                feed.setdefault("title", "")
                feed.setdefault("ai-comment", "")

            mute_flag = mute_checker.is_mute_time()
            # Detect new items & generate AI comments
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
                logger.debug("Found %d new items. Details:\n%s",
                             len(new_items),
                             json.dumps(new_items, indent=2, ensure_ascii=False, default=str))

                # Dispatch each new item to SocialSender
                for item in new_items:
                    # small random back‑off to avoid spamming multiple bots simultaneously
                    if sleep_time > 30:
                        rnd = random.uniform(0, sleep_time - 30)
                        logger.debug("Backing off %.1f seconds before sending next batch", rnd)
                        time.sleep(rnd)

                    sender = SocialSender(reader, logger)
                    sender.send_to_telegram(item, mute_flag)
                    sender.send_to_bluesky(item, mute_flag)
                    sender.send_to_linkedin(item, mute_flag)

                # Persist updated history
                history_reader.set_data(updated_history)
                logger.debug("Updated history written to %s", logfile)

            else:
                logger.info("No new RSS items found at this cycle.")

            # Compute next wake‑up time via croniter
            cron_iter = croniter(cron_expr, datetime.now())
            next_run = cron_iter.get_next(datetime)
            sleep_time = (next_run - datetime.now()).total_seconds()
            if sleep_time < 0:
                logger.warning("Next sleep_time was negative (%.1f), resetting to 0", sleep_time)
                sleep_time = 0.0

            logger.info("Sleeping %d minutes until next run …", int(sleep_time / 60))
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received – shutting down SocialBot.")


if __name__ == "__main__":
    main()