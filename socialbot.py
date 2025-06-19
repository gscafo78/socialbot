#!/usr/bin/env python3
"""
socialbot.py

Main runner for SocialBot. This script periodically fetches RSS feeds,
generates AI-powered comments, and dispatches new items to Telegram,
BlueSky, and LinkedIn while respecting configured quiet/mute windows
and scheduling future runs via a cron expression.

How to use:
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
from datetime import datetime, timedelta
from croniter import croniter

# JSONReader for reading configuration
from utils.readjson import JSONReader
# MuteTimeChecker to enforce quiet periods
from utils.utils import MuteTimeChecker
# RSSFeeders to fetch and parse RSS feeds
from rssfeeders.rssfeeders import RSSFeeders
# Model helper for querying GPT models
from gpt.get_ai_model import Model
# SocialSender for sending to social platforms
from senders.senders import SocialSender
# DatabaseManager for persistence and configuration storage
from utils.dbmanager import DatabaseManager

__version__ = "1.0.0"

# ------------------------------------------------------------------------------
# Module‑level logging configuration
# ------------------------------------------------------------------------------
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def main():
    """
    Main entry point for SocialBot.

    Steps performed by this script:
      1. Parse command-line arguments and load configuration.
      2. Configure logging and scheduling (cron).
      3. Load RSS feeds and previously seen items from the database.
      4. Identify new feed items and (optionally) generate AI comments.
      5. Dispatch new items to Telegram, BlueSky, and LinkedIn.
      6. Respect configured mute/quiet time windows.
      7. Sleep until the next scheduled execution and repeat.

    Command-line arguments:
      --version              Show program version and exit.
      -c, --config           Path to configuration file (default: ./settings.json).
      --debug                Enable DEBUG-level logging (default: INFO).

    Configuration file structure (settings.json):
      settings:
        host                 Database host (default: 127.0.0.1)
        port                 Database port (default: 3306)
        user                 Database user name
        password             Database password
        database             Database name
        secret-key           Encryption key for sensitive data
        days_of_news         How many days back to fetch news
        days_of_retention    How many days of logs/news to retain
        cron                 Cron expression for scheduling runs (e.g. "0 * * * *")
        mute:
          from               Mute window start time (HH:MM)
          to                 Mute window end time (HH:MM)
        log_level            Override log level for the runner
        bots:
          telegram           Enable Telegram posting (true/false)
          linkedin           Enable LinkedIn posting (true/false)
          bluesky            Enable BlueSky posting (true/false)
      ai:
        ai_comment_max_chars Max characters for AI-generated comments
        ai_comment_language  Language code for AI comments ("en", "it", ...)
        ai_base_url          Base URL for the AI API
        ai_model             GPT model to use (or "auto" for automatic selection)
        ai_key               OpenAI API key
    """
    # --------------------------------------------------------------------------
    # 1) Parse command-line arguments
    # --------------------------------------------------------------------------
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

    # --------------------------------------------------------------------------
    # 2) Configure root logger
    # --------------------------------------------------------------------------
    logging.basicConfig(format=LOG_FORMAT)
    logger = logging.getLogger(__name__)
    # Start with DEBUG if requested, otherwise INFO
    logger.setLevel(logging.DEBUG if args.debug else logging.INFO)

    # --------------------------------------------------------------------------
    # 3) Load initial config to check for an override of log_level
    # --------------------------------------------------------------------------
    reader_tmp = JSONReader(args.config_path, logger=logger)
    if not args.debug:
        cfg_level = reader_tmp.get_value("settings", {}).get("log_level", "INFO").upper()
        logger.setLevel(getattr(logging, cfg_level, logging.INFO))

    # Recreate JSONReader now that the log level is finalized
    reader = JSONReader(args.config_path, logger=logger)

    # --------------------------------------------------------------------------
    # 4) Read core settings from configuration
    # --------------------------------------------------------------------------
    host = reader.get_value("settings", {}).get("host", "127.0.0.1")
    port = reader.get_value("settings", {}).get("port", 3306)
    user = reader.get_value("settings", {}).get("user", "username")
    pwd = reader.get_value("settings", {}).get("password", "")
    database = reader.get_value("settings", {}).get("database", "db")
    secret_key = reader.get_value("settings", {}).get("secret-key", "")
    if not secret_key:
        logger.warning("No secret key provided in config – using empty string.")

    days_of_news = reader.get_value("settings", {}).get("days_of_news", None)
    retention_days = reader.get_value("settings", {}).get("days_of_retention", None)
    cron_expr = reader.get_value("settings", {}).get("cron", "0 * * * *")

    # Mute/quiet window settings
    mute_from = reader.get_value("settings", {}).get("mute", {}).get("from", "00:00")
    mute_to = reader.get_value("settings", {}).get("mute", {}).get("to", "00:00")
    mute_checker = MuteTimeChecker(mute_from, mute_to, logger=logger)

    # Which bots are enabled?
    bots = reader.get_value("settings", {}).get("bots", {})
    enabled_bots = []
    if bots.get("telegram"):
        enabled_bots.append("Telegram")
    if bots.get("linkedin"):
        enabled_bots.append("Linkedin")
    if bots.get("bluesky"):
        enabled_bots.append("BlueSky")

    # --------------------------------------------------------------------------
    # 5) Initialize and connect to the database
    # --------------------------------------------------------------------------
    db = DatabaseManager(
        host=host,
        port=port,
        user=user,
        password=pwd,
        database=database,
        secret_key=secret_key,
        logger=logger
    )
    db.connect()

    # --------------------------------------------------------------------------
    # 6) Retrieve AI configuration from the database (cleartext)
    # --------------------------------------------------------------------------
    ai_config = db.export_ai_config_cleartext()
    logger.info(f"AI config: {ai_config}")
    ai_max_chars = ai_config[0]["ai_comment_max_chars"]
    ai_lang = ai_config[0]["ai_comment_language"]
    ai_base_url = ai_config[0]["ai_base_url"]
    gpt_model = ai_config[0]["ai_model"]

    # --------------------------------------------------------------------------
    # 7) Auto‑select the cheapest GPT model if 'auto' was specified
    # --------------------------------------------------------------------------
    if gpt_model == "auto":
        logger.info("AI model set to 'auto', selecting cheapest GPT model …")
        raw = Model.fetch_raw_models(logger)
        models = Model.process_models(raw, logger)
        cheapest_model = Model.find_cheapest_model(models, logger, filter_str="openai")
        gpt_model = cheapest_model.id
        gpt_in_price = cheapest_model.prompt_price
        gpt_out_price = cheapest_model.completion_price
    else:
        # If not auto, we won't show pricing details
        gpt_in_price = 0
        gpt_out_price = 0

    # --------------------------------------------------------------------------
    # 8) Startup logging summary
    # --------------------------------------------------------------------------
    logger.info("Starting SocialBot – version %s", __version__)
    logger.debug("Config file path: %s", args.config_path)
    logger.info("Cron schedule for updates: %s", cron_expr)
    logger.info(
        "Mute window from %s to %s → is_mute_time=%s",
        mute_from, mute_to, mute_checker.is_mute_time()
    )
    logger.info("Bots enabled: %s", " / ".join(enabled_bots))
    logger.info("Retention days of news: %s", days_of_news)
    logger.info("Retention days of logs: %s", retention_days)
    logger.info("AI Base Url: %s", ai_base_url)
    logger.info(
        "AI model: %s - $%.2f/M input tokens | $%.2f/M output tokens",
        gpt_model,
        round(gpt_in_price * 1_000_000, 2),
        round(gpt_out_price * 1_000_000, 2)
    )
    logger.info("AI comment max chars: %s", ai_max_chars)
    logger.info("AI comment language: %s", ai_lang)

    # --------------------------------------------------------------------------
    # 9) Main fetch → process → post → sleep loop
    # --------------------------------------------------------------------------
    try:
        sleep_time = 40.0  # initial dummy value

        async def _worker_loop():
            nonlocal sleep_time
            while True:
                # a) Purge old execution logs
                retdays = (
                    datetime.now() - timedelta(days=retention_days)
                ).replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
                db.delete_old_execution_logs(retdays)
                logger.debug("News removed until %s", retdays)

                # b) Compute cutoff for new news
                retnews = (
                    datetime.now() - timedelta(days=days_of_news)
                ).replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
                logger.debug("Load news from %s", retnews)

                # c) Check if we're in a mute window
                mute_flag = mute_checker.is_mute_time()

                # d) Fetch new RSS items
                rss = RSSFeeders(
                    db,
                    logger=logger,
                    mutetime=mute_flag,
                    retention_days=0
                )
                new_items = rss.get_latest_rss()

                # e) Process each item and send to enabled bots concurrently
                async def _process_item(item):
                    sender = SocialSender(db.export_accounts_cleartext(), logger)
                    coros = []
                    if bots.get("telegram"):
                        coros.append(sender.send_to_telegram(item, mute_flag))
                    if bots.get("linkedin"):
                        coros.append(sender.send_to_linkedin(item, mute_flag, sleep_time=sleep_time))
                    if bots.get("bluesky"):
                        coros.append(sender.send_to_bluesky(item, mute_flag))
                    await asyncio.gather(*coros)

                tasks = [asyncio.create_task(_process_item(it)) for it in new_items]
                await asyncio.gather(*tasks)

                # f) Log what got inserted vs. skipped
                inserted, skipped = db.insert_execution_log_from_json(new_items)
                logger.debug("Execution logs inserted: %s, skipped: %s.", inserted, skipped)

                # g) Calculate next run time via cron expression
                cron_iter = croniter(cron_expr, datetime.now())
                next_run = cron_iter.get_next(datetime)
                sleep_time = (next_run - datetime.now()).total_seconds()
                if sleep_time < 0:
                    logger.warning("Negative sleep_time (%.1f); resetting to zero", sleep_time)
                    sleep_time = 0.0

                logger.info("Sleeping %d minutes until the next cycle…", int(sleep_time / 60))
                await asyncio.sleep(sleep_time)

        # Start the asynchronous worker loop
        asyncio.run(_worker_loop())

    except KeyboardInterrupt:
        # Graceful shutdown on Ctrl+C
        logger.info("KeyboardInterrupt received – shutting down SocialBot.")
    except Exception as exc:
        # Catch-all for fatal errors
        logger.exception("Fatal error: %s", exc)
    finally:
        # Ensure the DB connection is closed on exit
        db.close()
        logger.info("SocialBot stopped. Database connection closed.")


if __name__ == "__main__":
    main()