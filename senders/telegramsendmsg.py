#!/usr/bin/env python3
"""
telegram_bot_publisher.py

Class for sending messages to a Telegram chat via a BotFather token.
Includes a command-line interface for quick testing.

Usage examples:
    # Show version and exit
    python telegram_bot_publisher.py --version

    # Send a message from the CLI (INFO-level logs by default)
    python telegram_bot_publisher.py \
        --token XXXXXXXXXXXXXXXXXX \
        --chat-id XXXXXXXXXXXXXXX \
        --message "Hello, world!"

    # Send a message with debug logs enabled
    python telegram_bot_publisher.py \
        --token XXXXXXXXXXXXXXXXXX \
        --chat-id XXXXXXXXXXXXXXX \
        --message "Hello, world!" \
        --debug
"""

import argparse
import logging
import requests


# ------------------------------------------------------------------------------
# Module version
# ------------------------------------------------------------------------------
__version__ = "1.0.0"


# ------------------------------------------------------------------------------
# Module‐level logging configuration
# ------------------------------------------------------------------------------
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(format=LOG_FORMAT)
logger = logging.getLogger(__name__)


class TelegramBotPublisher:
    """
    Class to send messages to a Telegram chat using a bot token.

    Args:
        token_botfather (str): The Telegram bot token from BotFather.
        chat_id (str): The chat ID where the message will be sent.
    """

    def __init__(self, token_botfather, chat_id):
        self.token = token_botfather
        self.chat_id = chat_id
        # Build the full sendMessage API endpoint URL
        self.api_url = f"https://api.telegram.org/bot{self.token}/sendMessage"

        # Class‐specific logger
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug(
            "Initialized TelegramBotPublisher with chat_id=%s", self.chat_id
        )

    def send_message(self, message):
        """
        Sends a message to the specified Telegram chat.

        Args:
            message (str): The message text to send.

        Returns:
            dict: The JSON response from the Telegram API.
        """
        payload = {
            "chat_id": self.chat_id,
            "text": message
        }

        self.logger.debug("Sending payload to Telegram API: %s", payload)
        try:
            response = requests.post(self.api_url, data=payload)
        except Exception as e:
            self.logger.error("Failed to send request to Telegram API: %s", e)
            return {"ok": False, "error": str(e)}

        # Log a warning if Telegram returns a non‐200 status
        if response.status_code != 200:
            self.logger.warning(
                "Telegram API returned status %s: %s",
                response.status_code, response.text
            )
        else:
            self.logger.info("Message successfully sent to chat %s", self.chat_id)

        # Return parsed JSON (may contain 'ok': False on API-level errors)
        try:
            return response.json()
        except ValueError as ve:
            self.logger.error("Invalid JSON in Telegram response: %s", ve)
            return {"ok": False, "error": "Invalid JSON response"}


def main():
    """
    Command-line interface for TelegramBotPublisher.

    Allows sending a one-off message to a Telegram chat from the shell.
    """
    parser = argparse.ArgumentParser(
        description="Send a message to Telegram via BotFather token"
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program version and exit."
    )
    parser.add_argument(
        "-t", "--token",
        required=True,
        help="Telegram bot token (from BotFather)"
    )
    parser.add_argument(
        "-c", "--chat-id",
        required=True,
        help="Target chat ID (user or group)"
    )
    parser.add_argument(
        "-m", "--message",
        required=True,
        help="Text message to send"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable DEBUG-level logging instead of INFO"
    )

    args = parser.parse_args()

    # Configure root logger: DEBUG if --debug, otherwise INFO
    level = logging.DEBUG if args.debug else logging.INFO
    logger.setLevel(level)

    # Instantiate the publisher and send the message
    publisher = TelegramBotPublisher(args.token, args.chat_id)
    result = publisher.send_message(args.message)

    # Log the full Telegram API response at DEBUG level
    logger.debug("Telegram API response payload: %s", result)


if __name__ == "__main__":
    main()