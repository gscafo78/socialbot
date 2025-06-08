#!/usr/bin/env python3
"""
json_reader.py

Utility class for reading and writing JSON files with built-in logging.
Provides easy methods to load, query, update, and persist JSON data,
as well as to extract “social bot” credentials from structured JSON.

This script can also be used as a command-line tool:

    $ python json_reader.py --file settings.json [--create] [--log-level DEBUG]
    $ python json_reader.py --version
"""

import argparse
import json
import os
import logging


# ------------------------------------------------------------------------------
# Module version
# ------------------------------------------------------------------------------
__version__ = "1.0.0"


# ------------------------------------------------------------------------------
# Module‑level logging configuration
# ------------------------------------------------------------------------------
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


class JSONReader:
    """
    Utility class for reading and writing JSON files.

    This class wraps JSON file operations (load/read, write/update) and
    provides helper methods to fetch nested “social” bot credentials.

    Example:
        reader = JSONReader("config.json", create=True)
        data = reader.get_data()
        token, chat_id, _, mute = reader.get_social_values("telegram", "mybot")
        reader.set_data(updated_data)
    """

    def __init__(self, file_path, create=False, logger=None, log_level="INFO"):
        """
        Initialize the JSONReader with the path to the JSON file.

        Args:
            file_path (str): Path to the JSON file.
            create (bool): If True, create the file with an empty list if it does not exist.
            logger (logging.Logger, optional): External logger instance to use.
            log_level (str): Logging level name if logger is not provided (default "INFO").
        """
        self.file_path = file_path
        self.data = None

        # Use provided logger or create a new one for this class
        if logger is not None:
            self.logger = logger
        else:
            self.logger = logging.getLogger(self.__class__.__name__)
            level = getattr(logging, log_level.upper(), logging.INFO)
            self.logger.setLevel(level)

        self.logger.debug(f"Initializing JSONReader for '{self.file_path}', create={create}")
        self._read_file(create)

    def _read_file(self, create=False):
        """
        Private helper: reads the JSON file into self.data.
        If create=True and file is missing, creates it as an empty list.

        Args:
            create (bool): Whether to create the file if not present.
        """
        # Optionally create a new, empty JSON file if it does not exist
        if create and not os.path.exists(self.file_path):
            try:
                with open(self.file_path, "w", encoding="utf-8") as fp:
                    json.dump([], fp)
                self.data = []
                self.logger.info(
                    "File '%s' not found; created new empty list at path.", self.file_path
                )
            except Exception as e:
                self.logger.error(
                    "Failed to create new JSON file '%s': %s", self.file_path, e
                )
                self.data = None
            return

        # Read existing file
        try:
            with open(self.file_path, 'r', encoding="utf-8") as fp:
                self.data = json.load(fp)
            self.logger.debug("Successfully loaded JSON data from '%s'.", self.file_path)

        except FileNotFoundError:
            self.logger.error("File '%s' not found.", self.file_path)
            self.data = None

        except json.JSONDecodeError as jde:
            self.logger.error(
                "Failed to decode JSON from '%s': %s", self.file_path, jde
            )
            self.data = None

        except Exception as exc:
            self.logger.error(
                "Unexpected error reading '%s': %s", self.file_path, exc
            )
            self.data = None

    def get_data(self):
        """
        Retrieve the entire JSON object (list or dict).

        Returns:
            dict or list or None: The parsed JSON data, or None on failure.
        """
        return self.data

    def get_value(self, key, default=None):
        """
        Get a top‐level value by key from JSON data (only if data is a dict).

        Args:
            key (str): Dictionary key to look up.
            default: Value to return if key is missing or data is not a dict.

        Returns:
            Any: The value for the key, or default.
        """
        if isinstance(self.data, dict):
            return self.data.get(key, default)

        self.logger.error("Cannot get key '%s': JSON data is not a dictionary.", key)
        return default

    def set_data(self, data):
        """
        Overwrite the JSON file with the provided Python data structure.

        Args:
            data (dict or list): The data to write back to file.

        Returns:
            None
        """
        try:
            with open(self.file_path, 'w', encoding="utf-8") as fp:
                json.dump(data, fp, indent=4, ensure_ascii=False, default=str)
            self.data = data
            self.logger.info("Data successfully written to '%s'.", self.file_path)

        except Exception as exc:
            self.logger.error("Error writing to '%s': %s", self.file_path, exc)

    def get_social_values(self, social_type, name):
        """
        Extract credentials for a named social-bot entry.

        Args:
            social_type (str): Bot type, e.g. "telegram", "bluesky", or "linkedin".
            name (str): Name identifier of the bot entry.

        Returns:
            tuple: Four‐element tuple containing credentials and mute flag.
                - Telegram:   (token, chat_id, None, mute)
                - Bluesky:    (handle, password, service, mute)
                - LinkedIn:   (urn, access_token, None, mute)
                - On failure or not found: (None, None, None, None)
        """
        social_list = self.get_value("social", [])
        if not isinstance(social_list, list):
            self.logger.error("'social' key is not a list; found %s", type(social_list))
            return (None, None, None, None)

        # Iterate entries for the requested social_type
        for entry in social_list:
            if social_type not in entry:
                continue

            for bot in entry[social_type]:
                if bot.get("name") != name:
                    continue

                # Gather common fields
                mute = bot.get("mute", False)

                if social_type == "telegram":
                    token = bot.get("token")
                    chat_id = bot.get("chat_id")
                    if not token or not chat_id:
                        self.logger.error(
                            "Telegram bot '%s' missing token/chat_id.", name
                        )
                        return (None, None, None, None)
                    return (token, chat_id, None, mute)

                elif social_type == "bluesky":
                    handle = bot.get("handle")
                    password = bot.get("password")
                    service = bot.get("service", "https://bsky.social")
                    if not handle or not password:
                        self.logger.error(
                            "Bluesky bot '%s' missing handle/password.", name
                        )
                        return (None, None, None, None)
                    return (handle, password, service, mute)

                elif social_type == "linkedin":
                    urn = bot.get("urn")
                    access_token = bot.get("access_token")
                    if not urn or not access_token:
                        self.logger.error(
                            "LinkedIn bot '%s' missing urn/access_token.", name
                        )
                        return (None, None, None, None)
                    return (urn, access_token, None, mute)

                else:
                    self.logger.warning(
                        "Unsupported social_type '%s' requested.", social_type
                    )
                    return (None, None, None, None)

        # If we get here, no matching entry was found
        self.logger.error(
            "No credentials found for %s bot named '%s'.", social_type, name
        )
        return (None, None, None, None)


def main():
    """
    Command-line interface for JSONReader.

    Usage examples:
        # Show version and exit
        python json_reader.py --version

        # Read (or create) a JSON file, then dump data & try some lookups
        python json_reader.py \
            --file settings.json \
            --create \
            --log-level DEBUG
    """
    parser = argparse.ArgumentParser(
        description="JSONReader CLI — load, inspect, and update JSON files."
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program version and exit."
    )
    parser.add_argument(
        "-f", "--file",
        required=True,
        help="Path to the JSON settings file."
    )
    parser.add_argument(
        "--create",
        action="store_true",
        help="Create the file if it does not exist."
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level (default: INFO)."
    )

    args = parser.parse_args()

    # Instantiate reader with CLI options
    reader = JSONReader(
        file_path=args.file,
        create=args.create,
        log_level=args.log_level
    )

    # Dump entire JSON content
    data = reader.get_data()
    reader.logger.info("Full JSON data (pretty-printed):")
    reader.logger.info(json.dumps(data, indent=4, ensure_ascii=False))

    # Example: retrieve a top-level key 'rss'
    rss_val = reader.get_value("rss", default="(not found)")
    reader.logger.info("Value for key 'rss': %s", rss_val)

    # Example: fetch Telegram bot credentials
    token, chat_id, _, mute = reader.get_social_values("telegram", "mybot")
    if token and chat_id:
        reader.logger.info(
            "Telegram credentials → token=%s, chat_id=%s, mute=%s",
            token, chat_id, mute
        )
    else:
        reader.logger.warning("Telegram credentials not found or incomplete.")


if __name__ == "__main__":
    main()