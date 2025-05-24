from openai import OpenAI
import requests
from bs4 import BeautifulSoup
from .getmodel import GPTModelSelector

class ArticleCommentator:
    """
    Class to generate a comment for an article using OpenAI GPT models.

    Args:
        link (str): URL of the article.
        openai_key (str): OpenAI API key.
        model (str, optional): GPT model to use. If None, selects the cheapest available.
        max_chars (int, optional): Maximum number of characters for the response.
        language (str, optional): Language for the comment ('it' for Italian, 'en' for English).
    """
    def __init__(self, link, openai_key, model=None, max_chars=160, language="en"):
        self.link = link
        self.openai_key = openai_key
        self.max_chars = max_chars
        self.language = language
        # If no model is provided, select the cheapest GPT model automatically
        if model is None:
            selector = GPTModelSelector(self.openai_key)
            self.model = selector.get_cheapest_gpt_model()
            # print(f"Automatic model selection: {self.model}")
        else:
            self.model = model
        self.client = OpenAI(api_key=self.openai_key)
    
    def extract_text(self):
        """
        Extracts the main text from the article at the provided URL.
        """
        response = requests.get(self.link)
        soup = BeautifulSoup(response.content, 'html.parser')
        paragraphs = soup.find_all('p')
        full_text = ' '.join([p.get_text() for p in paragraphs])
        return full_text
    
    def generate_comment(self):
        """
        Generates a comment for the article using the selected GPT model.
        The comment is written in the language specified during initialization.
        """
        article_text = self.extract_text()
        if not article_text.strip():
            return ""
        if self.language == "en":
            answare = "English"
        elif self.language == "it":
            answare = "Italian"
        else:
            raise ValueError("Invalid language. Use 'en' for English or 'it' for Italian.") 

        prompt = (
            f"Read and summarize in a colloquial and natural way in {answare} the following article, "
            f"also giving a personal comment as if you had read it: {article_text}"
        )
        system_message = (
            f"You are an expert article commentator, able to summarize and comment in a colloquial way. "
            f"Do not sponsor advertisements in the article. The answer must be a maximum of {self.max_chars} characters."
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content

def main():    
    """
    Example usage:
    Prompts the user for article URL, max characters, language, and model selection.
    Generates and prints a comment for the article.
    """
    article_link = "https://www.redhotcyber.com/post/falso-mito-se-uso-una-vpn-sono-completamente-al-sicuro-anche-su-reti-wifi-aperte-e-non-sicure/"
    openai_key = "XXXXXXXXXXXXXXXXXXXXXXXXXXX" # Replace with your OpenAI API key
    # max_caratteri = int(input("Inserisci il numero massimo di caratteri per la risposta: "))
    # lingua = input("Lingua della risposta ('it' per italiano, 'en' per inglese): ").strip().lower()
    
    # scelta = input("Vuoi selezionare il modello manualmente? (s/n): ").strip().lower()
    # if scelta == "s":
    #     modello = input("Inserisci il nome del modello GPT da usare (es: gpt-4.1-nano): ").strip()
    # else:
    #     modello = None

    # commentatore = ArticleCommentator(article_link, openai_key, modello, max_caratteri, lingua)
    commentator = ArticleCommentator(article_link, openai_key)
    comment = commentator.generate_comment()
    print(comment)

if __name__ == "__main__":
    main()