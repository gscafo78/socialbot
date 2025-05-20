import requests

class TelegramBotPublisher:
    """
    Class to send messages to a Telegram chat using a bot token.

    Args:
        token_botfather (str): The Telegram bot token from BotFather.
        chat_id (str): The chat ID where the message will be sent.
    """
    def __init__(self, token_botfather, chat_id):
        self.token = token_botfather
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{self.token}/sendMessage"

    def send_message(self, message):
        """
        Sends a message to the specified Telegram chat.

        Args:
            message (str): The message text to send.

        Returns:
            dict: The JSON response from the Telegram API.
        """
        payload = {
            'chat_id': self.chat_id,
            'text': message
        }
        response = requests.post(self.api_url, data=payload)
        return response.json()

def main():
    """
    Example usage:
    Sends a test message to a Telegram chat using the TelegramBotPublisher class.
    """
    token = "XXXXXXXXXXXXXXXXXX"  # Replace with your bot token
    chat_id = "XXXXXXXXXXXXXXXXXXX"  # Replace with your chat ID
    message = "Hello from TelegramBotPublisher (test)!"
    bot = TelegramBotPublisher(token, chat_id)
    response = bot.send_message(message)
    print("Telegram API response:", response)

if __name__ == "__main__":
    main()

