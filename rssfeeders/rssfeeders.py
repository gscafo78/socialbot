import feedparser
from datetime import datetime
from bs4 import BeautifulSoup
import re
from utils.logger import Logger
import concurrent.futures
from datetime import datetime, timedelta

logger = Logger.get_logger(__name__)

class RSSFeeders:
    """
    Class to fetch and process the latest items from a list of RSS feeds.

    Args:
        feeds (list): List of feed dictionaries (each with at least a 'rss' key).
        previousrss (list): List of previously processed feeds (to avoid duplicates).

    Methods:
        get_latest_rss(url): Returns a dictionary with link, datetime, description, and title of the latest item.
        get_new_feeders(): Returns new feeds not present in previousrss and updates previousrss.
    """

    def __init__(self, feeds, previviousrss, retention=10):
        """
        Initialize the RSSFeeders object.

        Args:
            feeds (list): List of feed dictionaries.
            previviousrss (list): List of previously processed feeds.
        """
        self.feeds = feeds
        self.previousrss = previviousrss
        self.retention = retention

    def remove_old_feeds(self, previousrss):
        """
        Removes feeds older than self.retention days from previousrss.
        Args:
            previousrss (list): List of previously processed feeds.
        Returns:
            list: Updated list of feeds, excluding those older than retention period.
        """ 
        now = datetime.now(tz=None)
        retention_delta = timedelta(days=self.retention)
        filtered_previousrss = []
        for feed in previousrss:
            dt = feed.get('datetime')
            # Only keep feeds with a valid datetime and within retention period
            if isinstance(dt, datetime):
                # Make both datetimes either naive or aware
                if dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None:
                    now_cmp = datetime.now(dt.tzinfo)
                else:
                    now_cmp = now.replace(tzinfo=None)
                if now_cmp - dt <= retention_delta:
                    filtered_previousrss.append(feed)
            else:
                # If datetime is missing or invalid, keep the feed (optional: you can skip it)
                filtered_previousrss.append(feed)
        return filtered_previousrss
    
    def html_to_markdown(self, html_text):
        """
        Converts HTML content to Markdown format and removes unwanted "article source" lines.

        Args:
            html_text (str): The HTML string to convert.

        Returns:
            str: The converted and cleaned Markdown string.
        """
        soup = BeautifulSoup(html_text, "html.parser")
        markdown_lines = []
        # Extract all <p> and <a> elements
        for element in soup.find_all(['p', 'a']):
            if element.name == 'p':
                text = element.get_text(strip=True)
                # Remove lines like "L'articolo...proviene da..."
                if not re.match(r"^L'articolo.*proviene da.*\.$", text):
                    if text:
                        markdown_lines.append(text)
            elif element.name == 'a':
                href = element.get('href', '')
                text = element.get_text(strip=True)
                if href and text:
                    markdown_lines.append(f"[{text}]({href})")
        # If there are no <p> or <a>, fallback to plain text
        if not markdown_lines:
            return soup.get_text(separator="\n", strip=True)
        return "\n\n".join(markdown_lines)

    def get_latest_rss(self, url):
        """
        Parses the RSS feed and returns the latest item's details.

        Args:
            url (str): The RSS feed URL.

        Returns:
            dict: {
                "link": str,
                "datetime": datetime or None,
                "description": str (Markdown),
                "title": str
            }
            or None if no items are found.
        """
        feed = feedparser.parse(url)
        if feed.entries:
            latest = feed.entries[0]
            link = latest.link
            description = latest.description if 'description' in latest else ''
            # Clean and convert description to Markdown if it contains HTML
            if "<" in description and ">" in description:
                description = self.html_to_markdown(description)
            title = latest.title if 'title' in latest else ''
            date_time = latest.published if 'published' in latest else ''
            if not date_time and 'updated' in latest:
                date_time = latest.updated
            # Try to parse the date string to a datetime object
            try:
                date_time_dt = datetime.strptime(date_time, '%a, %d %b %Y %H:%M:%S %z')
            except (ValueError, TypeError):
                date_time_dt = None
            return {
                "link": link,
                "datetime": date_time_dt,
                "description": description,
                "title": title
            }
        return None

    def get_new_feeders(self):
        """
        Checks all feeds for new items not present in previousrss, using multithreading.
        Removes feeds older than self.retention days from previousrss.

        Returns:
            tuple: (newfeeds, previousrss)
                newfeeds (list): List of new feed dictionaries found.
                previousrss (list): Updated list including new feeds.
        """
        newfeeds = []
        previousrss = self.previousrss

        def process_feed(feed):
            """Process a single feed and return updated feed if new, else None."""
            result = self.get_latest_rss(feed['rss'])
            if result and not any(f.get('link', '') == result['link'] for f in previousrss):
                feed['link'] = result['link']
                feed['datetime'] = result['datetime']
                feed['description'] = result['description']
                feed['title'] = result['title']
                logger.info(f"Added new feed: {feed['link']}")
                return feed
            else:
                logger.info(f"No new feed found for {feed['rss']}")
                return None

        # Use ThreadPoolExecutor to process feeds in parallel
        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = list(executor.map(process_feed, self.feeds))

        # Filter out None results and update lists
        for feed in results:
            if feed:
                newfeeds.append(feed)
                previousrss.append(feed)

        previousrss = self.remove_old_feeds(previousrss)

        return newfeeds, previousrss


def main():
    """
    Example usage:
    Fetches and prints the latest RSS item from the given feed URL.
    """
    rss_url = "https://www.cshub.com/rss/articles"
    # rss = RSSLatestItem(rss_url)
    # result = rss.get_latest_rss()
    # if result:
    #     print(f"Link: {result['link']}")
    #     print(f"Datetime: {result['datetime']}")
    #     print(f"Description:\n{result['description']}")
    #     print(f"Title: {result['title']}")
    # else:
    #     print("No items found.")

if __name__ == "__main__":
    main()