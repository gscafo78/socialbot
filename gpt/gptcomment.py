#!/usr/bin/env python3
"""
article_commentator.py  (version 0.0.2)

Generate a colloquial summary and personal comment for an online article
using OpenAI GPT models. If no model is supplied, selects the cheapest GPT
model automatically.

Usage:
    # Show version:
    python article_commentator.py --version

    # Enable debug-level logging:
    python article_commentator.py --debug --link URL --api-key YOUR_API_KEY

    # Manually select base url, model, set max chars and language:
    python article_commentator.py \
      --link URL \
      --base_url your API base url endpoint \
      --api-key YOUR_API_KEY \
      --model gpt-4.1-nano \
      --max-chars 200 \
      --language it
      

Requirements:
    pip install openai requests beautifulsoup4
"""

import argparse
import logging
import os
import sys
from typing import Optional

import requests
from bs4 import BeautifulSoup
from openai import OpenAI

# Ensure getmodel.py (with GPTModelSelector) is importable
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from get_ai_model import Model

__version__ = "0.0.4"


class ArticleCommentator:
    """
    Generate a short, colloquial summary + personal comment for an article
    URL using the OpenAI API.

    Args:
        link: URL of the target article.
        base_url: Optional custom base URL for the OpenAI API. If None, uses the default OpenAI endpoint.
        api_key: OpenAI API key.
        logger: A configured `logging.Logger` instance.
        model: Optional GPT model name; if None, picks the cheapest GPT model.
        max_chars: Maximum length of the generated comment in characters.
        language: 'en' for English or 'it' for Italian.

    Methods:
        extract_text() -> str: Retrieves and concatenates all <p> text from the article.
        generate_comment() -> str: Calls OpenAI with a system+user prompt and returns the answer.
    """

    def __init__(
        self,
        link: str,
        api_key: str,
        logger: logging.Logger,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        max_chars: int = 299,
        language: str = "en",
    ) -> None:
        if not link:
            raise ValueError("Article URL (--link) must be provided.")
        if not api_key:
            raise ValueError("OpenAI API key (--api-key or OPENAI_API_KEY) is required.")

        self.link = link
        self.api_key = api_key
        self.logger = logger
        self.max_chars = max_chars
        self.language = language.lower()
        self.base_url = base_url or "https://api.openai.com/v1"

        # Determine which GPT model to use
        if model:
            self.model = model
            self.logger.info("Using user‑specified model: %s", self.model)
        else:
            raw = Model.fetch_raw_models(logger)
            models = Model.process_models(raw, logger)
            cheapest_model = Model.find_cheapest_model(models, logger, filter_str="openai")
            self.model = cheapest_model.id
            gpt_in_price = cheapest_model.prompt_price
            gpt_out_price = cheapest_model.completion_price
            self.logger.info("Auto‑selected cheapest GPT model: %s", self.model)

        # Initialize OpenAI client
        self.client = OpenAI(base_url=self.base_url,
                             api_key=self.api_key)

    def extract_text(self) -> str:
        """
        Fetches the article page and concatenates all <p> tags into one text blob.

        Returns:
            The article text, or an empty string on failure.
        """
        try:
            resp = requests.get(self.link, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            self.logger.error("Failed to fetch article at %s: %s", self.link, e)
            return ""

        soup = BeautifulSoup(resp.content, "html.parser")
        paragraphs = soup.find_all("p")
        text = " ".join(p.get_text(strip=True) for p in paragraphs)
        self.logger.debug("Extracted %d paragraphs, total %d chars", len(paragraphs), len(text))
        return text

    def generate_comment(self) -> str:
        """
        Builds and sends a chat completion request to OpenAI to summarize
        and comment on the article in the requested language.

        Returns:
            The GPT‑generated comment (possibly truncated), or an empty string on failure.
        """
        article_text = self.extract_text()
        if not article_text:
            self.logger.error("No article text extracted; aborting comment generation.")
            return ""

        if self.language == "it":
            lang_name = "Italian"
        elif self.language == "en":
            lang_name = "English"
        else:
            raise ValueError("Language must be 'en' or 'it'")

        prompt = (
            f"Read and summarize the following article in a colloquial, natural way "
            f"in {lang_name}, then add a personal comment as if you had read it:\n\n"
            f"{article_text}"
        )
        system_msg = (
            f"You are an expert article commentator. Summarize and comment in a "
            f"colloquial style without advertising. "
            f"Reply in {lang_name}, max {self.max_chars} characters."
        )

        self.logger.debug("Sending chat completion: model=%s, max_chars=%d", self.model, self.max_chars)
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt},
                ],
            )
            content = response.choices[0].message.content.strip()
            self.logger.info("Received response of %d chars", len(content))
            return content[: self.max_chars]
        except Exception as e:
            self.logger.error("OpenAI API error: %s", e)
            return ""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a colloquial summary+comment for an article via OpenAI GPT."
    )
    parser.add_argument(
        "--link",
        required=True,
        help="URL of the article to process",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("OPENAI_API_KEY"),
        help="OpenAI API key (or set OPENAI_API_KEY environment variable)",
    )
    parser.add_argument(
        "--model",
        help="GPT model to use (e.g. gpt-4.1-nano). If omitted, selects cheapest GPT model.",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=160,
        help="Maximum characters for the generated comment (default: 160)",
    )
    parser.add_argument(
        "--language",
        choices=("en", "it"),
        default="en",
        help="Language for the comment: 'en' or 'it' (default: en)",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Custom base URL for the OpenAI API (optional). If not provided, uses the default endpoint.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug-level logging",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s v{__version__}",
        help="Show program version and exit",
    )
    args = parser.parse_args()

    # Configure root logger
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(message)s")
    logger = logging.getLogger("article_commentator")

    commentator = ArticleCommentator(
        link=args.link,
        api_key=args.api_key or "",
        logger=logger,
        base_url=args.base_url,
        model=args.model,
        max_chars=args.max_chars,
        language=args.language,
    )
    comment = commentator.generate_comment()
    if comment:
        print(comment)
    else:
        logger.error("No comment generated.")
        sys.exit(1)


if __name__ == "__main__":
    main()