import requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import time
import json

class BlueskyPoster:
    """
    A class to post messages with link previews to the Bluesky network.
    Args:
        handle (str): The Bluesky user handle (e.g., "user.bsky.social").
        app_password (str): The app password for authentication.
        service (str): The Bluesky service URL (default: "https://bsky.social").
        user_agent (str): The User-Agent string for HTTP requests (optional).
    """
    DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    MAX_POST_LENGTH = 300  # Bluesky's character limit
    
    def __init__(self, handle, app_password, service='https://bsky.social', user_agent=None):
        self.handle = handle
        self.app_password = app_password
        self.service = service
        self.access_jwt = None
        self.did = None
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT
        self.session = requests.Session()
    
    def create_session(self):
        """
        Authenticates with Bluesky and stores the access token and DID.
        Raises an exception if authentication fails.
        """
        resp = requests.post(
            f"{self.service}/xrpc/com.atproto.server.createSession",
            json={"identifier": self.handle, "password": self.app_password},
        )
        resp.raise_for_status()
        session = resp.json()
        self.access_jwt = session["accessJwt"]
        self.did = session["did"]
        print(f"Successfully authenticated as {self.handle}")
    
    def create_simple_embed(self, url, title=None, description=None):
        """
        Creates a simple embed with just the URL and optional title/description
        """
        card = {
            "uri": url,
            "title": title or "Link Preview",
            "description": description or "Visit the link for more information",
        }
        
        return {
            "$type": "app.bsky.embed.external",
            "external": card,
        }
    
    def fetch_embed_url_card(self, url):
        """
        Fetches metadata (title, description, image) from a URL to create a link preview card.
        Falls back to a simple embed if the fetch fails.
        """
        print(f"Attempting to fetch preview for: {url}")
        
        # For Fanpage.it domains, skip scraping and use a simple embed
        if "fanpage.it" in url:
            print("Detected fanpage.it domain - using simple embed")
            title = "Articolo da Fanpage.it"
            description = "Clicca per leggere l'articolo completo su Fanpage.it"
            return self.create_simple_embed(url, title, description)
        
        card = {
            "uri": url,
            "title": "",
            "description": "",
        }
        
        headers = {
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
        
        self.session.headers.update(headers)
        
        try:
            # Add a small delay to avoid being rate limited
            time.sleep(1)
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Extract title
            title_tag = soup.find("meta", property="og:title")
            if title_tag:
                card["title"] = title_tag.get("content", "")
            if not card["title"] and soup.title:
                card["title"] = soup.title.string or ""
            
            # Extract description
            description_tag = soup.find("meta", property="og:description")
            if description_tag:
                card["description"] = description_tag.get("content", "")
            if not card["description"]:
                desc_tag = soup.find("meta", attrs={"name": "description"})
                if desc_tag:
                    card["description"] = desc_tag.get("content", "")
            
            # Truncate if too long
            if card["title"] and len(card["title"]) > 250:
                card["title"] = card["title"][:247] + "..."
                
            if card["description"] and len(card["description"]) > 300:
                card["description"] = card["description"][:297] + "..."
                
            # Make sure we have at least some content
            if not card["title"]:
                card["title"] = "Link Preview"
            
            # Extract image and upload as blob if present
            image_tag = soup.find("meta", property="og:image")
            if image_tag:
                img_url = image_tag.get("content", "")
                img_url = urljoin(url, img_url)
                
                # Add a small delay before fetching the image
                time.sleep(0.5)
                img_resp = self.session.get(img_url, timeout=15)
                img_resp.raise_for_status()
                
                IMAGE_MIMETYPE = img_resp.headers.get("Content-Type", "image/jpeg")
                if len(img_resp.content) <= 1000000:  # Only upload if image is <= 1MB
                    print(f"Uploading image: {img_url}")
                    blob_resp = requests.post(
                        f"{self.service}/xrpc/com.atproto.repo.uploadBlob",
                        headers={
                            "Content-Type": IMAGE_MIMETYPE,
                            "Authorization": "Bearer " + self.access_jwt,
                        },
                        data=img_resp.content,
                    )
                    blob_resp.raise_for_status()
                    card["thumb"] = blob_resp.json()["blob"]
                    print("Image uploaded successfully")
            
            print(f"Successfully created embed with title: {card['title']}")
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching URL: {e}")
            # If we encounter an error, return a simplified card
            return self.create_simple_embed(url)
        
        return {
            "$type": "app.bsky.embed.external",
            "external": card,
        }
    
    def create_facets(self, text, link):
        """
        Creates link facets for the post text, so the link is clickable in the post.
        Args:
            text (str): The post text.
            link (str): The URL to facet.
        Returns:
            list: List of facet dictionaries.
        """
        facets = []
        for m in re.finditer(re.escape(link), text):
            facets.append({
                "index": {"byteStart": m.start(), "byteEnd": m.end()},
                "features": [{
                    "$type": "app.bsky.richtext.facet#link",
                    "uri": link
                }]
            })
        return facets
    
    def truncate_text(self, text, max_length=None):
        """
        Truncates text to stay within Bluesky's character limit
        """
        max_length = max_length or self.MAX_POST_LENGTH
        if len(text) <= max_length:
            return text
        
        return text[:max_length-3] + "..."
    
    def post_without_preview(self, text, link):
        """
        Posts a simple message with clickable link but no preview
        """
        if not self.access_jwt or not self.did:
            self.create_session()
            
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        # Make sure the text + link fits within the character limit
        link_length = len(link) + 2  # +2 for newlines
        available_chars = self.MAX_POST_LENGTH - link_length
        
        if available_chars <= 10:  # Not enough space for meaningful text
            truncated_text = self.truncate_text(text, self.MAX_POST_LENGTH)
            full_text = truncated_text
        else:
            truncated_text = self.truncate_text(text, available_chars)
            full_text = f"{truncated_text}\n{link}"
        
        print(f"Text length: {len(full_text)} characters")
        facets = self.create_facets(full_text, link)
        
        post = {
            "$type": "app.bsky.feed.post",
            "text": full_text,
            "createdAt": now,
        }
        
        if facets:
            post["facets"] = facets
            
        print("Posting without preview...")
        print(f"Post content: {full_text[:50]}...")
        
        record_resp = requests.post(
            f"{self.service}/xrpc/com.atproto.repo.createRecord",
            headers={"Authorization": "Bearer " + self.access_jwt},
            json={
                "repo": self.did,
                "collection": "app.bsky.feed.post",
                "record": post,
            },
        )
        
        if not record_resp.ok:
            print(f"Error response: {record_resp.status_code} - {record_resp.text}")
            record_resp.raise_for_status()
            
        return record_resp.json()
    
    def post_with_preview(self, text, link):
        """
        Publishes a post with a link preview to Bluesky.
        Args:
            text (str): The post text.
            link (str): The URL to preview.
        Returns:
            dict: The server response as a dictionary.
        Raises:
            Exception: If posting fails.
        """
        if not self.access_jwt or not self.did:
            self.create_session()
        
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        # With a link preview, we don't need to include the link in the text
        # This saves characters for the actual message
        truncated_text = self.truncate_text(text)
        
        print(f"Text length: {len(truncated_text)} characters")
        embed = self.fetch_embed_url_card(link)
        
        # Create facets for the URL (if it's in the text)
        facets = self.create_facets(truncated_text, link) if link in truncated_text else []
        
        post = {
            "$type": "app.bsky.feed.post",
            "text": truncated_text,
            "createdAt": now,
            "embed": embed,
        }
        
        if facets:
            post["facets"] = facets
        
        print("Posting with preview...")
        print(json.dumps(post, indent=2, default=str)[:500] + "...")
        
        record_resp = requests.post(
            f"{self.service}/xrpc/com.atproto.repo.createRecord",
            headers={"Authorization": "Bearer " + self.access_jwt},
            json={
                "repo": self.did,
                "collection": "app.bsky.feed.post",
                "record": post,
            },
        )
        
        if not record_resp.ok:
            print(f"Error response: {record_resp.status_code} - {record_resp.text}")
            record_resp.raise_for_status()
            
        return record_resp.json()

# Example usage:
if __name__ == "__main__":
    # Replace these values with your Bluesky credentials and desired post
    text = "Il consiglio d'amministrazione di Stellantis ha scelto il 51enne napoletano Antonio Filosa come suo nuovo Ceo: da 25 anni in Fiat, è stato Chief Executive Officer dell'Americhe e capo del marchio Jeep, rimpiazzerà il dimissionario Carlos Tavares."
    link = "https://www.fanpage.it/attualita/chi-e-antonio-filosa-il-nuovo-ceo-di-stellantis-dagli-inizi-in-fiat-fino-al-vertice-di-jeep/"
    user = "XXXXXXXXX.bsky.social"
    password = "XXXXXXXXXXXXXXXXXXX"  # Replace with your app password
    service = "https://bsky.social"
    
    poster = BlueskyPoster(user, password, service)
    
    try:
        # First try posting with preview
        response = poster.post_with_preview(text, link)
        print("Successfully posted with preview!")
        print("Server response:")
        print(json.dumps(response, indent=2))
    except Exception as e:
        print(f"Error while posting with preview: {e}")
        
        try:
            # Fall back to posting without preview
            response = poster.post_without_preview(text, link)
            print("Successfully posted without preview!")
            print("Server response:")
            print(json.dumps(response, indent=2))
        except Exception as e2:
            print(f"Error posting without preview: {e2}")
            print("All posting attempts failed.")