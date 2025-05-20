import requests
from gptmodelprice import GPTModelPriceExtractor


def get_models_and_prices(api_key):
    """
    Fetches the list of available OpenAI models and retrieves their usage prices by scraping docsbot.ai.

    Args:
        api_key (str): Your OpenAI API key.

    Returns:
        list: A list of dictionaries, each containing:
            {
                'id': <model_id>,
                'prices': {'input': float or None, 'output': float or None} or {'error': str}
            }
        If the API call fails, returns a dictionary with an 'error' key.
    """
    url = "https://api.openai.com/v1/models"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        models = response.json().get("data", [])
        result = []
        for model in models:
            model_id = model["id"]
            extractor = GPTModelPriceExtractor(model_id)
            prices = extractor.get_prices()
            model_info = {
                "id": model_id,
                "prices": prices
            }
            result.append(model_info)
        return result
    else:
        return {"error": response.json()}

def get_cheapest_gpt_model(api_key):
    """
    Identifies the cheapest GPT model (by input price) available for the given API key.

    Args:
        api_key (str): Your OpenAI API key.

    Returns:
        str: The model_id of the cheapest GPT model, or None if not found.
    """
    models = get_models_and_prices(api_key)
    cheapest_model = None
    cheapest_price = float('inf')
    for model in models:
        model_id = model["id"]
        # Consider only GPT models
        if model_id.startswith("gpt"):
            prices = model.get("prices", {})
            input_price = prices.get("input")
            if isinstance(input_price, float) and input_price < cheapest_price:
                cheapest_price = input_price
                cheapest_model = model_id
    return cheapest_model

def main():
    """
    Example usage:
    Retrieves all available OpenAI models and prints their input/output prices (if available).
    Also prints the cheapest GPT model by input price.
    """
    api_key = "XXXXXXXXXXXXXXXXXXXX" # Replace with your OpenAI API key
    print("All models and prices:")
    models = get_models_and_prices(api_key)
    for model in models:
        print(f"ID: {model['id']}, Prices: {model['prices']}")
    cheapest = get_cheapest_gpt_model(api_key)
    print(f"Cheapest GPT model by input price: {cheapest}")

if __name__ == "__main__":
    main()