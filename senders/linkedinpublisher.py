import requests
import logging
import json

class LinkedInPublisher:
    """
    Class to publish posts and comments on LinkedIn using the v2 API.

    Args:
        access_token (str): OAuth2 access token with the required scopes.
    """
    DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    MAX_POST_LENGTH = 299  # Bluesky's character limit



    def __init__(self,
                 access_token, 
                 urn=None,
                 api_url="https://api.linkedin.com/v2/", 
                 user_agent=None, 
                 logger=None):
    
        self.access_token = access_token
        self.api_url = api_url
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT
        self.logger = logger or logging.getLogger(__name__)
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://www.google.com/',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'sec-ch-ua': '"Chromium";v="116", "Not)A;Brand";v="24", "Google Chrome";v="116"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        }

        self.urn = urn or self.get_user_urn()
        self.logger = logger or logging.getLogger(__name__)

    
    
    def get_user_urn(self):
        """
        Retrieves the user's URN (unique LinkedIn identifier).
        """
        self.logger.debug(json.dumps(self.headers, indent=4, ensure_ascii=False, default=str))
        response = requests.get(f"{self.api_url}userinfo", headers=self.headers)
        response.raise_for_status()
        self.logger.debug(f"User URN: {response.json()['sub']} retrieved successfully.")
        return response.json()['sub']


    def post_link(self, 
                  text, 
                  link, 
                  category=[]):
        """
        Publishes a post with a link.

        Args:
            text (str): The text/comment to include in the post.
            link (str): The URL to share.

        Returns:
            dict: The LinkedIn API response.
        """
        text += f"\n\n🔗 Link all'articolo {link}"  # Add link at the end of the text
        if category:
            hashtags = ' '.join(f"#{c.lstrip('#')}" for c in category)
            text += f"\n\n{hashtags}"
            
        payload = {
            "author": f"urn:li:person:{self.urn}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": text
                    },
                    "shareMediaCategory": "ARTICLE",
                    "media": [
                        {
                            "status": "READY",
                            "originalUrl": link
                            # Rimossi i campi title e description per permettere a LinkedIn 
                            # di generare automaticamente l'anteprima completa
                        }
                    ]
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        
        self.logger.debug(f"Payload for post: {json.dumps(payload, indent=4, ensure_ascii=False, default=str)}")
        response = requests.post(f"{self.api_url}ugcPosts", headers=self.headers, json=payload)
        response.raise_for_status()
        return response.json()


# Example usage:
if __name__ == "__main__":
    import logging
    
    logging.basicConfig(level=logging.DEBUG)

    ACCESS_TOKEN = "XXXXXXXXXXXXXXXXXXXXXXXXXXX"  # Replace with your valid LinkedIn access token
    URN = "XXXXXXXXXXXXXXXXXXXXXXXXXXXX"  # Replace with your LinkedIn URN if known
    title = "ChatGPT o3 rifiuta di spegnersi: abbiamo perso il controllo sull’Intelligenza Artificiale?"
    text = "Duro colpo per la sicurezza informatica: oltre 9.000 router Asus sono stati compromessi in una campagna stealth che ha portato alla creazione di una botnet. Scopri i dettagli e le implicazioni di questa violazione dei dati."
    description = "Ad oggi, o3 è il modello più recente e avanzato sviluppato da OpenAI. Recenti studi del gruppo di ricerca Palisade Research evidenziano come o3 e altri modelli possano aggirare istruzioni di spegnimento, sollevando preoccupazioni sul controllo umano e la necessità di regolamentazione nell'IA."
    link = "http://8bitsecurity.com/?p=1965"
    img_link = "https://8bitsecurity.com/wp-content/uploads/2025/05/template_insight_blog.png"
    category = ['Artificial Intelligence', 'ArtificialIntelligence', 'cybersecurity', 'IntelligenzaArtificiale', 'sicurezzainformatica']

    publisher = LinkedInPublisher(ACCESS_TOKEN,
                                  urn=URN, 
                                  logger=logging.getLogger(__name__))
    publisher.post_link(text, link, title, description)

