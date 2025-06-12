#!/usr/bin/env python3
"""
bluesky_poster.py

Utility to post feed entries (with optional link previews) to Bluesky via the XRPC API.

This module provides the BlueskyPoster class for:
  - Authenticating to a Bluesky server
  - Building link‐preview embeds by scraping metadata
  - Posting feeds (with or without preview) according to Bluesky’s schema

It also exposes a command‐line interface:

    # Show version
    python bluesky_poster.py --version

    # Post to Bluesky with a simple link preview
    python bluesky_poster.py \
      --handle yourname.bsky.social \
      --password YOUR_APP_PASSWORD \
      --link https://example.com/article \
      --description "Some summary text" \
      --title "Article Title"

    # Same, but with debug logging and forcing more metadata in preview
    python bluesky_poster.py \
      --handle yourname.bsky.social \
      --password YOUR_APP_PASSWORD \
      --link https://example.com/article \
      --description "Some summary text" \
      --title "Article Title" \
      --more-info \
      --debug
"""

import argparse
import html
import json
import logging
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ------------------------------------------------------------------------------
# Module version
# ------------------------------------------------------------------------------
__version__ = "1.0.1"

# ------------------------------------------------------------------------------
# Module‐level logging configuration
# ------------------------------------------------------------------------------
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(format=LOG_FORMAT)
logger = logging.getLogger(__name__)


class BlueskyPoster:
    """
    Poster for Bluesky feeds, supporting optional link‐preview embeds.

    Attributes:
        handle (str): Bluesky handle (e.g. 'alice.bsky.social').
        app_password (str): Application password for Bluesky authentication.
        service (str): Base URL of the Bluesky instance (default 'https://bsky.social').
        user_agent (str): User‐Agent string for fetching previews.
        access_jwt (str): JWT obtained after authentication.
        did (str): Decentralized identifier for the authenticated user.
        session (requests.Session): Session to reuse connections and headers.
        logger (logging.Logger): Logger for this class.
    """

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    )
    MAX_POST_LENGTH = 299  # Bluesky’s maximum post length in characters

    def __init__(self, handle, app_password, service="https://bsky.social",
                 user_agent=None, logger=None):
        self.handle = handle
        self.app_password = app_password
        self.service = service.rstrip("/")  # Ensure no trailing slash
        self.access_jwt = None
        self.did = None
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT
        self.session = requests.Session()
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    def create_session(self):
        """
        Authenticate to Bluesky and store access_jwt & did for future requests.
        Raises an exception on failure.
        """
        resp = requests.post(
            f"{self.service}/xrpc/com.atproto.server.createSession",
            json={"identifier": self.handle, "password": self.app_password},
        )
        resp.raise_for_status()
        session = resp.json()
        self.access_jwt = session["accessJwt"]
        self.did = session["did"]
        self.logger.info("Successfully authenticated as %s", self.handle)

    def create_simple_embed(self, url, title=None, description=None):
        """
        Fallback embed for when detailed metadata fetching fails.

        Args:
            url (str): The URL to embed.
            title (str): Optional title override.
            description (str): Optional description override.

        Returns:
            dict: A minimal external embed object.
        """
        card = {
            "uri": url,
            "title": title or "Link Preview",
            "description": description or "Visit the link for more information",
        }
        return {"$type": "app.bsky.embed.external", "external": card}

    def fetch_embed_url_card(self, url, more_info=False):
        """
        Fetch OpenGraph metadata (title/description/image) from a URL and upload image blob.

        Args:
            url (str): The target URL for preview.
            more_info (bool): If True, attempt to include description metadata.

        Returns:
            dict: A Bluesky external embed record.
        """
        self.logger.debug("Attempting to fetch preview for URL: %s", url)
        card = {"uri": url, "title": "", "description": ""}

        # Set headers to mimic a real browser for best metadata coverage
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        self.session.headers.update(headers)

        try:
            time.sleep(1)  # polite delay
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # ===== TITLE EXTRACTION =====
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                card["title"] = og_title["content"]
            elif soup.title and soup.title.string:
                card["title"] = soup.title.string

            # Normalize HTML entities and encoding issues
            if card["title"]:
                # Decodifica eventuali entità HTML
                card["title"] = html.unescape(card["title"])
                # Prova a sistemare eventuali errori di doppia codifica
                try:
                    card["title"] = card["title"].encode("latin1").decode("utf-8")
                except (UnicodeEncodeError, UnicodeDecodeError):
                    pass

            # Truncate excessively long titles
            if len(card["title"]) > 250:
                card["title"] = card["title"][:247] + "..."
            if not card["title"]:
                card["title"] = "Link Preview"

            # ===== DESCRIPTION EXTRACTION (optional) =====
            if more_info:
                og_desc = soup.find("meta", property="og:description")
                if og_desc and og_desc.get("content"):
                    card["description"] = og_desc["content"]
                else:
                    desc_tag = soup.find("meta", attrs={"name": "description"})
                    if desc_tag and desc_tag.get("content"):
                        card["description"] = desc_tag["content"]
                if len(card["description"]) > 300:
                    card["description"] = card["description"][:297] + "..."

            # ===== IMAGE FETCH & UPLOAD (optional) =====
            og_img = soup.find("meta", property="og:image")
            if og_img and og_img.get("content"):
                img_url = urljoin(url, og_img["content"])
                time.sleep(0.5)
                img_resp = self.session.get(img_url, timeout=15)
                img_resp.raise_for_status()
                content_type = img_resp.headers.get("Content-Type", "image/jpeg")
                if len(img_resp.content) <= 1_000_000:
                    self.logger.debug("Uploading image blob from %s", img_url)
                    blob_resp = self.session.post(
                        f"{self.service}/xrpc/com.atproto.repo.uploadBlob",
                        headers={
                            "Content-Type": content_type,
                            "Authorization": f"Bearer {self.access_jwt}",
                        },
                        data=img_resp.content,
                    )
                    blob_resp.raise_for_status()
                    blob_json = blob_resp.json()
                    if "blob" in blob_json:
                        card["thumb"] = blob_json["blob"]
                        self.logger.info("Image uploaded successfully")
                    else:
                        self.logger.warning("Unexpected uploadBlob response: %s", blob_json)

            self.logger.info("Created embed with title: %s", card["title"])

        except requests.RequestException as exc:
            self.logger.error("Error fetching URL preview: %s", exc)
            return self.create_simple_embed(url)

        return {"$type": "app.bsky.embed.external", "external": card}

    def create_facets(self, text, link):
        """
        Create link facets so Bluesky clients render the link as a hyperlink.

        Args:
            text (str): The post text containing the link.
            link (str): The exact link substring to facet.

        Returns:
            list: A list of facet objects for the Bluesky post record.
        """
        facets = []
        for match in re.finditer(re.escape(link), text):
            byte_start = len(text[: match.start()].encode("utf-8"))
            byte_end = byte_start + len(link.encode("utf-8"))
            facets.append({
                "index": {"byteStart": byte_start, "byteEnd": byte_end},
                "features": [{
                    "$type": "app.bsky.richtext.facet#link",
                    "uri": link,
                }],
            })
        return facets

    def truncate_text(self, text, max_length=None):
        """
        Truncate text to fit within Bluesky’s maximum post length,
        appending an ellipsis if truncated.

        Args:
            text (str): Original text.
            max_length (int): Override max length (default Bluesky limit).

        Returns:
            str: Possibly truncated text.
        """
        max_len = max_length or self.MAX_POST_LENGTH
        if len(text) <= max_len:
            return text
        return text[: max_len - 3] + "..."

    def post_without_preview(self, text, link):
        """
        Publish a feed post that simply appends the link,
        without creating an embed preview.

        Args:
            text (str): Main post text.
            link (str): URL to append.

        Returns:
            dict: The server JSON response.
        """
        if not self.access_jwt or not self.did:
            self.create_session()

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        # Reserve characters for the link itself and newline
        link_len = len(link) + 1
        available = self.MAX_POST_LENGTH - link_len
        if available <= 0:
            body = self.truncate_text(text, self.MAX_POST_LENGTH)
        else:
            body = f"{self.truncate_text(text, available)}\n{link}"

        self.logger.debug("Final post text length: %d", len(body))
        facets = self.create_facets(body, link)

        post_record = {
            "$type": "app.bsky.feed.post",
            "text": body,
            "createdAt": now,
        }
        if facets:
            post_record["facets"] = facets

        self.logger.info("Posting without preview...")
        resp = requests.post(
            f"{self.service}/xrpc/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {self.access_jwt}"},
            json={"repo": self.did, "collection": "app.bsky.feed.post", "record": post_record},
        )
        if not resp.ok:
            self.logger.error("Error posting without preview: %s %s", resp.status_code, resp.text)
            resp.raise_for_status()
        return resp.json()

    def post_feed(self, description, link, ai_comment=None, title=None, more_info=False):
        """
        Publish a feed post with a link‐preview embed.

        Args:
            description (str): Body text or summary.
            link (str): URL to preview.
            ai_comment (str, optional): If provided, use as the only text.
            title (str, optional): Title to prepend if ai_comment is absent.
            more_info (bool): If True, include full description metadata in embed.

        Returns:
            dict: The server JSON response.
        """
        if not self.access_jwt or not self.did:
            self.create_session()

        # Build the post text
        if ai_comment:
            text_body = ai_comment
        else:
            parts = []
            if title:
                parts.append(title)
            if description:
                parts.append(description)
            text_body = "\n".join(parts)

        truncated = self.truncate_text(text_body)
        self.logger.debug("Truncated post text length: %d", len(truncated))

        # Fetch embed and create facets
        embed = self.fetch_embed_url_card(link, more_info=more_info)
        facets = self.create_facets(truncated, link)

        post_record = {
            "$type": "app.bsky.feed.post",
            "text": truncated,
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "embed": embed,
        }
        if facets:
            post_record["facets"] = facets

        self.logger.info("Posting feed with preview...")
        self.logger.debug("Post payload (first 500 chars): %s",
                          json.dumps(post_record, indent=2, default=str)[:500] + "...")

        resp = requests.post(
            f"{self.service}/xrpc/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {self.access_jwt}"},
            json={"repo": self.did, "collection": "app.bsky.feed.post", "record": post_record},
        )
        if not resp.ok:
            self.logger.error("Error posting feed: %s %s", resp.status_code, resp.text)
            resp.raise_for_status()
        return resp.json()


def main():
    """
    Command‑line interface for BlueskyPoster.

    Examples:
      # Show version
      python bluesky_poster.py --version

      # Post feed with link preview
      python bluesky_poster.py \
        --handle alice.bsky.social \
        --password YOUR_APP_PASSWORD \
        --link https://example.com \
        --description "Summary text" \
        --title "My Article" \
        --more-info

      # Same, with debug logs
      python bluesky_poster.py ... --debug
    """
    parser = argparse.ArgumentParser(
        description="Post a feed entry to Bluesky (with optional link preview)."
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program version and exit."
    )
    parser.add_argument(
        "-u", "--handle",
        required=True,
        help="Bluesky handle (e.g. 'alice.bsky.social')."
    )
    parser.add_argument(
        "-p", "--password",
        required=True,
        help="Bluesky application password."
    )
    parser.add_argument(
        "-s", "--service",
        default="https://bsky.social",
        help="Bluesky service URL (default: https://bsky.social)."
    )
    parser.add_argument(
        "-l", "--link",
        required=True,
        help="URL to include (and preview) in the post."
    )
    parser.add_argument(
        "-d", "--description",
        required=True,
        help="Description or body text for the post."
    )
    parser.add_argument(
        "-t", "--title",
        help="Optional title to prepend when no AI comment is provided."
    )
    parser.add_argument(
        "--ai-comment",
        dest="ai_comment",
        help="If set, use this text as the sole post content."
    )
    parser.add_argument(
        "--more-info",
        action="store_true",
        help="Include full description metadata in the preview card."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable DEBUG-level logging (default is INFO)."
    )

    args = parser.parse_args()

    # Configure root logger level
    log_level = logging.DEBUG if args.debug else logging.INFO
    logger.setLevel(log_level)

    # Instantiate poster
    poster = BlueskyPoster(
        handle=args.handle,
        app_password=args.password,
        service=args.service,
    )

    # Attempt to post with preview first; fallback to no-preview on error
    try:
        result = poster.post_feed(
            description=args.description,
            link=args.link,
            ai_comment=args.ai_comment,
            title=args.title,
            more_info=args.more_info,
        )
        logger.info("Posted feed with preview successfully.")
        logger.debug("Server response: %s", json.dumps(result, indent=2))
    except Exception as exc:
        logger.error("Failed to post with preview: %s", exc)
        logger.info("Retrying to post without preview...")
        try:
            result = poster.post_without_preview(args.description, args.link)
            logger.info("Posted feed without preview successfully.")
            logger.debug("Server response: %s", json.dumps(result, indent=2))
        except Exception as exc2:
            logger.error("All posting attempts failed: %s", exc2)


if __name__ == "__main__":
    main()