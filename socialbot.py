import json
import time
import random
from datetime import datetime
from croniter import croniter
from utils.readjson import JSONReader
from utils.logger import Logger
from utils.utils import MuteTimeChecker
from rssfeeders.rssfeeders import RSSFeeders
from gpt.getmodel import GPTModelSelector
from senders.senders import SocialSender
import argparse

__version__ = "0.0.15"


def main():
    """
    Main entry point for SocialBot.
    Parses arguments, loads configuration, and starts the main loop.
    """
    # --- Parse command line arguments ---
    parser = argparse.ArgumentParser(description="SocialBot main runner")
    parser.add_argument(
        "-c", "--config",
        dest="config_path",
        default="./settings.json",
        help="Path to configuration file (default: ./settings.json)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging"
    )
    args = parser.parse_args()

    # --- Configuration file path ---
    file_path = args.config_path

    # --- Logger setup ---
    log_level_str = 'DEBUG' if args.verbose else "INFO"
    temp_logger = Logger.get_logger(__name__, level=log_level_str)
    reader = JSONReader(file_path, logger=temp_logger)
    log_level_str = 'DEBUG' if args.verbose else reader.get_value('settings', {}).get('log_level', 'INFO')
    logger = Logger.get_logger(__name__, level=log_level_str)
    
    # Re-initialize reader with the correct logger if needed
    reader = JSONReader(file_path, logger=logger)
    feeds_path = reader.get_value('settings', {}).get('feeds_file', "/opt/github/03_Script/Python/socialbot/feeds.json")
    readfeeds = JSONReader(feeds_path, logger=logger)

    # --- Log file and update interval ---
    logfile = reader.get_value('settings', {}).get('log_file', '/var/log/socialbot.log')
    cron = reader.get_value('settings', {}).get('cron', '0 * * * *')  # Default: every hour
    openai_comment_max_chars = reader.get_value('openai', {}).get('openai_comment_max_chars', 160) 
    openai_comment_language = reader.get_value('openai', {}).get('openai_comment_language', 'en')
    gptmodel = reader.get_value('openai', {}).get('openai_model', 'gpt-4.1-nano')
    mutefrom = reader.get_value('settings', {}).get('mute', {}).get('from', '00:00')
    muteto = reader.get_value('settings', {}).get('mute', {}).get('to', '00:00')
    mute = MuteTimeChecker(mutefrom, muteto, logger=logger)

    # --- Select GPT model if set to auto ---
    if gptmodel == "auto":
        logger.info("OpenAI model not set. Using auto model.")
        gptmodel = GPTModelSelector(
            reader.get_value('openai')['openai_key'],
            logger
        ).get_cheapest_gpt_model()
    
    # --- Log startup information ---
    logger.info(f"Start SocialBot - Ver. {__version__}")
    logger.debug(f"File setting path: {file_path}")
    logger.info(f"Feeds file path: {feeds_path}")
    logger.info(f"Log file path: {logfile}")
    logger.info(f"Feed update interval by cron: {cron}")
    logger.info(f"Mute is {mute.is_mute_time()}, because is from: {mutefrom}, to: {muteto}")
    logger.info(f"OpenAI model: {gptmodel}")
    logger.info(f"OpenAI comment max chars: {openai_comment_max_chars}")
    logger.info(f"OpenAI comment language: {openai_comment_language}")

    try:
        sleep_time = 40
        while True:
            # --- Load previous RSS data from log file ---
            filerss = JSONReader(logfile, create=True, logger=logger)
            previousrss = filerss.get_data()
            logger.debug("Full JSON data loaded from log file.")

            # --- Load feeds from config file ---
            feeds = readfeeds.get_data()
            logger.debug(f"Value for key 'feeds': {feeds}")
            newfeeds = []
            feedstofile = []

            # --- Ensure all required keys exist in each feed ---
            for feed in feeds:
                feed.setdefault("link", "")
                feed.setdefault("datetime", "")
                feed.setdefault("description", "")
                feed.setdefault("title", "")
                feed.setdefault("ai-comment", "")

            # --- Initialize RSSFeeders with logger ---
            rss = RSSFeeders(
                feeds, 
                previousrss, 
                retention=reader.get_value('settings')['days_of_retention'], 
                logger=logger
            )

            # --- Get new feeds and update file ---
            newfeeds, feedstofile = rss.get_new_feeders(
                reader.get_value('openai')['openai_key'],
                gptmodel,
                openai_comment_max_chars,
                openai_comment_language
            )
            
            if newfeeds:
                logger.debug("New feeds found:")
                logger.debug(json.dumps(newfeeds, indent=4, ensure_ascii=False, default=str))
                # Send each new feed to all platforms
                for feed in newfeeds:
                    # --- Wait a random time between 0 and sleep_time-30 (if possible) ---
                    if sleep_time > 30:
                        random_wait = random.uniform(0, sleep_time - 30)
                        logger.debug(f"Random wait before next send messages: {int(random_wait)} seconds.")
                        time.sleep(random_wait)
                    sender = SocialSender(reader, logger)
                    sender.send_to_telegram(feed, mute.is_mute_time())
                    sender.send_to_bluesky(feed, mute.is_mute_time())
                    sender.send_to_linkedin(feed, mute.is_mute_time())
                # Save updated feeds to file
                filerss.set_data(feedstofile)
                logger.debug(f"New feeds saved to {logfile}.")
            else:
                logger.info("No new feeds found.")

            # --- Calculate next execution time based on cron schedule ---
            iter_cron = croniter(cron, datetime.now())
            next_run = iter_cron.get_next(datetime)
            sleep_time = (next_run - datetime.now()).total_seconds()

            if sleep_time < 0:
                logger.warning(f"Sleep time was negative ({sleep_time}), setting to 0.")
                sleep_time = 0

            # Log waiting time only if not in mute interval
            logger.info(f"Waiting {int(sleep_time/60)} minutes before the next execution...")

            # --- Wait until next scheduled run ---
            time.sleep(sleep_time)
    except KeyboardInterrupt:
        logger.info("Manual interruption received. Exiting program.")

"""
How to use this script:

- Run the script directly: `python socialbot.py`
- Use the `--config` option to specify a custom configuration file.
- Use the `--verbose` flag to enable debug logging.

Main loop steps:
1. Load configuration and feeds.
2. Check if current time is in mute interval (no posting).
3. Fetch new RSS items and generate AI comments.
4. Send new items to Telegram, Bluesky, and LinkedIn.
5. Wait until the next scheduled execution (based on cron).

You can extend this script by adding new sender classes or modifying the feed processing logic.
"""

if __name__ == "__main__":
    main()