#!/usr/bin/env python3
"""
senders.py

SocialSender: Utility for dispatching a single feed entry to Telegram, BlueSky,
and LinkedIn based on credentials and settings.

Description:
- Reads bot credentials and settings from a JSON config file (pass via --config).
- Sends a test feed (example) or your own feed entry to all configured bots for
  Telegram, BlueSky, and LinkedIn.
- Logs every step at INFO level by default, or DEBUG level if --debug is passed.
- Prints responses and errors to the log.
- Version is shown with --version.

"""
__version__ = "1.0.0"

import argparse
import logging
import sys
import os
import asyncio
import random
from urllib.parse import urlparse
from functools import partial
from typing import Any, Dict, List, Optional

# Allow importing local modules in a development layout
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# JSONReader could be used to load the config if desired:
# from utils.readjson import JSONReader

from senders.telegramsendmsg import TelegramBotPublisher
from senders.blueskysendmsg import BlueskyPoster
from senders.linkedinpublisher import LinkedInPublisher

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

# Type alias for the account/config structure
ConfigList = List[Dict[str, List[Dict[str, Any]]]]


def is_valid_url(url: str) -> bool:
    """
    Return True if the given string is a valid HTTP or HTTPS URL.
    """
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https")
    except Exception:
        return False


def find_bot(
    config: ConfigList, service: str, name: str
) -> Optional[Dict[str, Any]]:
    """
    Locate the bot configuration dict for a given service and bot name.

    Args:
        config: List of service sections from the config (e.g. [{"telegram": [...]}, ...]).
        service: One of "telegram", "bluesky", or "linkedin".
        name:    The 'name' identifier of the bot (must match config entry).

    Returns:
        The matching bot config dict, or None if not found.
    """
    for section in config:
        if service in section:
            for bot in section[service]:
                if bot.get("name") == name:
                    return bot
    return None


async def run_in_thread(func, *args, **kwargs):
    """
    Run a blocking function in a thread and await its result.
    Useful for calling synchronous APIs from async code.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(func, *args, **kwargs))


class SocialSender:
    """
    Coordinates sending a single feed entry to all configured social bots.

    Args:
        accounts: List of bot credentials/settings loaded from the JSON config.
        logger:   Logger instance for INFO/DEBUG output.
    """

    def __init__(self, accounts: ConfigList, logger: logging.Logger):
        self.accounts = accounts
        self.logger = logger

    async def send_to_telegram(self, feed: dict, ismute: bool = False):
        """
        Dispatch a feed entry to each specified Telegram bot.

        Args:
            feed:   Feed dict with 'title', 'description', 'short_link', etc.
            ismute: If True, ignore individual bot mute flags and send anyway.
        """
        bot_names = feed.get("telegram", {}).get("bots", [])
        if not bot_names:
            return

        self.logger.debug("Telegram bots to send to: %s", bot_names)
        tasks = []
        for bot_name in bot_names:
            bot_cfg = find_bot(self.accounts, "telegram", bot_name) or {}
            token = bot_cfg.get("token", "")
            chat_id = bot_cfg.get("chat_id", "")
            mute = bot_cfg.get("mute", False)

            if mute and ismute:
                self.logger.debug(
                    "Skipping Telegram bot '%s' due to mute: %s", bot_name, feed.get("title")
                )
                continue

            self.logger.debug("Sending to Telegram bot '%s': %s", bot_name, feed.get("title"))
            telebot = TelegramBotPublisher(token, chat_id)

            short_url = feed.get("short_link", "")
            if not is_valid_url(short_url):
                self.logger.error("Invalid short_link URL: %s", short_url)
                link_to_use = feed.get("link", "")
            else:
                link_to_use = short_url

            msg = f"{feed.get('title','')}\n{feed.get('description','')}\n{link_to_use}"
            self.logger.debug("Telegram payload: %s", msg.replace("\n", " | "))
            tasks.append(run_in_thread(telebot.send_message, msg))

        if tasks:
            await asyncio.gather(*tasks)

    async def send_to_bluesky(self, feed: dict, ismute: bool = False):
        """
        Dispatch a feed entry to each specified BlueSky bot.

        Args:
            feed:   Feed dict with 'title', 'description', 'short_link', etc.
            ismute: If True, ignore individual bot mute flags and send anyway.
        """
        bot_names = feed.get("bluesky", {}).get("bots", [])
        if not bot_names:
            return

        tasks = []
        for bot_name in bot_names:
            bot_cfg = find_bot(self.accounts, "bluesky", bot_name) or {}
            handle = bot_cfg.get("handle", "")
            password = bot_cfg.get("password", "")
            service = bot_cfg.get("service", "")
            mute = bot_cfg.get("mute", False)

            if mute and ismute:
                self.logger.debug(
                    "Skipping Bluesky bot '%s' due to mute: %s", bot_name, feed.get("title")
                )
                continue

            self.logger.debug("Sending to Bluesky bot '%s': %s", bot_name, feed.get("title"))

            short_url = feed.get("short_link", "")
            if not is_valid_url(short_url):
                self.logger.error("Invalid short_link URL: %s", short_url)
                link_to_use = feed.get("link", "")
            else:
                link_to_use = short_url

            blueskybot = BlueskyPoster(handle, password, service)
            ai_comment = feed.get("ai-comment")

            tasks.append(
                run_in_thread(
                    blueskybot.post_feed,
                    title=feed.get("title", ""),
                    description=feed.get("description", ""),
                    link=link_to_use,
                    ai_comment=ai_comment
                )
            )

        if tasks:
            await asyncio.gather(*tasks)

    async def send_to_linkedin(self, feed: dict, ismute: bool = False, sleep_time: float = 0):
        """
        Dispatch a feed entry to each specified LinkedIn bot.

        Args:
            feed:       Feed dict with 'title', 'description', 'short_link', etc.
            ismute:     If True, ignore individual bot mute flags and send anyway.
            sleep_time: Max back-off window (seconds) to randomize delays
                        between consecutive LinkedIn posts.
        """
        bot_names = feed.get("linkedin", {}).get("bots", [])
        if not bot_names:
            return

        tasks = []
        for bot_name in bot_names:
            bot_cfg = find_bot(self.accounts, "linkedin", bot_name) or {}
            urn = bot_cfg.get("urn", "")
            access_token = bot_cfg.get("access_token", "")
            mute = bot_cfg.get("mute", False)

            if mute and ismute:
                self.logger.debug(
                    "Skipping LinkedIn bot '%s' due to mute: %s", bot_name, feed.get("title")
                )
                continue

            self.logger.debug("Sending to LinkedIn bot '%s': %s", bot_name, feed.get("title"))

            short_url = feed.get("short_link", "")
            if not is_valid_url(short_url):
                self.logger.error("Invalid short_link URL: %s", short_url)
                link_to_use = feed.get("link", "")
            else:
                link_to_use = short_url

            linkedinbot = LinkedInPublisher(access_token, urn=urn, logger=self.logger)
            ai_comment = feed.get("ai-comment")
            text_to_post = ai_comment or feed.get("description", "")

            if sleep_time > 0:
                delay = random.uniform(0, sleep_time / 2)
                self.logger.debug("Back-off %.1f seconds before LinkedIn post", delay)
                await asyncio.sleep(delay)

            tasks.append(
                run_in_thread(
                    linkedinbot.post_link,
                    text=text_to_post,
                    link=link_to_use,
                    category=feed.get("category", [])
                )
            )

        if tasks:
            await asyncio.gather(*tasks)