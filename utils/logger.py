import logging

class Logger:
    """
    Logger utility class to configure and provide a logger instance.
    """

    @staticmethod
    def get_logger(name=__name__, level="INFO"):
        """
        Returns a configured logger instance.

        Args:
            name (str): Name of the logger.
            level (str or int): Logging level (e.g., "INFO", "DEBUG" or logging.INFO).

        Returns:
            logging.Logger: Configured logger instance.
        """
        logger = logging.getLogger(name)
        if not logger.hasHandlers():
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        # Convert string level to logging constant if needed
        if isinstance(level, str):
            level = getattr(logging, level.upper(), logging.INFO)
        logger.setLevel(level)
        return logger