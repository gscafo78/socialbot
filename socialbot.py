import json
import time
from datetime import datetime, timedelta
from croniter import croniter
from utils.readjson import JSONReader
from utils.logger import Logger
from utils.utils import MuteTimeChecker
from rssfeeders.rssfeeders import RSSFeeders
from gpt.getmodel import GPTModelSelector
from senders.telegramsendmsg import TelegramBotPublisher
from senders.blueskysendmsg import BlueskyPoster
from senders.linkedinpublisher import LinkedInPublisher
import argparse

__version__ = "0.0.8"

def send_feed_to_telegram(feed, 
                          reader, 
                          logger,
                          ismute=False):
    """
    Send a single feed to all configured Telegram bots.

    Args:
        feed (dict): The feed data to send.
        reader (JSONReader): The JSONReader instance for config.
        logger (Logger): Logger instance.
    """
    bots = feed.get("telegram", {}).get("bots", [])
    for bot in bots:
        mute = False
        token, chat_id, _ , mute = reader.get_social_values("telegram", bot)
        if not mute or not ismute:
            logger.debug(f"Sending new feed to Telegram... {feed.get('title', '')}")                
            logger.debug(f"TelegramBotPublisher initialized with token {token} and chat_id {chat_id}.")
            telebot = TelegramBotPublisher(token, chat_id)
            # Use short_link if present and not empty/None, otherwise use link
            link_to_use = feed.get('short_link')
            if not link_to_use:
                link_to_use = feed.get('link', '')
            logger.debug(f"{feed.get('title', '')}\n{feed.get('description', '')}\n{link_to_use}")
            telebot.send_message(f"{feed.get('title', '')}\n{feed.get('description', '')}\n{link_to_use}")
        else:
            logger.debug(f"Skipping Telegram message for {feed.get('title', '')} due to mute setting.")

def send_feed_to_bluesky(feed, 
                         reader, 
                         logger, 
                         ismute=False):
    """
    Send a single feed to all configured Bluesky bots.

    Args:
        feed (dict): The feed data to send.
        reader (JSONReader): The JSONReader instance for config.
        logger (Logger): Logger instance.
    """
    bots = feed.get("bluesky", {}).get("bots", [])
    for bot in bots:
        mute = False
        handle, password, service, mute = reader.get_social_values("bluesky", bot)
        if not mute or not ismute:
            logger.debug(f"Sending new feed to BlueSky... {feed.get('title', '')}")                
            # Use short_link if present and not empty/None, otherwise use link
            link_to_use = feed.get('short_link')
            if not link_to_use:
                link_to_use = feed.get('link', '')
            logger.debug(f"BlueskyBotPublisher initialized with Handle {handle}, password {password} and service {service}.")
            logger.debug(f"{feed.get('title', '')}\n{feed.get('description', '')}\n{link_to_use}")
            blueskybot = BlueskyPoster(handle, password, service)
            try:
                ai_comment = feed.get('ai-comment', '')
                if ai_comment == '':
                    ai_comment = None

                response = blueskybot.post_feed(
                    description=feed.get('description', ''),
                    link=link_to_use,
                    ai_comment=ai_comment,
                    title=feed.get('title', '')
                )
                logger.debug(f"Server response: {response}")
            except Exception as e:
                logger.error(f"Error while posting: {e}")
                # Or, to log the stacktrace:
                # logger.exception("Error while posting:")
        else:
            logger.debug(f"Skipping Bluesky message for {feed.get('title', '')} due to mute setting.")

def send_feed_to_linkedin(feed, 
                         reader, 
                         logger, 
                         ismute=False):
    """
    Send a single feed to all configured Linkedin account.

    Args:
        feed (dict): The feed data to send.
        reader (JSONReader): The JSONReader instance for config.
        logger (Logger): Logger instance.
    """
    bots = feed.get("linkedin", {}).get("bots", [])
    for bot in bots:
        mute = False
        urn, access_token, _, mute = reader.get_social_values("linkedin", bot)
        if not mute or not ismute:
            logger.debug(f"Sending new feed to Linkedin... {feed.get('title', '')}")                
            # Use short_link if present and not empty/None, otherwise use link
            link_to_use = feed.get('short_link')
            if not link_to_use:
                link_to_use = feed.get('link', '')
            logger.debug(f"LinkedinBotPublisher initialized with urn {urn}, access_toekn {access_token}.")
            logger.debug(f"{feed.get('title', '')}\n{feed.get('description', '')}\n{link_to_use}")
            linkedinbot = LinkedInPublisher(access_token, urn=urn, logger=logger)
            try:
                ai_comment = feed.get('ai-comment', '')
                if ai_comment == '':
                    ai_comment = None

                response = linkedinbot.post_link(
                    text=ai_comment or feed.get('description', ''),
                    link=link_to_use,
                    category=feed.get('category', []),
                )
                logger.debug(f"Server response: {response}")
            except Exception as e:
                logger.error(f"Error while posting: {e}")
                # Or, to log the stacktrace:
                # logger.exception("Error while posting:")
        else:
            logger.debug(f"Skipping Linkedin message for {feed.get('title', '')} due to mute setting.")

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
    base_time = datetime.now()
    cron = reader.get_value('settings', {}).get('cron', '0 * * * *')  # Default: every hour
    openai_comment_max_chars = reader.get_value('openai', {}).get('openai_comment_max_chars', 160) 
    openai_comment_language = reader.get_value('openai', {}).get('openai_comment_language', 'en')
    gptmodel = reader.get_value('openai', {}).get('openai_model', 'gpt-4.1-nano')
    mutefrom = reader.get_value('settings', {}).get('mute', {}).get('from', '00:00')
    muteto = reader.get_value('settings', {}).get('mute', {}).get('to', '00:00')
    mute = MuteTimeChecker(mutefrom, muteto, logger=logger)

    # --- Select GPT model ---
    if gptmodel == "auto":
        logger.info("OpenAI model not set. Using auto model.")
        gptmodel = GPTModelSelector(reader.get_value('openai')['openai_key']).get_cheapest_gpt_model()
    
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
        mute_logged = False  # Track if mute message has already been logged
        while True:
            # Calculate next run time using cron expression
            iter_cron = croniter(cron, base_time)
            next_run = iter_cron.get_next(datetime)
            sleep_time = (next_run - datetime.now()).total_seconds()
        # if not mute.is_mute_time():
            # mute_logged = False  # Reset when not in mute
            # --- Load previous RSS data ---
            filerss = JSONReader(logfile, create=True, logger=logger)
            previousrss = filerss.get_data()
            logger.debug("Full JSON data loaded from log file.")

            # --- Load feeds from config ---
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
                for feed in newfeeds:
                    send_feed_to_telegram(feed, reader, logger, mute.is_mute_time())
                    send_feed_to_bluesky(feed, reader, logger, mute.is_mute_time())
                    send_feed_to_linkedin(feed, reader, logger, mute.is_mute_time())
                # Save new feeds to file
                filerss.set_data(feedstofile)
                logger.debug(f"New feeds saved to {logfile}.")
            else:
                logger.info("No new feeds found.")
        # else:
        #     if not mute_logged:
        #         logger.info("Mute time, skipping feed update.")
        #         mute_logged = True

            # --- Wait before next execution ---
            if sleep_time < 0:
                logger.warning(f"Sleep time was negative ({sleep_time}), setting to 0.")
                sleep_time = 0
            if not mute.is_mute_time():
                logger.info(f"Waiting {int(sleep_time/60)} minutes before the next execution...")

            base_time = datetime.now()
            time.sleep(sleep_time)
    except KeyboardInterrupt:
        logger.info("Manual interruption received. Exiting program.")

"""
How to use this script:

- Run the script directly: `python socialbot.py`
- Use the `--config` option to specify a custom settings file.
- Use the `--verbose` flag for debug logging.

The main loop will:
1. Load configuration and feeds.
2. Check if it's mute time (no posting).
3. Fetch new RSS items and generate AI comments.
4. Send new items to Telegram and Bluesky.
5. Wait for the next scheduled run (cron-based).

You can extend the script by adding new senders or modifying the feed processing logic.
"""

if __name__ == "__main__":
    main()