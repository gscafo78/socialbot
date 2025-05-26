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


def send_feed_to_telegram(feed, reader, logger):
    """
    Send a single feed to all configured Telegram bots.
    """
    bots = feed.get("telegram", {}).get("bots", [])
    for bot in bots:
        logger.debug(f"Sending new feed to Telegram... {feed.get('title', '')}")                
        token, chat_id, _ = reader.get_social_credentials("telegram", bot)
        logger.debug(f"TelegramBotPublisher initialized with token {token} and chat_id {chat_id}.")
        logger.debug(f"{feed.get('title', '')}\n{feed.get('description', '')}\n{feed.get('link', '')}")
        telebot = TelegramBotPublisher(token, chat_id)
        telebot.send_message(f"{feed.get('title', '')}\n{feed.get('description', '')}\n{feed.get('link', '')}")

def send_feed_to_bluesky(feed, reader, logger):
    """
    Send a single feed to all configured Bluesky bots.
    """
    bots = feed.get("bluesky", {}).get("bots", [])
    for bot in bots:
        logger.debug(f"Sending new feed to BlueSky... {feed.get('title', '')}")                
        handle, password, service = reader.get_social_credentials("bluesky", bot)
        logger.debug(f"BlueskyBotPublisher initialized with Handel {handle}, password {password} and service {service}.")
        logger.debug(f"{feed.get('title', '')}\n{feed.get('description', '')}\n{feed.get('link', '')}")
        blueskybot = BlueskyPoster(handle, password, service)
        try:
            response = blueskybot.post_with_preview(feed.get('title', ''), feed.get('link', ''))
            logger.debug(f"Server response: {response}")
        except Exception as e:
            logger.error("Error while posting:", e)

def main():
    # --- Configuration file path ---
    file_path = "/opt/github/03_Script/Python/socialbot/settings.json"
    
    
    # --- Logger setup ---
    log_level_str = "INFO"
    # Temporary logger for config reading
    temp_logger = Logger.get_logger(__name__, level=log_level_str)
    reader = JSONReader(file_path, logger=temp_logger)
    
    log_level_str = reader.get_value('settings', {}).get('log_level', 'INFO')
    logger = Logger.get_logger(__name__, level=log_level_str)
    

    # Re-initialize reader with the correct logger if needed
    reader = JSONReader(file_path, logger=logger)
    feeds_path = reader.get_value('settings', {}).get('feeds_file', "/opt/github/03_Script/Python/socialbot/feeds.json")
    
    readfeeds = JSONReader(feeds_path, logger=logger)


    # --- Log file and update interval ---
    logfile = reader.get_value('settings', {}).get('log_file', '/var/log/socialbot.log').lower()
    base_time = datetime.now()
    cron = reader.get_value('settings', {}).get('cron', '0 * * * *')  # Default: every hour
    openai_comment_max_chars = reader.get_value('openai', {}).get('openai_comment_max_chars', 160) 
    openai_comment_language = reader.get_value('openai', {}).get('openai_comment_language', 'en')
    gptmodel = reader.get_value('openai', {}).get('openai_model', 'gpt-4.1-nano')
    mutefrom = reader.get_value('settings', {}).get('mute', {}).get('from', '00:00')
    muteto = reader.get_value('settings', {}).get('mute', {}).get('to', '00:00')
    mute = MuteTimeChecker(mutefrom, muteto, logger=logger)

    # --- Select GPT model ---
    if gptmodel == "auto" :
        logger.info("OpenAI model not set. Using auto model.")
        gptmodel = GPTModelSelector(reader.get_value('openai')['openai_key']).get_cheapest_gpt_model()
    
    logger.debug(f"File setting path: {file_path}")
    logger.info(f"Feeds file path: {feeds_path}")
    logger.info(f"Log file path: {logfile}")
    logger.info(f"Feed update interval by cron: {cron}")
    logger.info(f"Mute is {mute.is_mute_time()}, because is from: {mutefrom}, to: {muteto}")
    logger.info(f"OpenAI model: {gptmodel}")
    logger.info(f"OpenAI comment max chars: {openai_comment_max_chars}")
    logger.info(f"OpenAI comment language: {openai_comment_language}")

    try:
        while True:
            iter_cron = croniter(cron, base_time)
            next_run = iter_cron.get_next(datetime)
            sleep_time = (next_run - datetime.now()).total_seconds()
            if not mute.is_mute_time():
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
                rss = RSSFeeders(feeds, previousrss, logger=logger)

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
                        send_feed_to_telegram(feed, reader, logger)
                        send_feed_to_bluesky(feed, reader, logger)

                    filerss.set_data(feedstofile)
                    logger.debug(f"New feeds saved to {logfile}.")
                else:
                    logger.info("No new feeds found.")

            
            
            # --- Wait before next execution ---
            logger.info(f"Waiting {int(sleep_time/60)} minutes before the next execution...")
            base_time = datetime.now()
            time.sleep(sleep_time)  
    except KeyboardInterrupt:
        logger.info("Manual interruption received. Exiting program.")


if __name__ == "__main__":
    main()