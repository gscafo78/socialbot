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
"""
[
    {
        "telegram": [
            {
                "name": "gs_cyberbot",
                "token": "7978695717:AAE3NS-QjpqZYX_dihbfwS7XA2IQo2QdH7c",
                "chat_id": "-1002663511141"
            },
            {
                "name": "gs_financebot",
                "token": "7732151977:AAH4Bkw68PGsxQNhkaMKXIBOGHAIoUSHlTY",
                "chat_id": "-1002541911908"
            },
            {
                "name": "gs_newsbot",
                "token": "7538733048:AAHKkiRQ9-zEMSZAiy1cbrahQpToFP7QwD4",
                "chat_id": "-1002554531164"
            }
        ]
    },
    {
        "bluesky": [
            {
                "name": "gscafo78",
                "handle": "gscafo78.bluesky.myhomecloud.it",
                "password": "Can8d1g0mm4!",
                "service": "https://bluesky.myhomecloud.it",
                "mute": true
            },
            {
                "name": "gscafo",
                "handle": "gscafo.bsky.social",
                "password": "Can8d1g0mm4!",
                "service": "https://bsky.social",
                "mute": true
            },
            {
                "name": "affaritaliani",
                "handle": "gs-affaritaliani.bsky.social",
                "password": "Can8d1g0mm4!",
                "service": "https://bsky.social",
                "mute": false
            },
            {
                "name": "ilgiornale",
                "handle": "gs-ilgiornale-bot.bsky.social",
                "password": "Can8d1g0mm4!",
                "service": "https://bsky.social",
                "mute": false
            },
            {
                "name": "formiche",
                "handle": "gs-formiche-bot.bluesky.myhomecloud.it",
                "password": "yfNwknfaJhyAO8DPH8L9p7tb",
                "service": "https://bluesky.myhomecloud.it",
                "mute": false
            },
            {
                "name": "ansa",
                "handle": "gs-ansa-bot.bluesky.myhomecloud.it",
                "password": "3wxDrE9lvpBAzK2iDmtPpdKv",
                "service": "https://bluesky.myhomecloud.it",
                "mute": false
            },
            {
                "name": "lastampa",
                "handle": "gs-lastampa-bot.bluesky.myhomecloud.it",
                "password": "SAgUJdv2rIZeJVYPpDcIRXi9",
                "service": "https://bluesky.myhomecloud.it",
                "mute": false
            },
            {
                "name": "repubblica",
                "handle": "gs-repubblica-bot.bluesky.myhomecloud.it",
                "password": "oc5RMuFWQsIq6kC6P3xX5DAs",
                "service": "https://bluesky.myhomecloud.it",
                "mute": false
            },
            {
                "name": "gazzetta",
                "handle": "gs-gazzetta-bot.bluesky.myhomecloud.it",
                "password": "ejrpbnivtMDfRzamgnrangwy",
                "service": "https://bluesky.myhomecloud.it",
                "mute": false
            },
            {
                "name": "ilsole24ore",
                "handle": "gs-ilsole24ore-bot.bluesky.myhomecloud.it",
                "password": "H7eX9TcpMwvZVaMIUsQ58CEC",
                "service": "https://bluesky.myhomecloud.it",
                "mute": false
            },
            {
                "name": "corrieredellosport",
                "handle": "gs-corrieresport.bluesky.myhomecloud.it",
                "password": "YJHP6lZOwCSxrsAT3syHSMTl",
                "service": "https://bluesky.myhomecloud.it",
                "mute": false
            },
            {
                "name": "corriere",
                "handle": "gs-corrieresera.bluesky.myhomecloud.it",
                "password": "0worN2ejoxi3tiHl56iv92lJ",
                "service": "https://bluesky.myhomecloud.it",
                "mute": false
            },
            {
                "name": "ilfoglio",
                "handle": "gs-ilfoglio-bot.bluesky.myhomecloud.it",
                "password": "qs7TSiDtH0EE6j5dL1Wy8Gxs",
                "service": "https://bluesky.myhomecloud.it",
                "mute": false
            }
        ]
    },
    {
        "linkedin": [
            {
                "name": "gscafo78",
                "urn": "1z-ly-tSO_",
                "access_token": "AQXFrh5ETcBAAglxkHfE7CwUPTDbyZOuksuLFIQ2Zj1bJrSABGbUxdRKqIqxgtTBfImHsLNxTbplf1T_-WboO_Sm6_hkDdOLWevlGL4KuXyHHZEXCVyBNMS0Adb_OL4uXV8Wjh25u3lfmE64hiEfYtIH4zLFxF31cWtrAcYCcRDZ5zndz1699JlmRbypDRhNRVUX8ITF56dFFv6j-5KzX3PZKS690HgWnQuXIAKLAXoDIlg6eahr4P4z-gejlkylXGD19cWbBAtMB9EozFUmjOOL1oErDsdbHMZDoYEklBdE0tYDTh7IxiITbES-WKqJZ2z3VPtNtCw89WHzpV__qIlGzGhUDA",
                "mute": true
            }
        ]
    }
]
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
from typing import Any, Dict, List, Optional

# Add parent directory to sys.path for local imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# from utils.readjson import JSONReader
from senders.telegramsendmsg import TelegramBotPublisher
from senders.blueskysendmsg import BlueskyPoster
from senders.linkedinpublisher import LinkedInPublisher

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

ConfigList = List[Dict[str, List[Dict[str, Any]]]]

def is_valid_url(url):
    """
    Check if a string is a valid HTTP/HTTPS URL.
    """
    try:
        result = urlparse(url)
        return result.scheme in ("http", "https")
    except Exception:
        return False

def find_bot(config: ConfigList, service: str, name: str) -> Optional[Dict[str, Any]]:
    """
    Ritorna il dizionario del bot di tipo `service` e di nome `name`.
    Se non trova corrispondenza, ritorna None.
    """
    for section in config:
        # se nella sezione c'è la chiave service (es. "telegram", "bluesky", "linkedin")
        if service in section:
            for bot in section[service]:
                if bot.get("name") == name:
                    return bot
    return None

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
        accouts : A Dictionary with bot credentials.
        logger (logging.Logger): Logger for output (INFO/DEBUG/etc).
    """

    def __init__(self, accounts, logger):
        self.accounts = accounts
        self.logger = logger

    async def send_to_telegram(self, feed: dict, ismute: bool = False):
        """
        Send a single feed to all configured Telegram bots asynchronously.

        Args:
            feed (dict): Feed entry with keys like 'title', 'description', 'short_link', etc.
            ismute (bool): If True, override individual bot mute flags (send anyway).
        """
        bots = feed.get("telegram", {}).get("bots", [])
        if len(bots) > 0:
            self.logger.debug("Telegram bots to send to: %s", bots)
            tasks = []
            for bot_name in bots:
                # da modificare per leggere i valori di telegram
                telegramaccount = find_bot(self.accounts, "telegram", bot_name)
                token = telegramaccount.get("token", "")
                chat_id = telegramaccount.get("chat_id", "")
                mute = telegramaccount.get("mute", False)
                # token, chat_id, _, mute = self.reader.get_social_values("telegram", bot_name)
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
            # Da modificare per leggere i valori di bluesky
            bsaccount = find_bot(self.accounts, "bluesky", bot_name)
            handle = bsaccount.get("handle", "")
            password = bsaccount.get("password", "")
            service = bsaccount.get("service", "")
            mute = bsaccount.get("mute", False)
            # handle, password, service, mute = self.reader.get_social_values("bluesky", bot_name)
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

            linkedinaccount = find_bot(self.accounts, "linkedin", bot_name)
            urn = linkedinaccount.get("urn", "")
            access_token = linkedinaccount.get("access_token", "")
            mute = linkedinaccount.get("mute", False)

            # Da modificare per leggere i valori di linkedin
            # urn, access_token, _, mute = self.reader.get_social_values("linkedin", bot_name)
            
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
    # reader = JSONReader(args.config, create=True, logger=logger)
    # sender = SocialSender(reader, logger)

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

    # logger.info("=== Sending to Telegram ===")
    # await sender.send_to_telegram(test_feed)

    # logger.info("=== Sending to Bluesky ===")
    # await sender.send_to_bluesky(test_feed)

    # logger.info("=== Sending to LinkedIn ===")
    # await sender.send_to_linkedin(test_feed)

    # logger.info("All messages dispatched. Exiting.")

if __name__ == "__main__":
    asyncio.run(main())