import logging

class Logger:
    """
    Logger utility class to configure and provide a logger instance.
    """

    @staticmethod
    def get_logger(name=__name__, level=logging.INFO):
        """
        Returns a configured logger instance.

        Args:
            name (str): Name of the logger.
            level (int): Logging level (e.g., logging.INFO, logging.DEBUG).

        Returns:
            logging.Logger: Configured logger instance.
        """
        logger = logging.getLogger(name)
        if not logger.hasHandlers():
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        logger.setLevel(level)
        return logger