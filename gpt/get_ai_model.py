#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
openrouter_models.py

Object‐oriented script to fetch the list of models from the OpenRouter API
and display each model’s ID along with its prompt & completion pricing.

Usage examples:
  $ python openrouter_models.py
  $ python openrouter_models.py --debug
  $ python openrouter_models.py --version
"""
import argparse
import logging
import sys
from typing import List, Optional

import requests

__version__ = "0.0.1"


class Model:
    """
    Represents an OpenRouter model, holding its ID and pricing
    for both prompts and completions.
    """

    def __init__(
        self,
        model_id: str,
        prompt_price: Optional[float],
        completion_price: Optional[float],
    ) -> None:
        self.id = model_id
        # Convert to float if possible, else None
        try:
            self.prompt_price = float(prompt_price) if prompt_price is not None else None
        except (ValueError, TypeError):
            self.prompt_price = None
        try:
            self.completion_price = float(completion_price) if completion_price is not None else None
        except (ValueError, TypeError):
            self.completion_price = None

    def __str__(self) -> str:
        """
        String representation of the model, showing its ID and pricing.
        """
        return (
            f"{self.id}: "
            f"prompt={self.prompt_price}, "
            f"completion={self.completion_price}"
        )

    @staticmethod
    def fetch_raw_models(logger: logging.Logger) -> List[dict]:
        """
        Download the raw list of models from the OpenRouter API.

        Returns:
            A list of raw model dictionaries (empty on failure).
        """
        API_URL = "https://openrouter.ai/api/v1/models"
        logger.info("Fetching models from %s", API_URL)
        try:
            response = requests.get(API_URL, timeout=10)
            response.raise_for_status()
            data = response.json()
            logger.debug("Raw JSON data received: %s", data)
            return data.get("data", [])
        except requests.RequestException as exc:
            logger.warning("Failed to fetch models: %s", exc)
            return []

    @staticmethod
    def process_models(
        raw_models: List[dict], logger: logging.Logger
    ) -> List["Model"]:
        """
        Convert the list of raw model dicts into Model instances,
        extracting only the 'id', 'pricing.prompt', and 'pricing.completion'.

        Logs a warning if any pricing information is missing.
        """
        processed: List[Model] = []
        for entry in raw_models:
            model_id = entry.get("id", "<unknown>")
            pricing = entry.get("pricing", {})
            prompt_price = pricing.get("prompt")
            completion_price = pricing.get("completion")

            if prompt_price is None or completion_price is None:
                logger.warning(
                    "Model %s missing prompt/completion pricing", model_id
                )

            model = Model(model_id, prompt_price, completion_price)
            logger.debug("Constructed Model object: %s", model)
            processed.append(model)

        return processed

    
    @staticmethod
    def find_cheapest_model(
        models: List["Model"],
        logger: logging.Logger,
        filter_str: Optional[str] = None
    ) -> Optional["Model"]:
        """
        Identify and return the model with the lowest combined prompt+completion price,
        ensuring the total cost is not negative.

        Optionally filter models by a substring in their ID (case-insensitive).

        Args:
            models: List of Model objects.
            logger: Logger instance.
            filter_str: Optional substring to filter model IDs (case-insensitive).

        Returns:
            The cheapest Model object matching the filter (if any), else None.
        """
        if not models:
            logger.warning("No models available to determine the cheapest one.")
            return None

        # Apply filter if provided
        if filter_str:
            filtered_models = [m for m in models if filter_str.lower() in m.id.lower()]
            logger.info("Filtering models with substring '%s': %d found", filter_str, len(filtered_models))
        else:
            filtered_models = models

        cheapest: Optional[Model] = None
        min_cost = float("inf")

        for m in filtered_models:
            if m.prompt_price is None or m.completion_price is None:
                continue
            total_cost = m.prompt_price + m.completion_price
            logger.debug("Model %s total cost = %s", m.id, total_cost)
            # Skip if total_cost is negative
            if total_cost < 0:
                logger.debug("Model %s skipped because total cost is negative (%s)", m.id, total_cost)
                continue
            if total_cost < min_cost:
                min_cost = total_cost
                cheapest = m

        if cheapest is None:
            logger.warning(
                "Unable to determine cheapest model: missing complete pricing info or all costs negative."
            )
        else:
            logger.info(
                "Cheapest model selected: %s (prompt=%s, completion=%s)",
                cheapest.id,
                cheapest.prompt_price,
                cheapest.completion_price,
            )
        return cheapest


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """
    Define and parse command‐line arguments.

    Args:
        argv: Optional list of arguments (for testing); defaults to sys.argv.

    Returns:
        Namespace with parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Fetch models from the OpenRouter API and display "
            "each model’s ID and pricing."
        )
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="enable debug logging",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="show program’s version number and exit",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main entry point of the script. Configures logging, fetches
    and processes models, and prints them to stdout.

    Args:
        argv: Optional list of arguments (for testing).

    Returns:
        Exit status code (0 on success, non‐zero on failure).
    """
    args = parse_args(argv)

    # Configure logging based on --debug flag
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("openrouter_models")

    # Download raw model data and process into Model objects
    raw = Model.fetch_raw_models(logger)
    models = Model.process_models(raw, logger)

    if not models:
        logger.info("No models to display.")
        return 1

    # Print out each model
    for model in models:
        print(model)

    # Example in main() after processing models:
    cheapest = Model.find_cheapest_model(models, logger, filter_str="openai")
    if cheapest:
        print("Cheapest model:", cheapest)

    return 0


if __name__ == "__main__":
    sys.exit(main())