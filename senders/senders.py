#!/usr/bin/env python3
"""
social_sender.py

Utility for dispatching a single “feed” entry to Telegram, Bluesky, and LinkedIn
bots configured in a JSON settings file.

Usage examples:
  # Show version
  python social_sender.py --version

  # Run with INFO-level logging (default)
  python social_sender.py --config ./settings.json

  # Run with DEBUG-level logging
  python social_sender.py --config ./settings.json --debug
"""

__version__ = "0.0.1"

import argparse
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.readjson import JSONReader
from senders.telegramsendmsg import TelegramBotPublisher
from senders.blueskysendmsg import BlueskyPoster
from senders.linkedinpublisher import LinkedInPublisher

# ------------------------------------------------------------------------------
# Module‐level logging configuration
# ------------------------------------------------------------------------------
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


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

    def send_to_telegram(self, feed, ismute=False):
        """
        Send a single feed to all configured Telegram bots.

        Args:
            feed (dict): Feed entry with keys like 'title', 'description', 'short_link', etc.
            ismute (bool): If True, override individual bot mute flags (send anyway).
        """
        bots = feed.get("telegram", {}).get("bots", [])
        for bot_name in bots:
            # Retrieve token/chat_id + mute flag from settings.json
            token, chat_id, _, mute = self.reader.get_social_values("telegram", bot_name)

            # Skip if bot is muted (unless globally overridden via ismute)
            if mute and not ismute:
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
            link_to_use = feed.get("short_link") or feed.get("link", "")
            msg = f"{feed.get('title','')}\n{feed.get('description','')}\n{link_to_use}"
            self.logger.debug("Payload for Telegram: %s", msg.replace("\n", " | "))
            telebot.send_message(msg)

    def send_to_bluesky(self, feed, ismute=False):
        """
        Send a single feed to all configured Bluesky bots.

        Args:
            feed (dict): Feed entry with keys like 'title', 'description', 'short_link', etc.
            ismute (bool): If True, override individual bot mute flags (send anyway).
        """
        bots = feed.get("bluesky", {}).get("bots", [])
        for bot_name in bots:
            handle, password, service, mute = self.reader.get_social_values("bluesky", bot_name)

            if mute and not ismute:
                self.logger.debug(
                    "Skipping Bluesky message for '%s' due to mute setting.", feed.get("title", "")
                )
                continue

            self.logger.debug(
                "Sending new feed to Bluesky bot '%s' → %s",
                bot_name, feed.get("title", "")
            )
            link_to_use = feed.get("short_link") or feed.get("link", "")
            self.logger.debug(
                "BlueskyPoster init with handle=%s, service=%s", handle, service
            )
            self.logger.debug(
                "Payload: %s\n%s",
                feed.get("title",""), feed.get("description","")
            )

            blueskybot = BlueskyPoster(handle, password, service)
            try:
                ai_comment = feed.get("ai-comment") or None
                response = blueskybot.post_feed(
                    description=feed.get("description", ""),
                    link=link_to_use,
                    ai_comment=ai_comment,
                    title=feed.get("title", "")
                )
                self.logger.debug("Bluesky server response: %s", response)
            except Exception as exc:
                self.logger.error("Error while posting to Bluesky: %s", exc)

    def send_to_linkedin(self, feed, ismute=False):
        """
        Send a single feed to all configured LinkedIn accounts.

        Args:
            feed (dict): Feed entry with keys like 'title', 'description', 'short_link', etc.
            ismute (bool): If True, override individual bot mute flags (send anyway).
        """
        bots = feed.get("linkedin", {}).get("bots", [])
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
            link_to_use = feed.get("short_link") or feed.get("link", "")
            self.logger.debug(
                "LinkedInPublisher init with urn=%s", urn
            )
            self.logger.debug(
                "Payload: %s\n%s",
                feed.get("title",""), feed.get("description","")
            )

            linkedinbot = LinkedInPublisher(access_token, urn=urn, logger=self.logger)
            try:
                ai_comment = feed.get("ai-comment") or None
                text_for_post = ai_comment or feed.get("description", "")
                response = linkedinbot.post_link(
                    text=text_for_post,
                    link=link_to_use,
                    category=feed.get("category", []),
                )
                self.logger.debug("LinkedIn server response: %s", response)
            except Exception as exc:
                self.logger.error("Error while posting to LinkedIn: %s", exc)


def main():
    """
    Command‑line interface for SocialSender.

    Examples:
      # Show version
      python social_sender.py --version

      # Run with default INFO logging
      python social_sender.py --config ./settings.json

      # Run with DEBUG logging enabled
      python social_sender.py --config ./settings.json --debug
    """
    parser = argparse.ArgumentParser(
        description="Dispatch a single feed entry to Telegram, Bluesky & LinkedIn bots."
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
    logger = logging.getLogger(__name__)

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
    sender.send_to_telegram(test_feed)

    logger.info("=== Sending to Bluesky ===")
    sender.send_to_bluesky(test_feed)

    logger.info("=== Sending to LinkedIn ===")
    sender.send_to_linkedin(test_feed)


if __name__ == "__main__":
    main()