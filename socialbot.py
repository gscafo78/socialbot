import json
import time
from datetime import datetime, timedelta
from utils.readjson import JSONReader
from getrss.getrss import RSSLatestItem
from utils.logger import Logger

# Logger configuration
logger = Logger.get_logger(__name__)

def readrss(rss_urls, newrss):
    """
    Reads a list of RSS feed URLs, fetches the latest item from each,
    and adds it to the result list if it is not older than 6 months and not a duplicate.

    Args:
        rss_urls (list): List of RSS feed URLs to process.
        newrss (list): List to store new RSS items (dicts).

    Returns:
        list: List of RSS items (dicts) not older than 6 months and not duplicated.
    """
    risultato_rss = []

    logger.info("Starting RSS reading...")
    six_months_ago = datetime.now().astimezone() - timedelta(days=6*30)  # Approximation of 6 months

    for rss_url in rss_urls:
        rss = RSSLatestItem(rss_url)
        result = rss.get_latest_rss()

        if result:
            item_datetime = result.get('datetime')
            if item_datetime and item_datetime > six_months_ago:
                # Check for duplicates by link
                if not any(item['link'] == result['link'] for item in risultato_rss):
                    # Check if already present in newrss
                    existing = next((item for item in newrss if item['link'] == result['link']), None)
                    if existing:
                        # Replace if different
                        if existing != result:
                            newrss.remove(existing)
                            newrss.append({'link': result['link'],
                                           'datetime': result['datetime'],
                                           'description': result['description'],
                                           'title': result['title'],
                                           'printed': False})
                    else:
                        # Add new feed
                        newrss.append({'link': result['link'],
                                       'datetime': result['datetime'],
                                       'description': result['description'],
                                       'title': result['title'],
                                       'printed': False})
                    # Accumulate result
                    risultato_rss.append({'link': result['link'],
                                          'datetime': result['datetime'],
                                          'description': result['description'],
                                          'title': result['title'],
                                          'printed': False})
                else:
                    # Duplicate already present, skip
                    pass
            else:
                logger.info(f"Skipped (older than 6 months): {rss_url}")
        else:
            logger.warning(f"No items found for {rss_url}")

    return risultato_rss

def main():
    """
    Runs the main loop in an infinite cycle, with a 10-minute pause between each execution.
    Exits only if Ctrl+C is pressed.

    How to run:
        python socialbot.py

    Required variables:
        - settings.json: JSON configuration file containing at least the 'rss' key with a list of RSS feed URLs.
        - The script expects the file path to be set in 'file_path' variable (default: /opt/github/03_Script/Python/socialbot/settings.json).
    """
    file_path = "/opt/github/03_Script/Python/socialbot/settings.json"  # Path to your JSON config file
    reader = JSONReader(file_path)
    newrss = []
    try:
        while True:
            config = reader.get_data()
            logger.info("Full JSON data:")
            # logger.info(json.dumps(config, indent=4, ensure_ascii=False))
            value = reader.get_value('rss', default="Key not found")
            logger.info(f"Value for key 'rss': {value}")
            newrss = readrss(config['rss'], newrss)
            print(json.dumps(newrss, indent=4, ensure_ascii=False, default=str))
            logger.info("Waiting 10 minutes before the next execution...")
            time.sleep(600)  # 600 seconds = 10 minutes
    except KeyboardInterrupt:
        logger.info("Manual interruption received. Exiting program.")

if __name__ == "__main__":
    main()