#!/usr/bin/env python3
"""
rssfeeders.py

Optimized RSS feed fetcher + optional GPT‑powered comments.

USAGE EXAMPLES:
    # Show version
    python rssfeeders.py --version

    # Fetch and display the latest item from each feed
    python rssfeeders.py --feeds https://8bitsecurity.com/feed/ --feeds https://www.fanpage.it/feed/

    # Test image extraction / HTML sanitization
    python rssfeeders.py --test-extract-image --html "<p>Test <img src='https://img.com/x.jpg'></p>"
    python rssfeeders.py --test-sanitize-text --html "<div>Test <b>bold</b></div>"

    # Fetch items + AI comment
    python rssfeeders.py --feeds https://8bitsecurity.com/feed/ --ai-key sk-... --model gpt-4.1-nano

REQUIREMENTS:
    pip install feedparser requests beautifulsoup4 openai
"""

import logging
import re
import html
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import feedparser
import requests
from bs4 import BeautifulSoup

import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger import Logger
from gpt.gptcomment import ArticleCommentator

__version__ = "1.0.2"


class RSSFeeders:
    """
    Fetch and process RSS feeds, optionally generating AI comments.
    """

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36 Edg/136.0.3240.92"
    )

    # Precompile patterns for performance
    _CUT_PATTERNS = [
        re.compile(r"Contenuto a pagamento"),
        re.compile(r"<a h"),
    ]
    _SPACE_PATTERN = re.compile(r"\s+", flags=re.UNICODE)

    def __init__(
        self,
        db,
        logger: logging.Logger,
        retention_days: Optional[int] = 0,
        user_agent: Optional[str] = None,
        mutetime: Optional[bool] = False,
        base_url: Optional[str] = None,
    ) -> None:
        """
        Args:
            db:                         Database/helper with feed list & execution‑log methods.
            logger:                     Logger instance.
            retention_days:             Days to keep old entries.
            user_agent:                 Custom HTTP User‑Agent.
            mutetime:                   Disable AI comments if True.
            base_url:                   Override AI API base URL.
        """
        self.db = db
        self.logger = logger
        self.mutetime = mutetime
        self.retention_days = retention_days or 0
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT

        # Load AI config from DB
        ai_cfg = db.export_ai_config_cleartext()[0]
        self.base_url = base_url or ai_cfg["ai_base_url"]
        self.ai_max_chars = ai_cfg["ai_comment_max_chars"]
        self.ai_lang = ai_cfg["ai_comment_language"]
        self.gpt_model = ai_cfg["ai_model"]
        self.ai_key = ai_cfg["ai_key"]

        # Prepare HTTP session (connection pooling + default headers)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

        # Cache feed definitions
        self.feeds = db.generate_feed_list()
        logger.debug("Loaded %d feeds, AI enabled: %s", len(self.feeds), bool(self.ai_key and not mutetime))

    @staticmethod
    def _parse_entry_date(entry: dict) -> Optional[datetime]:
        """Extract first available date from feed entry."""
        for field in ("published_parsed", "updated_parsed"):
            struct = entry.get(field)
            if struct:
                return datetime(*struct[:6])
        return None

    def _extract_image(self, html_str: str) -> Optional[str]:
        """Return first <img> src URL found in HTML snippet, or None."""
        soup = BeautifulSoup(html_str, "html.parser")
        img = soup.find("img")
        return img.get("src") if img and img.get("src") else None

    def _sanitize_text(self, html_content: str) -> str:
        """
        Strip HTML tags, cut unwanted sections, normalize whitespace.
        """
        text = BeautifulSoup(html_content, "html.parser").get_text()
        # Cut off at any of the unwanted markers
        for pat in self._CUT_PATTERNS:
            m = pat.search(text)
            if m:
                text = text[: m.start()]
        # Only take first line
        text = text.split("\n", 1)[0]
        # Normalize all whitespace
        text = self._SPACE_PATTERN.sub(" ", text).replace("\xa0", " ").strip()
        return text

    def get_latest_rss(self) -> List[Dict[str, Any]]:
        """
        Fetch each feed, pick newest entry within retention period, sanitize
        and optionally generate an AI comment.

        Returns:
            List of dicts with keys
            ['rss', 'link', 'datetime', 'title', 'description',
             'category', 'short_link', 'img_link', 'ai_comment']
        """
        results: List[Dict[str, Any]] = []
        cutoff_dt = (
            datetime.now() - timedelta(days=self.retention_days)
        ).replace(hour=0, minute=0, second=0, microsecond=0)

        for feed_info in self.feeds:
            url = feed_info["rss"]
            try:
                resp = self.session.get(url, timeout=10)
                resp.raise_for_status()
                parsed = feedparser.parse(resp.content)
            except Exception as e:
                self.logger.error("Failed to fetch/parse RSS %s: %s", url, e)
                continue

            if not parsed.entries:
                self.logger.debug("No entries for %s", url)
                continue

            # Filter & sort entries by date
            valid = []
            for entry in parsed.entries:
                dt = self._parse_entry_date(entry)
                if dt and dt >= cutoff_dt:
                    valid.append((entry, dt))
            if not valid:
                self.logger.debug("No recent entries for %s since %s", url, cutoff_dt.date())
                continue

            entry, dt = max(valid, key=lambda x: x[1])
            link = entry.get("link")
            if not link or self.db.link_exists_in_execution_logs(link):
                self.logger.debug("Skipping already seen or malformed link: %s", link)
                continue

            # Title & description
            title = html.unescape(entry.get("title", "") or "")
            desc_html = html.unescape(entry.get("description", "") or "")
            description = self._sanitize_text(desc_html)

            # Categories/tags
            categories = [t.get("term") for t in entry.get("tags", []) if t.get("term")]

            # Image: media_content first, fallback to HTML scrape
            img_link = None
            media = entry.get("media_content") or []
            if isinstance(media, list) and media:
                img_link = media[0].get("url")
            elif entry.get("content"):
                img_link = self._extract_image(entry["content"][0].get("value", ""))

            # Optional AI comment
            ai_comment = ""
            if feed_info.get("ai") and self.ai_key and self.gpt_model and not self.mutetime:
                commentator = ArticleCommentator(
                    link=link,
                    api_key=self.ai_key,
                    logger=self.logger,
                    model=self.gpt_model,
                    base_url=self.base_url,
                    max_chars=self.ai_max_chars,
                    language=self.ai_lang,
                )
                ai_comment = commentator.generate_comment() or ""
                self.logger.info("Generated AI comment for %s", link)

            results.append(
                {
                    "rss": url,
                    "link": link,
                    "datetime": dt,
                    "title": title,
                    "description": description,
                    "category": categories,
                    "short_link": entry.get("id"),
                    "img_link": img_link,
                    "ai_comment": ai_comment,
                }
            )

        return results