import json
import os
from utils.logger import Logger

logger = Logger.get_logger(__name__)

class JSONReader:
    def __init__(self, file_path, create=False):
        """
        Initialize the JSONReader with the path to the JSON file.

        :param file_path: Path to the JSON file
        :param create: If True, create the file with an empty list if it does not exist
        """
        self.file_path = file_path
        self.data = None
        self._read_file(create)

    def _read_file(self, create=False):
        """
        Private method to read the JSON file and load its content into the `data` attribute.
        If create=True and the file does not exist, create it with an empty list.
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

        :return: Parsed JSON data as a Python dictionary or list
        """
        return self.data

    def get_value(self, key, default=None):
        """
        Get a value from the JSON data by key (for dictionary-like JSON).

        :param key: Key to look up in the JSON data
        :param default: Default value to return if the key is not found
        :return: Value associated with the key, or the default value
        """
        if isinstance(self.data, dict):
            return self.data.get(key, default)
        else:
            logger.error("Error: JSON data is not a dictionary.")
            return default

    def set_data(self, data):
        """
        Sovrascrive il file JSON con i dati forniti.

        :param data: Dati (lista o dizionario) da scrivere nel file JSON
        """
        try:
            with open(self.file_path, 'w') as file:
                json.dump(data, file, indent=4, ensure_ascii=False, default=str)
            self.data = data
            logger.info(f"Dati scritti correttamente su '{self.file_path}'.")
        except Exception as e:
            logger.error(f"Errore durante la scrittura su '{self.file_path}': {e}")

def main():
    """
    Example usage:
    Reads a JSON file and prints its content and a specific value by key.
    If the file does not exist, it will be created as an empty list.
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

