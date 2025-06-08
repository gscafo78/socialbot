#!/usr/bin/env python3

"""
gpt_model_selector.py  (version 0.0.2)

Fetch available OpenAI models, retrieve their usage prices, and identify the
cheapest GPT model by input price.

Usage:
    # Show version:
    python gpt_model_selector.py --version

    # Enable debug-level logging:
    python gpt_model_selector.py --debug

    # Or pass your API key on the command line:
    python gpt_model_selector.py --api-key YOUR_OPENAI_API_KEY

    # Or set the environment variable OPENAI_API_KEY:
    export OPENAI_API_KEY=YOUR_OPENAI_API_KEY
    python gpt_model_selector.py
"""

import argparse
import logging
import os
import sys
import requests
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional
from gpt.gptmodelprice import GPTModelPriceExtractor



__version__ = "0.0.2"


class GPTModelSelector:
    """
    A helper class to fetch OpenAI models, retrieve their prices, and determine
    the cheapest GPT model based on input token pricing.

    The caller must provide a configured `logging.Logger` instance so that
    logging verbosity can be controlled externally.
    """

    MODELS_URL = "https://api.openai.com/v1/models"
    REQUEST_TIMEOUT = 10  # seconds

    def __init__(self, api_key: str, logger: logging.Logger) -> None:
        """
        Initialize the selector.

        Args:
            api_key: A valid OpenAI API key.
            logger: A configured Logger instance (INFO/DEBUG/etc.).
        """
        if not api_key:
            raise ValueError("An OpenAI API key must be provided.")
        self.api_key = api_key
        self.headers = {"Authorization": f"Bearer {self.api_key}"}
        self.logger = logger

    def fetch_models(self) -> List[Dict[str, Any]]:
        """
        Fetch the list of available OpenAI models.

        Returns:
            A list of model metadata dicts, or an empty list on error.
        """
        try:
            resp = requests.get(
                self.MODELS_URL, headers=self.headers, timeout=self.REQUEST_TIMEOUT
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
            self.logger.info("Successfully fetched %d models.", len(data))
            return data if isinstance(data, list) else []
        except Exception as e:
            self.logger.error("Error fetching models: %s", e)
            return []

    def _fetch_price_for_model(self, model_id: str) -> Dict[str, Any]:
        """
        Internal helper: get price info for a single model via GPTModelPriceExtractor.

        Returns:
            A dict containing pricing info, or an 'error' key on failure.
        """
        try:
            extractor = GPTModelPriceExtractor(model_id, self.logger)
            prices = extractor.get_prices()
            self.logger.debug("Prices for %s: %s", model_id, prices)
            return prices
        except Exception as e:
            self.logger.warning("Failed to fetch prices for %s: %s", model_id, e)
            return {"error": str(e)}

    def get_models_and_prices(self, max_workers: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieve all models and their corresponding price data, fetching in parallel.

        Args:
            max_workers: Number of threads to use for parallel price fetching.

        Returns:
            A list of dicts, each containing:
                - 'id': the model identifier (str)
                - 'prices': dict with pricing or error info
        """
        models = self.fetch_models()
        result: List[Dict[str, Any]] = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_model = {
                executor.submit(self._fetch_price_for_model, m.get("id")): m.get("id")
                for m in models
                if m.get("id")
            }
            for future in as_completed(future_to_model):
                model_id = future_to_model[future]
                prices = future.result()
                result.append({"id": model_id, "prices": prices})

        self.logger.info("Fetched pricing for %d models.", len(result))
        return result

    def get_cheapest_gpt_model(self) -> Optional[str]:
        """
        Identify the GPT model (model_id starts with 'gpt') with the lowest input price.

        Returns:
            The model_id of the cheapest GPT model, or None if none found/parsable.
        """
        models_and_prices = self.get_models_and_prices()
        cheapest_model: Optional[str] = None
        cheapest_price = float("inf")

        for entry in models_and_prices:
            model_id = entry["id"]
            if not model_id.lower().startswith("gpt"):
                continue

            prices = entry.get("prices", {})
            input_price = prices.get("input")
            try:
                price_val = float(input_price)
            except (TypeError, ValueError):
                self.logger.debug(
                    "Skipping %s due to invalid input price: %s", model_id, input_price
                )
                continue

            if price_val < cheapest_price:
                cheapest_price = price_val
                cheapest_model = model_id

        if cheapest_model:
            self.logger.info(
                "Cheapest GPT model: %s @ %f per input token",
                cheapest_model,
                cheapest_price,
            )
        else:
            self.logger.info("No valid GPT model pricing found.")

        return cheapest_model

    def print_all_models_and_cheapest(self) -> None:
        """
        Print all models with their prices and highlight the cheapest GPT model.
        """
        models_and_prices = self.get_models_and_prices()
        print("\n=== All Models and Prices ===")
        for entry in models_and_prices:
            print(f"ID: {entry['id']:<20} Prices: {entry['prices']}")
        cheapest = self.get_cheapest_gpt_model()
        print(f"\nCheapest GPT model by input price: {cheapest}")


def main() -> None:
    """
    Parse command-line arguments, configure logging, and run the selector.
    """
    parser = argparse.ArgumentParser(
        description="Fetch OpenAI models and identify the cheapest GPT model by input price."
    )
    parser.add_argument(
        "--api-key",
        help="OpenAI API key (or set OPENAI_API_KEY environment variable)",
        default=os.getenv("OPENAI_API_KEY"),
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

    if not args.api_key:
        parser.error("An OpenAI API key must be provided via --api-key or OPENAI_API_KEY.")

    # Configure root logger level and formatting
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s [%(levelname)s] %(message)s"
    )

    # Create a named logger and pass it into our selector
    logger = logging.getLogger("gpt_model_selector")

    selector = GPTModelSelector(api_key=args.api_key, logger=logger)
    selector.print_all_models_and_cheapest()


if __name__ == "__main__":
    main()