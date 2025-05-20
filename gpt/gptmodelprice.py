import requests
from bs4 import BeautifulSoup

class GPTModelPriceExtractor:
    """
    Extracts input and output prices for a given GPT model from docsbot.ai.

    Args:
        model (str): The model name (e.g., 'gpt-4-1-nano' or 'gpt-4.1-nano').

    Methods:
        get_prices(): Returns a dictionary with input and output prices as floats, or an error message.
    """
    def __init__(self, model):
        # Replace dots with dashes to match the URL format
        self.model = model.replace('.', '-')
        self.url = f"https://docsbot.ai/models/{self.model}"

    def extract_number(self, div):
        """
        Extracts a float number from a BeautifulSoup div containing a price string.
        """
        if div:
            text = div.get_text(strip=True).replace("$", "").replace(",", ".")
            try:
                return float(text)
            except ValueError:
                return None
        return None

    def get_prices(self):
        """
        Scrapes the docsbot.ai model page and returns input/output prices as floats.

        Returns:
            dict: {'input': float or None, 'output': float or None} or {'error': str}
        """
        response = requests.get(self.url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            input_div = soup.select_one(
                "div.mt-8.flow-root div > div > table > tbody > tr:nth-child(1) > td.px-3.py-4.text-center > div.text-lg.font-bold.text-gray-900"
            )
            output_div = soup.select_one(
                "div.mt-8.flow-root div > div > table > tbody > tr:nth-child(2) > td.px-3.py-4.text-center > div.text-lg.font-bold.text-gray-900"
            )
            input_price = self.extract_number(input_div)
            output_price = self.extract_number(output_div)
            return {"input": input_price, "output": output_price}
        else:
            return {"error": f"Unable to access the page, status: {response.status_code}"}

if __name__ == "__main__":
    model = "gpt-4.1-nano"  # You can use either "gpt-4.1-nano" or "gpt-4-1-nano"
    extractor = GPTModelPriceExtractor(model)
    prices = extractor.get_prices()
    if "error" in prices:
        print(prices["error"])
    else:
        print(f"Price for {model}: input={prices['input']}, output={prices['output']}")
