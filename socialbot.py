import json
import os
import time
from datetime import datetime, timedelta
from utils.readjson import JSONReader
from rssfeeders.rssfeeders import RSSFeeders
from utils.logger import Logger

# Logger configuration
logger = Logger.get_logger(__name__)


def main():
    """
    Runs the main loop in an infinite cycle, with a 10-minute pause between each execution.
    Exits only if Ctrl+C is pressed.
    """
    file_path = "/opt/github/03_Script/Python/socialbot/settings.json"  # Path to your JSON config file
    tmp_file = "/tmp/socialbot.tmp"

    reader = JSONReader(file_path)
    try:
        while True:
            filerss = JSONReader(tmp_file, create=True)
            previousrss = filerss.get_data()
            logger.info("Full JSON data:")

            feeds = reader.get_value('feeds', default=[])
            logger.info(f"Value for key 'feeds': {feeds}")
            newfeeds = []
            feedstofile = []

            # Aggiungi le chiavi mancanti a ogni feed
            for feed in feeds:
                feed.setdefault("link", "")
                feed.setdefault("datetime", "")
                feed.setdefault("description", "")
                feed.setdefault("title", "")

            rss = RSSFeeders(feeds, previousrss)
            newfeeds, feedstofile = rss.get_new_feeders()
            filerss.set_data(feedstofile)

            # print(json.dumps(feeds, indent=4, ensure_ascii=False, default=str))
            print(json.dumps(newfeeds, indent=4, ensure_ascii=False, default=str))

            logger.info("Waiting 10 minutes before the next execution...")
            time.sleep(600)  # 600 seconds = 10 minutes
    except KeyboardInterrupt:
        logger.info("Manual interruption received. Exiting program.")

if __name__ == "__main__":
    main()