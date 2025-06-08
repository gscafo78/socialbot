#!/usr/bin/env python3
"""
gpt_model_price_extractor.py  (version 0.0.2)

Scrape docsbot.ai to extract input/output token prices for one or more GPT models.
‘gpt-4’, ‘gpt-4.1-nano’ and ‘gpt-4-1-nano’ now all map to the same nano‑variant page.

Usage:
    # Show version and exit:
    python gpt_model_price_extractor.py --version

    # Enable debug-level logging:
    python gpt_model_price_extractor.py --debug gpt-4

    # Fetch prices for multiple models in parallel:
    python gpt_model_price_extractor.py --workers 8 gpt-3.5-turbo gpt-4 gpt-4.1-nano

Requirements:
    - requests
    - beautifulsoup4
"""

import argparse
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Union

import requests
from bs4 import BeautifulSoup, Tag

__version__ = "0.0.2"


class GPTModelPriceExtractor:
    """
    Extracts input and output prices for a given GPT model from docsbot.ai.
    Maps base 'gpt-4' to the 'gpt-4-1-nano' page so that you always get nano‑variant prices.

    Args:
        model: The model name (e.g. 'gpt-4', 'gpt-4.1-nano', 'gpt-4-1-nano').
        logger: A configured `logging.Logger` instance for internal logging.
    """

    REQUEST_TIMEOUT = 10  # seconds

    # Any future aliases can be added here
    _ALIASES = {
        "gpt-4.1-nano":    "gpt-4-1-nano",
        "gpt-4-1-mini":    "gpt-4-1-mini",
    }

    def __init__(self, model: str, logger: logging.Logger) -> None:
        self.logger = logger

        # Normalize dotted names → dashed and lowercase
        norm = model.replace(".", "-").lower()

        # Apply aliasing so that 'gpt-4' and variants all point to the nano page
        self.model = self._ALIASES.get(norm, norm)
        self.url = f"https://docsbot.ai/models/{self.model}"

        self.logger.debug("Extractor init: raw_model=%r → normalized_model=%r → url=%s",
                          model, self.model, self.url)

    def _extract_number(self, elem: Optional[Tag]) -> Optional[float]:
        """
        Parse a BeautifulSoup Tag containing a price like '$0.003' into float.
        Returns None on parse failure or if elem is None.
        """
        if not elem:
            return None
        txt = elem.get_text(strip=True).replace("$", "").replace(",", ".")
        try:
            val = float(txt)
            self.logger.debug("Parsed price text %r → %f", txt, val)
            return val
        except ValueError:
            self.logger.warning("Unable to parse price text %r", txt)
            return None

    def get_prices(self) -> Dict[str, Union[float, None, str]]:
        """
        Fetch the model page and extract input/output token prices.

        Returns:
            {'input': float|None, 'output': float|None} on success,
            or {'error': <message>} on failure.
        """
        try:
            resp = requests.get(self.url, timeout=self.REQUEST_TIMEOUT)
            resp.raise_for_status()
            self.logger.info("Fetched page for %s (HTTP %d)", self.model, resp.status_code)
        except Exception as e:
            err = f"Error fetching {self.url}: {e}"
            self.logger.error(err)
            return {"error": err}

        soup = BeautifulSoup(resp.content, "html.parser")

        # The CSS selectors below reflect docsbot.ai’s table layout for prices
        input_sel = (
            "div.mt-8.flow-root div > div > table > tbody "
            "> tr:nth-child(1) > td.px-3.py-4.text-center "
            "> div.text-lg.font-bold.text-gray-900"
        )
        output_sel = (
            "div.mt-8.flow-root div > div > table > tbody "
            "> tr:nth-child(2) > td.px-3.py-4.text-center "
            "> div.text-lg.font-bold.text-gray-900"
        )

        input_div = soup.select_one(input_sel)
        output_div = soup.select_one(output_sel)

        input_price = self._extract_number(input_div)
        output_price = self._extract_number(output_div)

        return {"input": input_price, "output": output_price}


def main() -> None:
    """
    Parse CLI args, configure logging, and fetch prices for specified model(s).
    """
    parser = argparse.ArgumentParser(
        description="Scrape docsbot.ai for GPT model input/output token prices."
    )
    parser.add_argument(
        "models",
        nargs="+",
        help="GPT model names (e.g. 'gpt-4', 'gpt-4.1-nano', 'gpt-4-1-nano')."
    )
    parser.add_argument(
        "-w", "--workers",
        type=int,
        default=4,
        help="Parallel worker threads (default: 4)."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug-level logging."
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"%(prog)s v{__version__}",
        help="Show program version and exit."
    )
    args = parser.parse_args()

    # Configure root logger
    lvl = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=lvl, format="%(asctime)s [%(levelname)s] %(message)s")
    logger = logging.getLogger("gpt_price_extractor")

    results: Dict[str, Dict[str, Union[float, None, str]]] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(GPTModelPriceExtractor(m, logger).get_prices): m
            for m in args.models
        }
        for fut in as_completed(futures):
            model = futures[fut]
            try:
                results[model] = fut.result()
            except Exception as exc:
                logger.error("Unhandled error for %s: %s", model, exc)
                results[model] = {"error": str(exc)}

    # Print results in the order requested
    print("\n=== GPT Model Prices ===")
    for model in args.models:
        data = results.get(model, {})
        if "error" in data:
            print(f"{model:<20} ERROR → {data['error']}")
        else:
            inp = data.get("input")
            out = data.get("output")
            print(f"{model:<20} input=${inp!s:<6}  output=${out!s}")

    # Exit non-zero if any errors occurred
    if any("error" in v for v in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()