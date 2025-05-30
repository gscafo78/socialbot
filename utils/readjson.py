import json
import os
from utils.logger import Logger

class JSONReader:
    """
    Utility class for reading and writing JSON files.
    """

    def __init__(self, file_path, create=False, logger=None, log_level="INFO"):
        """
        Initialize the JSONReader with the path to the JSON file.

        Args:
            file_path (str): Path to the JSON file.
            create (bool): If True, create the file with an empty list if it does not exist.
            logger (logging.Logger): Logger instance (optional).
            log_level (str): Logging level if logger is not provided (default "INFO").
        """
        self.file_path = file_path
        self.data = None
        # Use the provided logger or create a new one with the requested level
        if logger is not None:
            self.logger = logger
        else:
            self.logger = Logger.get_logger(__name__, level=log_level)
        self._read_file(create)

    def _read_file(self, create=False):
        """
        Private method to read the JSON file and load its content into the `data` attribute.
        If create=True and the file does not exist, create it with an empty list.

        Args:
            create (bool): Whether to create the file if it does not exist.
        """
        if create and not os.path.exists(self.file_path):
            with open(self.file_path, "w") as f:
                json.dump([], f)
            self.data = []
            self.logger.info(f"File '{self.file_path}' not found. Created an empty list file.")
            return

        try:
            with open(self.file_path, 'r') as file:
                self.data = json.load(file)
        except FileNotFoundError:
            self.logger.error(f"Error: File '{self.file_path}' not found.")
            self.data = None
        except json.JSONDecodeError as e:
            self.logger.error(f"Error: Failed to decode JSON. {e}")
            self.data = None
        except Exception as e:
            self.logger.error(f"An unexpected error occurred: {e}")
            self.data = None

    def get_data(self):
        """
        Get the entire JSON data.

        Returns:
            dict or list or None: Parsed JSON data as a Python dictionary or list, or None if loading failed.
        """
        return self.data

    def get_value(self, key, default=None):
        """
        Get a value from the JSON data by key (for dictionary-like JSON).

        Args:
            key (str): Key to look up in the JSON data.
            default: Default value to return if the key is not found.

        Returns:
            Any: Value associated with the key, or the default value if not found or if data is not a dict.
        """
        if isinstance(self.data, dict):
            return self.data.get(key, default)
        else:
            self.logger.error("Error: JSON data is not a dictionary.")
            return default

    def set_data(self, data):
        """
        Overwrite the JSON file with the provided data.

        Args:
            data (dict or list): Data to write to the JSON file.

        Returns:
            None
        """
        try:
            with open(self.file_path, 'w') as file:
                json.dump(data, file, indent=4, ensure_ascii=False, default=str)
            self.data = data
            self.logger.info(f"Data successfully written to '{self.file_path}'.")
        except Exception as e:
            self.logger.error(f"Error writing to '{self.file_path}': {e}")

    def get_social_values(self, social_type, name):
        """
        Returns the credentials for a given social bot name.

        Args:
            social_type (str): The social type, e.g. "telegram" or "bluesky".
            name (str): The bot name to search for.

        Returns:
            tuple:
                - For "telegram": (token, chat_id, None)
                - For "bluesky": (handle, password, service)
                - If not found: (None, None, None)
        """
        social_list = self.get_value("social", [])
        for entry in social_list:
            if social_type in entry:
                if social_type == "telegram":
                    for bot in entry[social_type]:
                        if bot.get("name") == name:
                            token = bot.get("token")
                            chat_id = bot.get("chat_id")
                            if not token or not chat_id:
                                self.logger.error(f"Error: Missing token or chat_id for {social_type} bot named '{name}'.")
                                return None, None, None, None
                            # Check if 'mute' is present, default to False if not
                            mute = bot.get("mute", False)
                            return token, chat_id, None, mute
                elif social_type == "bluesky":
                    for bot in entry[social_type]:
                        if bot.get("name") == name:
                            handle = bot.get("handle")
                            password = bot.get("password")
                            service = bot.get("service", "https://bsky.social")
                            mute = bot.get("mute", False)
                            if not handle or not password:
                                self.logger.error(f"Error: Missing handle or password for {social_type} bot named '{name}'.")
                                return None, None, None, None
                            return handle, password, service, mute
                elif social_type == "linkedin":
                    for bot in entry[social_type]:
                        if bot.get("name") == name:
                            urn = bot.get("urn")
                            access_token = bot.get("access_token")
                            mute = bot.get("mute", False)
                            if not urn or not access_token:
                                self.logger.error(f"Error: Missing handle or password for {social_type} bot named '{name}'.")
                                return None, None, None, None
                            return urn, access_token, None, mute
        
        self.logger.error(f"Error: No credentials found for {social_type} bot named '{name}'.")
        return None, None, None, None

# Example usage
def main():
    """
    Example usage:
    Reads a JSON file and prints its content and a specific value by key.
    If the file does not exist, it will be created as an empty list.

    Usage:
        reader = JSONReader(file_path, create=True)
        data = reader.get_data()
        value = reader.get_value('some_key', default="Not found")
        reader.set_data(new_data)
    """
    file_path = "/opt/github/03_Script/Python/socialbot/settings.json"  # Replace with your JSON file path
    reader = JSONReader(file_path, create=True)
    data = reader.get_data()
    reader.logger.info("Full JSON data (pretty print):")
    reader.logger.info(json.dumps(data, indent=4, ensure_ascii=False))  # Pretty print the JSON
    # Example: try to get the value for key 'rss'
    value = reader.get_value('rss', default="Key not found")
    reader.logger.info(f"Value for key 'rss': {value}")

if __name__ == "__main__":
    main()

