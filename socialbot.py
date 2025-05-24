import json
import time
from utils.readjson import JSONReader
from utils.logger import Logger
from rssfeeders.rssfeeders import RSSFeeders
from gpt.getmodel import GPTModelSelector

def main():
    # --- Configuration file path ---
    file_path = "/opt/github/03_Script/Python/socialbot/settings.json"
    reader = JSONReader(file_path)
    
    # --- Logger setup ---
    log_level_str = reader.get_value('settings', {}).get('log_level', 'INFO')
    logger = Logger.get_logger(__name__, level=log_level_str)

    # --- Log file and update interval ---
    logfile = reader.get_value('settings', {}).get('log_file', '/var/log/socialbot.log').lower()
    feed_update_interval = reader.get_value('settings', {}).get('feed_update_interval', 600)  # Default: 10 minutes
    openai_comment_max_chars = reader.get_value('openai', {}).get('openai_comment_max_chars', 160) 
    openai_comment_language = reader.get_value('openai', {}).get('openai_comment_language', 'en')
    gptmodel = reader.get_value('openai', {}).get('openai_model', 'gpt-4.1-nano')

    # --- Select GPT model ---
    if gptmodel == "auto" :
        logger.info("OpenAI model not set. Using auto model.")
        gptmodel = GPTModelSelector(reader.get_value('openai')['openai_key']).get_cheapest_gpt_model()
    
    logger.debug(f"File setting path: {file_path}")
    logger.info(f"Log file path: {logfile}")
    logger.info(f"Feed update interval: {feed_update_interval} seconds")
    logger.info(f"OpenAI model: {gptmodel}")
    logger.info(f"OpenAI comment max chars: {openai_comment_max_chars}")
    logger.info(f"OpenAI comment language: {openai_comment_language}")

    
    try:
        while True:
            # --- Load previous RSS data ---
            filerss = JSONReader(logfile, create=True)
            previousrss = filerss.get_data()
            logger.debug("Full JSON data loaded from log file.")

            # --- Load feeds from config ---
            feeds = reader.get_value('feeds', default=[])
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
            
            if newfeeds != []:
                logger.info("New feeds found:")
                logger.info(json.dumps(newfeeds, indent=4, ensure_ascii=False, default=str))
                filerss.set_data(feedstofile)
            else:
                logger.info("No new feeds found.")

            # --- Wait before next execution ---
            logger.info(f"Waiting {int(feed_update_interval/60)} minutes before the next execution...")
            time.sleep(feed_update_interval)  
    except KeyboardInterrupt:
        logger.info("Manual interruption received. Exiting program.")

if __name__ == "__main__":
    main()