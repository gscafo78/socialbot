#!/usr/bin/env python3
"""
senders.py

SocialSender: Utility for dispatching a single feed entry to Telegram, Bluesky, and LinkedIn
using credentials and settings from a JSON configuration file.

USAGE EXAMPLES:
  # Show version
  python senders.py --version

  # Run with INFO-level logging (default)
  python senders.py --config ./settings.json

  # Run with DEBUG-level logging
  python senders.py --config ./settings.json --debug

DESCRIPTION:
- Reads bot credentials and settings from a JSON config file (see --config).
- Sends a sample feed (or your own) to all configured Telegram, Bluesky, and LinkedIn bots.
- Uses logging for all output (INFO by default, DEBUG if --debug is passed).
- Prints all responses and errors to the log.
- Version is shown with --version.

ARGUMENTS:
  -c, --config   Path to JSON settings file (required)
  --debug        Enable DEBUG-level logging (default is INFO)
  --version      Show program version and exit

EXAMPLE CONFIG STRUCTURE (settings.json):
{
  "telegram": {"bots": {"default": {"token": "...", "chat_id": "...", "mute": false}}},
  "bluesky":  {"bots": {"default": {"handle": "...", "password": "...", "service": "...", "mute": false}}},
  "linkedin": {"bots": {"default": {"urn": "...", "access_token": "...", "mute": false}}}
}

EXAMPLE FEED STRUCTURE:
{
  "title":      "Test Title",
  "description": "Test Description",
  "short_link":  "https://example.com/test",
  "ai-comment":  "This is an AI-generated comment.",
  "category":    ["news", "cyber security"],
  "telegram": {"bots": ["default"]},
  "bluesky":  {"bots": ["default"]},
  "linkedin": {"bots": ["default"]}
}
"""

__version__ = "0.0.7"

import argparse
import logging
import sys
import os
import asyncio
import random
from urllib.parse import urlparse
from functools import partial

# Add parent directory to sys.path for local imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.readjson import JSONReader
from senders.telegramsendmsg import TelegramBotPublisher
from senders.blueskysendmsg import BlueskyPoster
from senders.linkedinpublisher import LinkedInPublisher

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

def is_valid_url(url):
    """
    Check if a string is a valid HTTP/HTTPS URL.
    """
    try:
        result = urlparse(url)
        return result.scheme in ("http", "https")
    except Exception:
        return False

async def run_in_thread(func, *args, **kwargs):
    """
    Run a blocking function in a thread for async compatibility.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(func, *args, **kwargs))

class SocialSender:
    """
    Coordinates sending a single feed entry to all configured social bots.

    Args:
        reader (JSONReader): JSONReader instance for reading bot credentials.
        logger (logging.Logger): Logger for output (INFO/DEBUG/etc).
    """

    def __init__(self, reader, logger):
        self.reader = reader
        self.logger = logger

    async def send_to_telegram(self, feed: dict, ismute: bool = False):
        """
        Send a single feed to all configured Telegram bots asynchronously.

        Args:
            feed (dict): Feed entry with keys like 'title', 'description', 'short_link', etc.
            ismute (bool): If True, override individual bot mute flags (send anyway).
        """
        bots = feed.get("telegram", {}).get("bots", [])
        tasks = []
        for bot_name in bots:
            token, chat_id, _, mute = self.reader.get_social_values("telegram", bot_name)
            if mute and ismute:
                self.logger.debug(
                    "Skipping Telegram message for '%s' due to mute setting.", feed.get("title", "")
                )
                continue
            self.logger.debug(
                "Sending new feed to Telegram bot '%s' → %s",
                bot_name, feed.get("title", "")
            )
            self.logger.debug(
                "TelegramBotPublisher initialized with token=%s, chat_id=%s", token, chat_id
            )
            telebot = TelegramBotPublisher(token, chat_id)
            if not is_valid_url(feed.get("short_link")):
                link_to_use = feed.get("link", "")
                self.logger.error("Invalid URL: %s", feed.get("short_link"))
                self.logger.info("New URL: %s", link_to_use)
            else:
                link_to_use = feed.get("short_link") or feed.get("link", "")
            msg = f"{feed.get('title','')}\n{feed.get('description','')}\n{link_to_use}"
            self.logger.debug("Payload for Telegram: %s", msg.replace("\n", " | "))
            tasks.append(
                run_in_thread(telebot.send_message, msg)
            )
        if tasks:
            await asyncio.gather(*tasks)

    async def send_to_bluesky(self, feed: dict, ismute: bool = False):
        """
        Send a single feed to all configured Bluesky bots asynchronously.

        Args:
            feed (dict): Feed entry with keys like 'title', 'description', 'short_link', etc.
            ismute (bool): If True, override individual bot mute flags (send anyway).
        """
        bots = feed.get("bluesky", {}).get("bots", [])
        tasks = []
        for bot_name in bots:
            handle, password, service, mute = self.reader.get_social_values("bluesky", bot_name)
            if mute and ismute:
                self.logger.debug(
                    "Skipping Bluesky message for '%s' due to mute setting.", feed.get("title", "")
                )
                continue
            self.logger.debug(
                "Sending new feed to Bluesky bot '%s' → %s",
                bot_name, feed.get("title", "")
            )
            if not is_valid_url(feed.get("short_link")):
                link_to_use = feed.get("link", "")
                self.logger.error("Invalid URL: %s", feed.get("short_link"))
                self.logger.info("New URL: %s", link_to_use)
            else:
                link_to_use = feed.get("short_link") or feed.get("link", "")
            self.logger.debug(
                "BlueskyPoster init with handle=%s, service=%s", handle, service
            )
            self.logger.debug(
                "Payload: %s\n%s",
                feed.get("title",""), feed.get("description","")
            )
            blueskybot = BlueskyPoster(handle, password, service)
            ai_comment = feed.get("ai-comment") or None
            tasks.append(
                run_in_thread(
                    blueskybot.post_feed,
                    description=feed.get("description", ""),
                    link=link_to_use,
                    ai_comment=ai_comment,
                    title=feed.get("title", "")
                )
            )
        if tasks:
            await asyncio.gather(*tasks)

    async def send_to_linkedin(self, feed: dict, ismute: bool = False, sleep_time: int = 0):
        """
        Send a single feed to all configured LinkedIn accounts asynchronously.

        Args:
            feed (dict): Feed entry with keys like 'title', 'description', 'short_link', etc.
            ismute (bool): If True, override individual bot mute flags (send anyway).
            sleep_time (int): Time to wait before sending next batch (to avoid spamming).
        """
        bots = feed.get("linkedin", {}).get("bots", [])
        tasks = []
        for bot_name in bots:
            urn, access_token, _, mute = self.reader.get_social_values("linkedin", bot_name)
            if mute and ismute:
                self.logger.debug(
                    "Skipping LinkedIn message for '%s' due to mute setting.", feed.get("title", "")
                )
                continue
            self.logger.debug(
                "Sending new feed to LinkedIn bot '%s' → %s",
                bot_name, feed.get("title", "")
            )
            if not is_valid_url(feed.get("short_link")):
                link_to_use = feed.get("link", "")
                self.logger.error("Invalid URL: %s", feed.get("short_link"))
                self.logger.info("New URL: %s", link_to_use)
            else:
                link_to_use = feed.get("short_link") or feed.get("link", "")
            self.logger.debug(
                "LinkedInPublisher init with urn=%s", urn
            )
            self.logger.debug(
                "Payload: %s\n%s",
                feed.get("title",""), feed.get("description","")
            )
            linkedinbot = LinkedInPublisher(access_token, urn=urn, logger=self.logger)
            ai_comment = feed.get("ai-comment") or None
            text_for_post = ai_comment or feed.get("description", "")
            # Random back-off to avoid spamming multiple bots simultaneously
            if sleep_time > 30:
                rnd = random.uniform(0, sleep_time - (sleep_time / 2))
                self.logger.debug("Backing off %.1f seconds before sending next batch", rnd)
                await asyncio.sleep(rnd)
            tasks.append(
                run_in_thread(
                    linkedinbot.post_link,
                    text=text_for_post,
                    link=link_to_use,
                    category=feed.get("category", []),
                )
            )
        if tasks:
            await asyncio.gather(*tasks)

async def main():
    """
    Command-line interface for SocialSender (async version).

    - Reads configuration and credentials from a JSON file.
    - Instantiates SocialSender and sends a test feed to all configured platforms asynchronously.
    - Logging level is INFO by default, DEBUG if --debug is passed.
    - Shows version with --version.

    Usage:
      python senders.py --config ./settings.json
      python senders.py --config ./settings.json --debug
      python senders.py --version
    """
    parser = argparse.ArgumentParser(
        description="Dispatch a single feed entry to Telegram, Bluesky & LinkedIn bots (async)."
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program version and exit."
    )
    parser.add_argument(
        "-c", "--config",
        required=True,
        help="Path to JSON settings file (with credentials for each social bot)."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable DEBUG-level logging (default is INFO)."
    )

    args = parser.parse_args()

    # Configure root logger
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level, format=LOG_FORMAT)
    logger = logging.getLogger("socialbot.senders")

    logger.info("SocialSender version %s starting up...", __version__)

    # Instantiate JSONReader & SocialSender
    reader = JSONReader(args.config, create=True, logger=logger)
    sender = SocialSender(reader, logger)

    # Example feed for testing – replace or extend as needed
    test_feed = {
        "title":      "Test Title",
        "description": "Test Description",
        "short_link":  "https://example.com/test",
        "ai-comment":  "This is an AI-generated comment.",
        "category":    ["news", "cyber security"],
        "telegram": {"bots": ["default"]},
        "bluesky":  {"bots": ["default"]},
        "linkedin": {"bots": ["default"]},
    }

    logger.info("=== Sending to Telegram ===")
    await sender.send_to_telegram(test_feed)

    logger.info("=== Sending to Bluesky ===")
    await sender.send_to_bluesky(test_feed)

    logger.info("=== Sending to LinkedIn ===")
    await sender.send_to_linkedin(test_feed)

    logger.info("All messages dispatched. Exiting.")

if __name__ == "__main__":
    asyncio.run(main())