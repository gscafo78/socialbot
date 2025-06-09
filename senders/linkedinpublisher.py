#!/usr/bin/env python3
"""
linkedin_publisher.py

Class to publish posts on LinkedIn via the v2 API.  
Includes a command‐line interface for quick testing.

Usage examples:
    # Show version and exit
    python linkedin_publisher.py --version

    # Publish a post with text, link and categories (INFO-level logs by default)
    python linkedin_publisher.py \
      --token YOUR_ACCESS_TOKEN \
      --link https://example.com/article \
      --text "Check out this article on cybersecurity." \
      --category CyberSecurity CyberCrime DataProtection

    # Same, but with DEBUG logs enabled
    python linkedin_publisher.py ... --debug
"""

__version__ = "0.0.3"

import sys
import os
import json
import logging
import argparse
import requests

# Ensure the parent directory is on PYTHONPATH so we can import Category
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rssfeeders.sanitizecategory import Category


# ------------------------------------------------------------------------------
# Module‐level logging configuration
# ------------------------------------------------------------------------------
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(format=LOG_FORMAT)
logger = logging.getLogger(__name__)


class LinkedInPublisher:
    """
    Class to publish posts and comments on LinkedIn using the v2 API.

    Args:
        access_token (str): OAuth2 access token with the required scopes.
        urn (str, optional): Your LinkedIn URN (person identifier). If omitted,
                             it will be fetched automatically via /userinfo.
        api_url (str): Base URL for LinkedIn’s REST API (default: https://api.linkedin.com/v2/).
        user_agent (str, optional): Custom User-Agent header.
        logger (logging.Logger, optional): Logger to use (default module logger).
    """
    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    )

    def __init__(self,
                 access_token,
                 urn=None,
                 api_url="https://api.linkedin.com/v2/",
                 user_agent=None,
                 logger=None):
        self.access_token = access_token
        self.api_url = api_url.rstrip("/") + "/"
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        # Fetch or accept a provided URN
        self.urn = urn or self.get_user_urn()
        # Common headers for all LinkedIn calls
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }

    def get_user_urn(self):
        """
        Retrieve the user's URN (unique LinkedIn identifier) via /userinfo.

        Returns:
            str: The URN string (e.g. 'urn:li:person:XXXXXXXX').
        Raises:
            requests.HTTPError on failure.
        """
        self.logger.debug("Fetching user URN via /userinfo with headers:\n%s",
                          json.dumps(self.headers, indent=2))
        resp = requests.get(f"{self.api_url}userinfo", headers=self.headers)
        resp.raise_for_status()
        urn = resp.json().get("sub")
        self.logger.info("Retrieved user URN: %s", urn)
        return urn

    def post_link(self, text, link, category=None):
        """
        Publish a post containing a link and optional hashtags.

        Args:
            text (str): The body text of the post.
            link (str): The URL to share.
            category (list[str], optional): List of category strings to convert to hashtags.

        Returns:
            dict: The JSON response from LinkedIn’s UGC Posts API.

        Raises:
            requests.HTTPError on non-2xx.
        """
        # Append the link at the end of the text
        post_text = f"{text}\n\n🔗 Link all'articolo {link}"
        # If categories passed, sanitize and convert to hashtags
        if category:
            post_text += "\n\n"
            sanitizer = Category(category, logger=logging.getLogger(__name__))
            sanitizer.sanitize(5)             # dedupe & normalize
            hashtags = sanitizer.hashtag()    # generate hashtags
            for tag in hashtags:
                post_text += f"{tag} "

        payload = {
            "author": f"urn:li:person:{self.urn}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": post_text},
                    "shareMediaCategory": "ARTICLE",
                    "media": [
                        {
                            "status": "READY",
                            "originalUrl": link
                        }
                    ]
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }

        self.logger.debug("POST payload to /ugcPosts:\n%s",
                          json.dumps(payload, indent=2, ensure_ascii=False))
        resp = requests.post(f"{self.api_url}ugcPosts", headers=self.headers, json=payload)
        resp.raise_for_status()
        self.logger.info("LinkedIn post created successfully.")
        return resp.json()


def main():
    """
    Command‐line interface for LinkedInPublisher.

    Examples:
      # Show version
      linkedin_publisher.py --version

      # Publish a post with text, link, and categories (INFO logs)
      linkedin_publisher.py \
        --token YOUR_ACCESS_TOKEN \
        --link https://example.com/article \
        --text "Check out this new article!" \
        --category CyberSecurity CyberCrime DataProtection

      # Same, but with DEBUG logging enabled
      linkedin_publisher.py ... --debug
    """
    parser = argparse.ArgumentParser(
        description="Publish a link post on LinkedIn via the v2 API"
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program version and exit."
    )
    parser.add_argument(
        "-t", "--token",
        required=True,
        help="OAuth2 access token for LinkedIn v2 API"
    )
    parser.add_argument(
        "-u", "--urn",
        help="Your LinkedIn URN (if known). If omitted, the script will fetch it."
    )
    parser.add_argument(
        "-l", "--link",
        required=True,
        help="URL to share in the post"
    )
    parser.add_argument(
        "-x", "--text",
        required=True,
        help="Text/comment to accompany the link"
    )
    parser.add_argument(
        "-c", "--category",
        nargs="*",
        help="Optional list of categories/hashtags"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable DEBUG-level logging (default is INFO)"
    )

    args = parser.parse_args()

    # Configure root logging level
    level = logging.DEBUG if args.debug else logging.INFO
    logger.setLevel(level)

    # Instantiate the publisher
    publisher = LinkedInPublisher(
        access_token=args.token,
        urn=args.urn,
        logger=logger
    )

    # Execute post_link() and log the response
    try:
        result = publisher.post_link(
            text=args.text,
            link=args.link,
            category=args.category or []
        )
        logger.debug("LinkedIn API response:\n%s", json.dumps(result, indent=2))
    except Exception as e:
        logger.error("Failed to create LinkedIn post: %s", e)


if __name__ == "__main__":
    main()