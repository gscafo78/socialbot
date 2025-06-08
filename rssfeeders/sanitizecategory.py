#!/usr/bin/env python3
"""
category_sanitizer.py  (version 1.0.0)

Clean up category names and generate corresponding hashtags.

Usage:
    # Show version
    python category_sanitizer.py --version

    # Enable debug logging
    python category_sanitizer.py --debug Technology Science "Cyber Security"

    # Limit to at most 3 tags (randomly sampled)
    python category_sanitizer.py --maxtag 3 Technology Science "Cyber Security"

Requirements:
    Only Python standard library (no external packages needed).
"""

import argparse
import logging
import random
import sys
from typing import List, Optional, Union

__version__ = "1.0.0"


class Category:
    """
    Sanitize category names and generate hashtags.

    Args:
        categories: A single category string or a list of category strings.
        logger: Optional logging.Logger instance for debug/info output.

    Attributes:
        sanitized: The sanitized category or list of categories (after calling sanitize()).
        hashtags: The list of hashtags generated (after calling hashtag()).
    """

    def __init__(
        self,
        categories: Union[str, List[str]],
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.original = categories
        self.sanitized: Optional[Union[str, List[str]]] = None
        self.hashtags: Optional[List[str]] = None
        self.logger = logger or logging.getLogger(__name__)

    def sanitize(self, maxtag: Optional[int] = None) -> None:
        """
        Clean and deduplicate the category or list of categories.

        - Converts to lowercase and removes spaces.
        - Skips entries with more than 3 words.
        - Skips entries containing apostrophes.
        - Skips the category 'articoli'.
        - Removes duplicates.
        - If maxtag is set and the sanitized list exceeds it,
          randomly samples maxtag items.

        Args:
            maxtag: Maximum number of tags to keep (random sample) if sanitized is a list.
        """
        result: Optional[Union[str, List[str]]]

        if isinstance(self.original, list):
            cleaned_list: List[str] = []
            for item in self.original:
                if not isinstance(item, str):
                    continue
                words = item.split()
                if len(words) > 3:
                    continue
                cleaned = item.replace(" ", "").lower()
                if "'" in cleaned or cleaned == "articoli":
                    continue
                if cleaned not in cleaned_list:
                    cleaned_list.append(cleaned)
            result = cleaned_list

        elif isinstance(self.original, str):
            cleaned = self.original.replace(" ", "").lower()
            result = None if cleaned == "articoli" else cleaned

        else:
            result = None

        # If result is a list and maxtag is specified, sample that many tags
        if maxtag is not None and isinstance(result, list) and len(result) > maxtag:
            try:
                result = random.sample(result, maxtag)
            except ValueError as e:
                self.logger.error("Error sampling tags: %s", e)

        self.sanitized = result
        self.logger.debug("Sanitized categories → %s", self.sanitized)

    def hashtag(self) -> Optional[List[str]]:
        """
        Generate hashtags from the sanitized categories.

        Returns:
            A list of hashtags (each prefixed with '#'), or None if sanitize() wasn't run or result was None.
        """
        if self.sanitized is None:
            self.logger.warning("sanitize() must be called (and yield non-None) before hashtag().")
            return None

        if isinstance(self.sanitized, list):
            tags = [f"#{cat}" for cat in self.sanitized]
        else:
            tags = [f"#{self.sanitized}"]

        self.hashtags = tags
        self.logger.debug("Generated hashtags → %s", tags)
        return tags


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sanitize category names and generate hashtags."
    )
    parser.add_argument(
        "categories",
        nargs="+",
        help="One or more category names (e.g. 'Cyber Security', 'Tech').",
    )
    parser.add_argument(
        "--maxtag",
        type=int,
        help="Maximum number of tags to keep (randomly sampled) if multiple categories are provided.",
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
    logger = logging.getLogger("category_sanitizer")

    # Instantiate and run
    cat = Category(categories=args.categories, logger=logger)
    cat.sanitize(maxtag=args.maxtag)
    tags = cat.hashtag()

    # Handle the case of no valid categories
    if cat.sanitized is None or tags is None:
        logger.error("No valid categories after sanitization.")
        sys.exit(1)

    # Output results
    print("Sanitized categories:", cat.sanitized)
    print("Hashtags:", tags)


if __name__ == "__main__":
    main()