#!/usr/bin/env python3
"""
logger.py  (version 1.0.0)

Utility to configure and retrieve a named logger instance.

Usage:
    # Show version
    python utils/logger.py --version

    # Create a logger named "myapp" at INFO level and emit test messages:
    python utils/logger.py --name myapp --level INFO

    # Same as above, but in debug mode:
    python utils/logger.py --name myapp --debug

Requirements:
    Only the Python standard library.
"""

import argparse
import logging
from typing import Union

__version__ = "1.0.0"


class Logger:
    """
    Logger utility class to configure and provide a logger instance.

    The Logger.get_logger(...) method will configure a StreamHandler
    (if no handlers are already present) and set the desired log level.
    """

    @staticmethod
    def get_logger(name: str = __name__, level: Union[str, int] = "INFO") -> logging.Logger:
        """
        Returns a configured logger instance.

        Args:
            name:  Name of the logger (usually __name__ of the calling module).
            level: Logging level as a string (e.g. "DEBUG", "INFO") or integer constant.

        Returns:
            A logging.Logger instance with a StreamHandler and specified level.
        """
        logger = logging.getLogger(name)

        # If no handlers are attached, add a default StreamHandler.
        if not logger.hasHandlers():
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        # Normalize string level to logging constant
        if isinstance(level, str):
            level = getattr(logging, level.upper(), logging.INFO)

        logger.setLevel(level)
        return logger


def main() -> None:
    """
    CLI entry point to test Logger.get_logger().

    Parses command-line arguments to create a logger and emits
    one message at each standard level.
    """
    parser = argparse.ArgumentParser(description="Test the Logger utility.")
    parser.add_argument(
        "--name",
        default="root",
        help="Name of the logger to create (default: root).",
    )
    parser.add_argument(
        "--level",
        default="INFO",
        help="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Shortcut to set level=DEBUG.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s v{__version__}",
        help="Show program version and exit.",
    )
    args = parser.parse_args()

    # If --debug is set, override --level
    level = "DEBUG" if args.debug else args.level

    logger = Logger.get_logger(name=args.name, level=level)

    # Emit a message at each standard level for demonstration
    logger.debug("This is a DEBUG message.")
    logger.info("This is an INFO message.")
    logger.warning("This is a WARNING message.")
    logger.error("This is an ERROR message.")
    logger.critical("This is a CRITICAL message.")


if __name__ == "__main__":
    main()