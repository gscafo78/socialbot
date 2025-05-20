import json

class JSONReader:
    def __init__(self, file_path):
        """
        Initialize the JSONReader with the path to the JSON file.

        :param file_path: Path to the JSON file
        """
        self.file_path = file_path
        self.data = None
        self._read_file()

    def _read_file(self):
        """
        Private method to read the JSON file and load its content into the `data` attribute.
        """
        try:
            with open(self.file_path, 'r') as file:
                self.data = json.load(file)
        except FileNotFoundError:
            print(f"Error: File '{self.file_path}' not found.")
        except json.JSONDecodeError as e:
            print(f"Error: Failed to decode JSON. {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

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
            print("Error: JSON data is not a dictionary.")
            return default

def main():
    """
    Example usage:
    Reads a JSON file and prints its content and a specific value by key.
    """
    file_path = "/opt/github/03_Script/Python/socialbot/settings.json"  # Replace with your JSON file path
    reader = JSONReader(file_path)
    data = reader.get_data()
    print("Full JSON data (pretty print):")
    print(json.dumps(data, indent=4, ensure_ascii=False))  # Pretty print the JSON
    # Example: try to get the value for key 'rss'
    value = reader.get_value('rss', default="Key not found")
    print("Value for key 'rss':", value)

if __name__ == "__main__":
    main()

