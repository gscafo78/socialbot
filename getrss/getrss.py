import feedparser
from datetime import datetime
from bs4 import BeautifulSoup
import re

class RSSLatestItem:
    """
    Class to fetch the latest item from an RSS feed.

    Args:
        url (str): The URL of the RSS feed.

    Methods:
        get_latest_rss(): Returns a dictionary with link, datetime, description, and title of the latest item.
    """
    def __init__(self, url):
        self.url = url
        self.latest_item = None

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

    def get_latest_rss(self):
        """
        Parses the RSS feed and returns the latest item's details.

        Returns:
            dict: {
                "link": str,
                "datetime": datetime or None,
                "description": str (Markdown),
                "title": str
            }
            or None if no items are found.
        """
        feed = feedparser.parse(self.url)
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

def main():
    """
    Example usage:
    Fetches and prints the latest RSS item from the given feed URL.
    """
    rss_url = "https://www.cshub.com/rss/articles"
    rss = RSSLatestItem(rss_url)
    result = rss.get_latest_rss()
    if result:
        print(f"Link: {result['link']}")
        print(f"Datetime: {result['datetime']}")
        print(f"Description:\n{result['description']}")
        print(f"Title: {result['title']}")
    else:
        print("No items found.")

if __name__ == "__main__":
    main()