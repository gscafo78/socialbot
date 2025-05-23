import json
import time
from utils.readjson import JSONReader
from utils.logger import Logger
from rssfeeders.rssfeeders import RSSFeeders
# from gpt.gptcomment import ArticleCommentator
from gpt.getmodel import GPTModelSelector

# Logger configuration
logger = Logger.get_logger(__name__)


# def put_comment(feeds, openai_key, gptmodel, gptmaxchars=200, language="it"):
#     # inserire la procedutra di arricchimento del commento
#     commentend_feeds = []
#     for feed in feeds:
#         # print(feed["ai"])
#         if feed["ai"] == True:
#             gptcomment = ArticleCommentator(feed["link"], 
#                                             openai_key, 
#                                             gptmodel, 
#                                             gptmaxchars, 
#                                             language)
#             feed["ai-comment"] = gptcomment.generate_comment()
#             commentend_feeds.append(feed)
#             gptcomment = None
    
#     return commentend_feeds


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
                feed.setdefault("ai-comment", "")

            rss = RSSFeeders(feeds, previousrss)
            if reader.get_value('openai')['openai_model'] == "":
                logger.info("OpenAI model not set. Using auto model.")
                gptmodel = GPTModelSelector(reader.get_value('openai')['openai_key']).get_cheapest_gpt_model()
            else:
                gptmodel = reader.get_value('openai')['openai_model']
            
            newfeeds, feedstofile = rss.get_new_feeders(reader.get_value('openai')['openai_key'],
                                                        gptmodel,
                                                        200,
                                                        "it")
            
            if newfeeds != []:
                logger.info("New feeds found:")
                logger.info(json.dumps(newfeeds, indent=4, ensure_ascii=False, default=str))
                filerss.set_data(feedstofile)
            else:
                logger.info("No new feeds found.")

            logger.info("Waiting 10 minutes before the next execution...")
            time.sleep(600)  # 600 seconds = 10 minutes
    except KeyboardInterrupt:
        logger.info("Manual interruption received. Exiting program.")

if __name__ == "__main__":
    main()