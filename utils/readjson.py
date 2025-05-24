import json
import os
from utils.logger import Logger

logger = Logger.get_logger(__name__)

class JSONReader:
    """
    Utility class for reading and writing JSON files.
    """

    def __init__(self, file_path, create=False):
        """
        Initialize the JSONReader with the path to the JSON file.

        Args:
            file_path (str): Path to the JSON file.
            create (bool): If True, create the file with an empty list if it does not exist.
        """
        self.file_path = file_path
        self.data = None
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
            logger.info(f"File '{self.file_path}' not found. Created an empty list file.")
            return

        try:
            with open(self.file_path, 'r') as file:
                self.data = json.load(file)
        except FileNotFoundError:
            logger.error(f"Error: File '{self.file_path}' not found.")
            self.data = None
        except json.JSONDecodeError as e:
            logger.error(f"Error: Failed to decode JSON. {e}")
            self.data = None
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
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
            logger.error("Error: JSON data is not a dictionary.")
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
            logger.info(f"Data successfully written to '{self.file_path}'.")
        except Exception as e:
            logger.error(f"Error writing to '{self.file_path}': {e}")

    def get_social_credentials(self, social_type, name):
        """
        Returns the token and chat_id (or equivalent) for a given social bot name.

        Args:
            social_type (str): The social type, e.g. "telegram" or "bluesky".
            name (str): The bot name to search for.

        Returns:
            tuple: (token, chat_id) if found, otherwise (None, None)
        """
        social_list = self.get_value("social", [])
        for entry in social_list:
            if social_type in entry:
                for bot in entry[social_type]:
                    if bot.get("name") == name:
                        token = bot.get("token")
                        chat_id = bot.get("chat_id")
                        return token, chat_id
        return None, None

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
    logger.info("Full JSON data (pretty print):")
    logger.info(json.dumps(data, indent=4, ensure_ascii=False))  # Pretty print the JSON
    # Example: try to get the value for key 'rss'
    value = reader.get_value('rss', default="Key not found")
    logger.info(f"Value for key 'rss': {value}")

if __name__ == "__main__":
    main()

