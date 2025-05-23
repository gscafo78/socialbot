import requests
from .gptmodelprice import GPTModelPriceExtractor


class GPTModelSelector:
    def __init__(self, api_key):
        self.api_key = api_key

    def get_models_and_prices(self):
        """
        Fetches the list of available OpenAI models and retrieves their usage prices.
        Returns a list of dicts with model id and prices.
        """
        url = "https://api.openai.com/v1/models"
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"Error fetching models: {e}")
            return []

        models = response.json().get("data", [])
        result = []
        for model in models:
            model_id = model.get("id")
            if not model_id:
                continue
            try:
                extractor = GPTModelPriceExtractor(model_id)
                prices = extractor.get_prices()
            except Exception as e:
                prices = {"error": str(e)}
            model_info = {
                "id": model_id,
                "prices": prices
            }
            result.append(model_info)
        return result

    def get_cheapest_gpt_model(self):
        """
        Identifies the cheapest GPT model (by input price) available for the given API key.
        Returns the model_id of the cheapest GPT model, or None if not found.
        """
        models = self.get_models_and_prices()
        cheapest_model = None
        cheapest_price = float('inf')
        for model in models:
            model_id = model["id"]
            # Consider only GPT models
            if model_id.startswith("gpt"):
                prices = model.get("prices", {})
                input_price = prices.get("input")
                try:
                    price_val = float(input_price)
                except (TypeError, ValueError):
                    continue
                if price_val < cheapest_price:
                    cheapest_price = price_val
                    cheapest_model = model_id
        return cheapest_model

    def print_all_models_and_cheapest(self):
        """
        Prints all models and their prices, and the cheapest GPT model.
        """
        print("All models and prices:")
        models = self.get_models_and_prices()
        for model in models:
            print(f"ID: {model['id']}, Prices: {model['prices']}")
        cheapest = self.get_cheapest_gpt_model()
        print(f"Cheapest GPT model by input price: {cheapest}")

def main():
    api_key = "XXXXXXXXXXXXXXXXXXXXXXXX" # Replace with your OpenAI API key
    selector = GPTModelSelector(api_key)
    selector.print_all_models_and_cheapest()

if __name__ == "__main__":
    main()