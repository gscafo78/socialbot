from datetime import datetime
from utils.logger import Logger

class MuteTimeChecker:
    """
    Utility class to check if the current time is within the mute interval.
    """
    def __init__(self, mute_from: str, mute_to: str, logger=None, log_level="INFO"):
        """
        :param mute_from: Start time of mute interval in "HH:MM" format.
        :param mute_to: End time of mute interval in "HH:MM" format.
        :param logger: Logger instance (optional).
        :param log_level: Logging level if logger is not provided (default "INFO").
        """
        self.mute_from = mute_from
        self.mute_to = mute_to
        # Use the provided logger or create a new one with the requested level
        if logger is not None:
            self.logger = logger
        else:
            self.logger = Logger.get_logger(__name__, level=log_level)

    def is_mute_time(self) -> bool:
        """
        Returns True if the current time is OUTSIDE the mute interval, False otherwise.
        """
        try:
            now = datetime.now().time()
            mute_from_time = datetime.strptime(self.mute_from, "%H:%M").time()
            mute_to_time = datetime.strptime(self.mute_to, "%H:%M").time()

            # Special case: mute_from == mute_to means never mute
            if mute_from_time == mute_to_time:
                return True

            if mute_from_time < mute_to_time:
                return not (mute_from_time <= now <= mute_to_time)
            else:
                return not (now >= mute_from_time or now <= mute_to_time)
        except ValueError as e:
            self.logger.error(f"Error parsing mute times: {e}")
            return True