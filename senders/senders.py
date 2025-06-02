from senders.telegramsendmsg import TelegramBotPublisher
from senders.blueskysendmsg import BlueskyPoster
from senders.linkedinpublisher import LinkedInPublisher

class SocialSender:
    def __init__(self, reader, logger):
        self.reader = reader
        self.logger = logger

    def send_to_telegram(self, feed, ismute=False):
        """
        Send a single feed to all configured Telegram bots.
        """
        bots = feed.get("telegram", {}).get("bots", [])
        for bot in bots:
            mute = False
            token, chat_id, _, mute = self.reader.get_social_values("telegram", bot)
            if not mute or not ismute:
                self.logger.debug(f"Sending new feed to Telegram... {feed.get('title', '')}")                
                self.logger.debug(f"TelegramBotPublisher initialized with token {token} and chat_id {chat_id}.")
                telebot = TelegramBotPublisher(token, chat_id)
                link_to_use = feed.get('short_link') or feed.get('link', '')
                self.logger.debug(f"{feed.get('title', '')}\n{feed.get('description', '')}\n{link_to_use}")
                telebot.send_message(f"{feed.get('title', '')}\n{feed.get('description', '')}\n{link_to_use}")
            else:
                self.logger.debug(f"Skipping Telegram message for {feed.get('title', '')} due to mute setting.")

    def send_to_bluesky(self, feed, ismute=False):
        """
        Send a single feed to all configured Bluesky bots.
        """
        bots = feed.get("bluesky", {}).get("bots", [])
        for bot in bots:
            mute = False
            handle, password, service, mute = self.reader.get_social_values("bluesky", bot)
            if not mute or not ismute:
                self.logger.debug(f"Sending new feed to BlueSky... {feed.get('title', '')}")                
                link_to_use = feed.get('short_link') or feed.get('link', '')
                self.logger.debug(f"BlueskyBotPublisher initialized with Handle {handle}, password {password} and service {service}.")
                self.logger.debug(f"{feed.get('title', '')}\n{feed.get('description', '')}\n{link_to_use}")
                blueskybot = BlueskyPoster(handle, password, service)
                try:
                    ai_comment = feed.get('ai-comment', '') or None
                    response = blueskybot.post_feed(
                        description=feed.get('description', ''),
                        link=link_to_use,
                        ai_comment=ai_comment,
                        title=feed.get('title', '')
                    )
                    self.logger.debug(f"Server response: {response}")
                except Exception as e:
                    self.logger.error(f"Error while posting: {e}")
            else:
                self.logger.debug(f"Skipping Bluesky message for {feed.get('title', '')} due to mute setting.")

    def send_to_linkedin(self, feed, ismute=False):
        """
        Send a single feed to all configured LinkedIn accounts.
        """
        bots = feed.get("linkedin", {}).get("bots", [])
        for bot in bots:
            mute = False
            urn, access_token, _, mute = self.reader.get_social_values("linkedin", bot)
            if not mute or not ismute:
                self.logger.debug(f"Sending new feed to Linkedin... {feed.get('title', '')}")                
                link_to_use = feed.get('short_link') or feed.get('link', '')
                self.logger.debug(f"LinkedinBotPublisher initialized with urn {urn}, access_token {access_token}.")
                self.logger.debug(f"{feed.get('title', '')}\n{feed.get('description', '')}\n{link_to_use}")
                linkedinbot = LinkedInPublisher(access_token, urn=urn, logger=self.logger)
                try:
                    ai_comment = feed.get('ai-comment', '') or None
                    self.logger.debug(f"Args passed to linkedinbot: {ai_comment or feed.get('description', '')}, {link_to_use}, {feed.get('category', [])}")
                    response = linkedinbot.post_link(
                        text=ai_comment or feed.get('description', ''),
                        link=link_to_use,
                        category=feed.get('category', []),
                    )
                    self.logger.debug(f"Server response: {response}")
                except Exception as e:
                    self.logger.error(f"Error while posting: {e}")
            else:
                self.logger.debug(f"Skipping Linkedin message for {feed.get('title', '')} due to mute setting.")

# --- Main function for testing ---
if __name__ == "__main__":
    import logging
    from utils.readjson import JSONReader
    from utils.logger import Logger

    # Example logger setup
    logger = Logger.get_logger("SocialSenderTest", level="DEBUG")

    # Example config and feed (replace with your real config/feeds for real test)
    config_path = "./settings.json"
    reader = JSONReader(config_path, logger=logger)

    # Example feed structure for testing
    test_feed = {
        "title": "Test Title",
        "description": "Test Description",
        "short_link": "https://example.com/test",
        "ai-comment": "This is an AI-generated comment.",
        "category": ["news", "cyber security"],
        "telegram": {"bots": ["default"]},
        "bluesky": {"bots": ["default"]},
        "linkedin": {"bots": ["default"]}
    }

    sender = SocialSender(reader, logger)
    print("Testing Telegram...")
    sender.send_to_telegram(test_feed)
    print("Testing Bluesky...")
    sender.send_to_bluesky(test_feed)
    print("Testing LinkedIn...")
    sender.send_to_linkedin(test_feed)
