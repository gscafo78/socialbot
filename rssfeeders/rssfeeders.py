#!/usr/bin/env python3
"""
rss_feeders.py  (version 1.0.0)

Fetch and process the latest items from one or more RSS feeds.  Optionally
generate AI comments on new entries via OpenAI GPT models.

Usage:
    # Show version
    python rss_feeders.py --version

    # Basic usage: fetch new items for these feeds
    python rss_feeders.py \
      --feeds https://8bitsecurity.com/feed/ \
      --feeds https://www.fanpage.it/feed/

    # Persist processed links to disk, so duplicates are skipped next time
    python rss_feeders.py \
      --feeds https://8bitsecurity.com/feed/ \
      --previous-file seen.json

    # Also generate AI comment (160 chars max) in Italian
    python rss_feeders.py \
      --feeds https://8bitsecurity.com/feed/ \
      --previous-file seen.json \
      --openai-key sk-... \
      --model gpt-4.1-nano \
      --language it \
      --max-chars 160

    # Enable debug logging
    python rss_feeders.py --debug --feeds https://8bitsecurity.com/feed/

Requirements:
    pip install feedparser requests beautifulsoup4 openai
"""

import argparse
import concurrent.futures
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import feedparser
import html
import requests
from bs4 import BeautifulSoup
from openai import OpenAI

# Ensure your utils.logger and gptcomment modules are on PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logger import Logger                # noqa: E402
from gpt.gptcomment import ArticleCommentator   # noqa: E402

__version__ = "1.0.0"


class RSSFeeders:
    """
    Fetch and process the latest items from a list of RSS feeds.
    Optionally generate an AI comment on each new item.

    Args:
        feeds:           List of dicts, each with key 'rss' for the feed URL.
        previous:        Previously seen items (to avoid duplicates).
        retention_days:  How many days to keep old entries in the previous list.
        logger:          A configured Logger instance (injected).
        user_agent:      HTTP User‑Agent header for fetching feeds.
    """

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36 Edg/136.0.3240.92"
    )

    def __init__(
        self,
        feeds: List[Dict[str, Any]],
        previous: List[Dict[str, Any]],
        retention_days: int,
        logger: logging.Logger,
        user_agent: Optional[str] = None,
    ) -> None:
        self.feeds = feeds.copy()
        self.previous = previous.copy()
        self.retention_days = retention_days
        self.logger = logger
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT

    def _prune_previous(self) -> None:
        """
        Remove entries from self.previous that are older than retention_days.
        """
        now = datetime.now()
        cutoff = timedelta(days=self.retention_days)
        kept: List[Dict[str, Any]] = []

        for item in self.previous:
            dt = item.get("datetime")
            if isinstance(dt, datetime):
                if now - dt <= cutoff:
                    kept.append(item)
                else:
                    self.logger.debug("Pruned old entry %s (>%d days)",
                                      item.get("link"), self.retention_days)
            else:
                # Keep items without valid datetime
                kept.append(item)

        self.previous = kept

    def _extract_image(self, html_str: str) -> Optional[str]:
        """
        Extract the first <img src="..."> URL from an HTML snippet.
        """
        match = re.search(r'<img[^>]+src="([^"]+)"', html_str)
        return match.group(1) if match else None

    def _html_to_markdown(self, html_text: str) -> str:
        """
        Convert an HTML description to plaintext/markdown:
          - Keep <p> paragraphs
          - Convert <a href> to [text](url)
          - Strip boilerplate lines like "L'articolo ... proviene da."
        """
        soup = BeautifulSoup(html_text, "html.parser")
        lines: List[str] = []

        for el in soup.find_all(["p", "a"]):
            if el.name == "p":
                txt = el.get_text(strip=True)
                if not re.match(r"^L'articolo.*proviene da.*\.$", txt):
                    if txt:
                        lines.append(txt)
            else:  # <a>
                href = el.get("href", "").strip()
                txt = el.get_text(strip=True)
                if href and txt:
                    lines.append(f"[{txt}]({href})")

        return "\n\n".join(lines) or soup.get_text(separator="\n", strip=True)

    def get_latest_rss(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Fetch an RSS URL and return its newest entry (within retention_days),
        cleaned up and ready for AI processing.

        Returns:
            A dict with keys: link, datetime, title, description, category,
            short_link, img_link, or None if no valid new item.
        """
        headers = {"User-Agent": self.user_agent}
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
        except Exception as e:
            self.logger.error("Failed to fetch/parse RSS %s: %s", url, e)
            return None

        if not feed.entries:
            return None

        def _entry_date(e) -> Optional[datetime]:
            for key in ("published_parsed", "updated_parsed"):
                struct = e.get(key)
                if struct:
                    return datetime(*struct[:6])
            return None

        dated = [(e, _entry_date(e)) for e in feed.entries]
        dated = [(e, dt) for e, dt in dated if dt is not None]
        if not dated:
            return None

        # Pick the most recent entry
        entry, dt = max(dated, key=lambda pair: pair[1])
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        if now - dt > timedelta(days=self.retention_days):
            self.logger.debug("No recent entries in %s within %d days",
                              url, self.retention_days)
            return None

        desc = entry.get("description", "") or ""
        desc = self._html_to_markdown(desc)
        desc = html.unescape(desc)

        title = html.unescape(entry.get("title", ""))

        # Category/tags
        cats = None
        if isinstance(entry.get("tags"), list):
            cats = [t.get("term") for t in entry.tags if t.get("term")]

        # Image: first look in media_content, else parse HTML
        img = None
        media = entry.get("media_content", [])
        if media and isinstance(media, list):
            img = media[0].get("url")
        elif entry.get("content"):
            img = self._extract_image(entry.content[0].get("value", ""))

        return {
            "link": entry.get("link"),
            "datetime": dt,
            "title": title,
            "description": desc,
            "category": cats,
            "short_link": entry.get("id"),
            "img_link": img,
        }

    def get_new_feeders(
        self,
        openai_key: Optional[str] = None,
        gptmodel: Optional[str] = None,
        max_chars: int = 160,
        language: str = "en",
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Process all feeds in parallel, compare to previously seen entries,
        and return any NEW items + the updated previous list (pruned/extended).

        If openai_key & gptmodel are provided, also generate an AI comment
        for feeds whose dict has feed['ai'] == True.

        Returns:
            new_items: List of new feed‑dicts (with same keys + optional 'ai-comment').
            previous:  The updated previous list, pruned by retention_days.
        """
        self._prune_previous()
        new_items: List[Dict[str, Any]] = []

        def _worker(fdict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            info = self.get_latest_rss(fdict["rss"])
            if not info:
                self.logger.debug("No new entry at %s", fdict["rss"])
                return None

            # Skip if link already seen
            if any(prev.get("link") == info["link"] for prev in self.previous):
                self.logger.debug("Already seen %s", info["link"])
                return None

            # Merge feed‑level metadata into this new entry
            out = {**fdict, **info}

            # Optionally generate AI comment
            if fdict.get("ai") and openai_key and gptmodel:
                commentator = ArticleCommentator(
                    link=out["link"],
                    api_key=openai_key,
                    logger=self.logger,
                    model=gptmodel,
                    max_chars=max_chars,
                    language=language,
                )
                out["ai-comment"] = commentator.generate_comment()

            self.logger.info("Discovered new RSS item: %s", out["link"])
            return out

        with concurrent.futures.ThreadPoolExecutor() as pool:
            futures = pool.map(_worker, self.feeds)
            for result in futures:
                if result:
                    new_items.append(result)
                    self.previous.append(result)

        # Final prune before returning
        self._prune_previous()
        return new_items, self.previous


def _load_previous(path: Path) -> List[Dict[str, Any]]:
    """
    Load a JSON list of previously seen items (with ISO datetime strings).
    """
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        # Convert ISO‑strings back to datetime
        for item in raw:
            if "datetime" in item and isinstance(item["datetime"], str):
                item["datetime"] = datetime.fromisoformat(item["datetime"])
        return raw
    except Exception:
        return []


def _save_previous(path: Path, data: List[Dict[str, Any]]) -> None:
    """
    Save the previous list to disk, converting datetimes to ISO strings.
    """
    out: List[Dict[str, Any]] = []
    for item in data:
        copy = item.copy()
        dt = copy.get("datetime")
        if isinstance(dt, datetime):
            copy["datetime"] = dt.isoformat()
        out.append(copy)
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch RSS feeds, detect new items, and optionally comment with GPT."
    )
    parser.add_argument(
        "--feeds",
        "-f",
        action="append",
        required=True,
        help="RSS feed URL to monitor (repeatable).",
    )
    parser.add_argument(
        "--previous-file",
        type=Path,
        help="Path to JSON file storing previously seen items.",
    )
    parser.add_argument(
        "--retention",
        type=int,
        default=10,
        help="Days to retain old items in the previous list (default: 10).",
    )
    parser.add_argument(
        "--openai-key",
        default=os.getenv("OPENAI_API_KEY"),
        help="OpenAI API key (or set OPENAI_API_KEY).",
    )
    parser.add_argument(
        "--model",
        help="GPT model to use for AI comments (e.g. gpt-4.1-nano).",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=160,
        help="Max characters for AI-generated comment (default: 160).",
    )
    parser.add_argument(
        "--language",
        choices=("en", "it"),
        default="en",
        help="Language for AI comment: 'en' or 'it' (default: en).",
    )
    parser.add_argument(
        "--user-agent",
        help="Custom HTTP User-Agent header for RSS requests.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug-level logging.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s v{__version__}",
        help="Show program version and exit.",
    )
    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(message)s")
    logger = logging.getLogger("rss_feeders")

    # Prepare previous list
    previous_list: List[Dict[str, Any]] = []
    if args.previous_file:
        previous_list = _load_previous(args.previous_file)
        logger.info("Loaded %d previous items from %s", len(previous_list), args.previous_file)

    # Build feed dicts (add 'ai'=True if model/key present)
    feeds = [{"rss": url, "ai": bool(args.openai_key and args.model)} for url in args.feeds]

    feeder = RSSFeeders(
        feeds=feeds,
        previous=previous_list,
        retention_days=args.retention,
        logger=logger,
        user_agent=args.user_agent,
    )

    new_items, updated_previous = feeder.get_new_feeders(
        openai_key=args.openai_key,
        gptmodel=args.model,
        max_chars=args.max_chars,
        language=args.language,
    )

    # Output results
    if new_items:
        print(json.dumps(new_items, indent=2, ensure_ascii=False, default=str))
    else:
        logger.info("No new RSS items found.")

    # Save back previous-file if requested
    if args.previous_file:
        _save_previous(args.previous_file, updated_previous)
        logger.info("Saved %d items to %s", len(updated_previous), args.previous_file)

    # Exit code 0 always (no error unless exceptional)
    sys.exit(0)


if __name__ == "__main__":
    main()