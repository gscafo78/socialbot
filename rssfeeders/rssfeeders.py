#!/usr/bin/env python3
"""
rssfeeders.py

Optimized RSS feed fetcher with optional GPT‑powered comments.

Requirements:
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

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger import Logger
from gpt.gptcomment import ArticleCommentator

__version__ = "1.0.2"


class RSSFeeders:
    """
    Fetch and process RSS feeds, optionally generating AI (GPT) comments.

    Attributes:
        db:             Database helper for feed list & execution‐log methods.
        logger:         Logger instance for output.
        retention_days: Number of days to keep old entries (0 = today only).
        user_agent:     HTTP User‑Agent header for requests.
        mutetime:       If True, skip AI comment generation.
        base_url:       Base URL for the AI API.
        ai_max_chars:   Maximum characters for AI comment.
        ai_lang:        Language code for AI comment.
        gpt_model:      GPT model to use.
        ai_key:         OpenAI API key.
        session:        requests.Session() with default headers.
        feeds:          Cached list of feeds from the database.
    """

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36 Edg/136.0.3240.92"
    )

    # Patterns to truncate unwanted text segments
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
        mutetime: bool = False,
        base_url: Optional[str] = None,
    ) -> None:
        """
        Initialize RSSFeeders.

        Args:
            db:             Database manager for feeds and logs.
            logger:         Logger for debug/info/error messages.
            retention_days: Days to keep old entries (entries older than this are ignored).
            user_agent:     Custom HTTP User‑Agent header (defaults defined above).
            mutetime:       If True, disables AI comment generation.
            base_url:       Override AI API base URL from the database config.
        """
        self.db = db
        self.logger = logger
        self.mutetime = mutetime
        self.retention_days = retention_days or 0
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT

        # Load AI settings from the database
        ai_cfg = db.export_ai_config_cleartext()[0]
        self.base_url = base_url or ai_cfg["ai_base_url"]
        self.ai_max_chars = ai_cfg["ai_comment_max_chars"]
        self.ai_lang = ai_cfg["ai_comment_language"]
        self.gpt_model = ai_cfg["ai_model"]
        self.ai_key = ai_cfg["ai_key"]

        # Prepare an HTTP session (connection pooling + default headers)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

        # Cache the list of feeds from the database
        self.feeds = db.generate_feed_list()
        logger.debug(
            "Loaded %d feeds; AI enabled: %s",
            len(self.feeds),
            bool(self.ai_key and not mutetime),
        )

    @staticmethod
    def _parse_entry_date(entry: Dict[str, Any]) -> Optional[datetime]:
        """
        Extract the first available date (published or updated) from an RSS entry.

        Returns:
            A datetime object if found, otherwise None.
        """
        for field in ("published_parsed", "updated_parsed"):
            struct = entry.get(field)
            if struct:
                return datetime(*struct[:6])
        return None

    def _extract_image(self, html_str: str) -> Optional[str]:
        """
        Return the 'src' URL of the first <img> tag found in the given HTML snippet.

        Args:
            html_str: HTML content to scan.

        Returns:
            The image URL if found, otherwise None.
        """
        soup = BeautifulSoup(html_str, "html.parser")
        img = soup.find("img")
        return img.get("src") if img and img.get("src") else None

    def _sanitize_text(self, html_content: str) -> str:
        """
        Strip HTML tags, remove undesired sections, and normalize whitespace.

        Steps:
          1. Remove all HTML tags.
          2. Truncate at any of the precompiled cut patterns.
          3. Keep only the first line.
          4. Collapse multiple whitespace characters into a single space.
          5. Trim leading/trailing whitespace.

        Args:
            html_content: Raw HTML string.

        Returns:
            A cleaned, plain‑text snippet.
        """
        text = BeautifulSoup(html_content, "html.parser").get_text()

        for pat in self._CUT_PATTERNS:
            m = pat.search(text)
            if m:
                text = text[: m.start()]

        text = text.split("\n", 1)[0]
        text = self._SPACE_PATTERN.sub(" ", text).replace("\xa0", " ").strip()
        return text

    def get_latest_rss(self) -> List[Dict[str, Any]]:
        """
        Fetch each configured RSS feed and return its newest entry within the retention window.

        Workflow for each feed:
          1. HTTP GET → parse with feedparser.
          2. Filter entries by date ≥ cutoff date (based on retention_days).
          3. Skip entries already logged in the database.
          4. Extract title, sanitized description, categories, image, and short_link.
          5. Optionally generate an AI comment via GPT.

        Returns:
            A list of dicts with keys:
              'rss', 'link', 'datetime', 'title', 'description',
              'category', 'short_link', 'img_link', 'ai_comment'
        """
        results: List[Dict[str, Any]] = []

        cutoff_dt = (
            datetime.now() - timedelta(days=self.retention_days)
        ).replace(hour=0, minute=0, second=0, microsecond=0)

        for feed_info in self.feeds:
            rss_url = feed_info["rss"]

            # Fetch & parse the feed
            try:
                resp = self.session.get(rss_url, timeout=10)
                resp.raise_for_status()
                parsed = feedparser.parse(resp.content)
            except Exception as e:
                self.logger.error("Failed to fetch/parse RSS %s: %s", rss_url, e)
                continue

            if not parsed.entries:
                self.logger.debug("No entries for %s", rss_url)
                continue

            # Collect entries newer than cutoff date
            valid = []
            for entry in parsed.entries:
                dt = self._parse_entry_date(entry)
                if dt and dt >= cutoff_dt:
                    valid.append((entry, dt))

            if not valid:
                self.logger.debug(
                    "No recent entries for %s since %s", rss_url, cutoff_dt.date()
                )
                continue

            # Pick the most recent entry
            entry, dt = max(valid, key=lambda x: x[1])
            link = entry.get("link")

            # Skip if missing or already processed
            if not link or self.db.link_exists_in_execution_logs(link):
                self.logger.debug("Skipping seen or invalid link: %s", link)
                continue

            # Title & sanitized description
            title = html.unescape(entry.get("title", "") or "")
            desc_html = html.unescape(entry.get("description", "") or "")
            description = self._sanitize_text(desc_html)

            # Categories/tags
            categories = [t.get("term") for t in entry.get("tags", []) if t.get("term")]

            # Image: try media_content first, then HTML extract
            img_link: Optional[str] = None
            media = entry.get("media_content") or []
            if isinstance(media, list) and media:
                img_link = media[0].get("url")
            elif entry.get("content"):
                img_link = self._extract_image(entry["content"][0].get("value", ""))

            # Optionally generate AI comment
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
                    "rss":         rss_url,
                    "link":        link,
                    "datetime":    dt,
                    "title":       title,
                    "description": description,
                    "category":    categories,
                    "short_link":  entry.get("id"),
                    "img_link":    img_link,
                    "ai_comment":  ai_comment,
                }
            )

        return results