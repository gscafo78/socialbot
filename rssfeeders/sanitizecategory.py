__version__ = "0.0.1"

import logging

class Category:
    def __init__(self, category, logger=None):
        """
        Initialize the Category object.
        Args:
            category (str or list): The category or list of categories to sanitize.
            logger (logging.Logger, optional): Logger instance for debug/info messages.
        """
        self.category = category
        self.sanitized_category = None
        self.hashtag_category = None
        self.logger = logger or logging.getLogger(__name__)

    def sanitize(self):
        """
        Sanitize the category or list of categories by:
        - Removing special characters and converting to lowercase.
        - Removing categories with more than 3 words.
        - Removing duplicates.
        - Removing the category 'articoli'.
        The result is saved in self.sanitized_category.
        """
        if isinstance(self.category, list):
            sanitized_category = []
            for c in self.category:
                if isinstance(c, str):
                    # Skip if more than 3 words
                    if len(c.split()) > 3:
                        continue
                    # Remove spaces and convert to lowercase
                    sanitized = c.replace(" ", "").lower()
                    # Skip the category 'articoli'
                    if sanitized == "articoli":
                        continue
                    # Add only unique categories
                    if sanitized not in sanitized_category:
                        sanitized_category.append(sanitized)
        elif isinstance(self.category, str):
            sanitized = self.category.replace(" ", "").lower()
            # Set to None if the category is 'articoli'
            sanitized_category = None if sanitized == "articoli" else sanitized
        else:
            sanitized_category = None
        self.sanitized_category = sanitized_category
        self.logger.debug(f"Categories: {sanitized_category}")
        return 
    
    def hashtag(self):
        """
        Generate a list of hashtags from the sanitized_category.
        - Each hashtag is prefixed with '#'.
        - The result is saved in self.hashtag_category.
        Returns:
            list: List of hashtags.
        """
        if self.sanitized_category is None:
            self.logger.warning("Sanitized category is None. Please run sanitize() first.")
            return None

        if isinstance(self.sanitized_category, list):
            hashtag_category = [f"#{cat}" for cat in self.sanitized_category]
        elif isinstance(self.sanitized_category, str):
            hashtag_category = [f"#{self.sanitized_category}"]
        else:
            hashtag_category = []

        self.hashtag_category = hashtag_category
        self.logger.debug(f"Hashtag categories: {hashtag_category}")
        return hashtag_category

def main():
    """
    Example usage of the Category class:
    - Sanitizes a list of categories.
    - Generates hashtags from sanitized categories.
    - Prints the results.
    """
    import logging
    logging.basicConfig(level=logging.DEBUG)
    # Example list of categories (with duplicates, spaces, and 'articoli')
    category = [
        "Articoli", 
        "Cyber Crime", 
        "Cyber Security", 
        "cybercrime", 
        "cybersecurity", 
        "cyberspace", 
        "Data Protection", 
        "deepfake",
        "digital security",
        "Disinformazione",
        "encrypting",
        "Ivan Visconti",
        "privacy protection",
        "Zero Knowledge Proofs",
        "ZKP",
        "Articoli",
        "Cyber Crime",
        "Cyber Risk",
        "Cyber Security",
        "Bring Your Own Vulnerable Driver",
        "BYOVD",
        "BYOVD Attacks",
        "Cyber Attacks",
        "cyber defence",
        "cyber threats",
        "cybercrime",
        "cybersecurity",
        "Hacking"
    ]
    sanitized = Category(category, logger=logging.getLogger(__name__))
    sanitized.sanitize()      # Clean and deduplicate categories
    hashtags = sanitized.hashtag()       # Generate hashtags from sanitized categories
    print("Sanitized categories:", sanitized.sanitized_category)
    print("Hashtags:", hashtags)

if __name__ == "__main__":
    main()



