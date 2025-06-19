#!/usr/bin/env python3
"""
category_sanitizer.py (version 1.0.0)

Clean and normalize category names and generate corresponding hashtags.

How to use:
    # Show version and exit
    python category_sanitizer.py --version

    # Enable debug logging (default INFO)
    python category_sanitizer.py --debug Technology Science "Cyber Security"

    # Limit to at most 3 tags (randomly sampled)
    python category_sanitizer.py --maxtag 3 Technology Science "Cyber Security"

Description:
- Accepts one or more category strings from the command line.
- Removes spaces and converts to lowercase.
- Filters out entries that:
    • Consist of more than three words.
    • Contain apostrophes.
    • Equal the word 'articoli' (Italian for 'articles').
- Deduplicates the cleaned categories.
- Optionally samples a maximum number of tags if --maxtag is specified.
- Converts sanitized categories into hashtags (prefix '#').

Requirements:
- Only the Python standard library is used (no external dependencies).
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

    Attributes:
        original:   The input category or list of categories.
        sanitized:  The cleaned category name(s) after calling sanitize().
        hashtags:   The list of hashtags after calling hashtag().
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

        - Converts to lowercase and removes all spaces.
        - Skips entries with more than 3 words.
        - Skips entries containing apostrophes.
        - Skips the category 'articoli'.
        - Removes duplicates while preserving order.
        - If maxtag is set and the result is a list longer than maxtag,
          randomly samples maxtag items.

        Args:
            maxtag: Maximum number of tags to keep (random sampling) if multiple categories.
        """
        result: Optional[Union[str, List[str]]]

        if isinstance(self.original, list):
            cleaned_list: List[str] = []
            for item in self.original:
                if not isinstance(item, str):
                    continue
                words = item.split()
                # Skip entries with more than 3 words
                if len(words) > 3:
                    continue
                cleaned = item.replace(" ", "").lower()
                # Skip entries with apostrophes or the literal 'articoli'
                if "'" in cleaned or cleaned == "articoli":
                    continue
                # Deduplicate
                if cleaned not in cleaned_list:
                    cleaned_list.append(cleaned)
            result = cleaned_list

        elif isinstance(self.original, str):
            cleaned = self.original.replace(" ", "").lower()
            # Single string: skip if equal to 'articoli'
            result = None if cleaned == "articoli" else cleaned

        else:
            result = None

        # If sampling is requested and we have a list longer than maxtag
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
            A list of hashtags (each prefixed with '#'), or None if sanitize()
            was not called or yielded None.
        """
        if self.sanitized is None:
            self.logger.warning(
                "sanitize() must be called (and produce non-None) before hashtag()."
            )
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
        help="Maximum number of tags to keep (randomly sampled) if multiple categories.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug-level logging (default INFO).",
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
    logging.basicConfig(
        level=level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    logger = logging.getLogger("category_sanitizer")

    # Sanitize and generate hashtags
    category_processor = Category(categories=args.categories, logger=logger)
    category_processor.sanitize(maxtag=args.maxtag)
    tags = category_processor.hashtag()

    # If no valid categories remain, exit with error
    if category_processor.sanitized is None or tags is None:
        logger.error("No valid categories after sanitization.")
        sys.exit(1)

    # Print results
    print("Sanitized categories:", category_processor.sanitized)
    print("Hashtags:", tags)


if __name__ == "__main__":
    main()