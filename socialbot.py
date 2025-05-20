import json
from utils.readjson import JSONReader



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
