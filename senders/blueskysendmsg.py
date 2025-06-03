import requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import time
import json
import logging

class BlueskyPoster:
    DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    MAX_POST_LENGTH = 299  # Bluesky's character limit

    def __init__(self, handle, app_password, service='https://bsky.social', user_agent=None, logger=None):
        self.handle = handle
        self.app_password = app_password
        self.service = service
        self.access_jwt = None
        self.did = None
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT
        self.session = requests.Session()
        self.logger = logger or logging.getLogger(__name__)

    def create_session(self):
        resp = requests.post(
            f"{self.service}/xrpc/com.atproto.server.createSession",
            json={"identifier": self.handle, "password": self.app_password},
        )
        resp.raise_for_status()
        session = resp.json()
        self.access_jwt = session["accessJwt"]
        self.did = session["did"]
        self.logger.info(f"Successfully authenticated as {self.handle}")

    def create_simple_embed(self, url, title=None, description=None):
        card = {
            "uri": url,
            "title": title or "Link Preview",
            "description": description or "Visit the link for more information",
        }
        return {
            "$type": "app.bsky.embed.external",
            "external": card,
        }

    def fetch_embed_url_card(self, url, more_info=False):
        self.logger.debug(f"Attempting to fetch preview for: {url}")

        # Card base: "uri" sempre presente!
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
            # Truncate if too long
            if card["title"] and len(card["title"]) > 250:
                card["title"] = card["title"][:247] + "..."
            if not card["title"]:
                card["title"] = "Link Preview"

            if more_info:
                # Extract description
                description_tag = soup.find("meta", property="og:description")
                if description_tag:
                    card["description"] = description_tag.get("content", "")
                if not card["description"]:
                    desc_tag = soup.find("meta", attrs={"name": "description"})
                    if desc_tag:
                        card["description"] = desc_tag.get("content", "")
                if card["description"] and len(card["description"]) > 300:
                    card["description"] = card["description"][:297] + "..."

            # Estrarre immagine e upload come già fai
            image_tag = soup.find("meta", property="og:image")
            if image_tag:
                img_url = image_tag.get("content", "")
                img_url = urljoin(url, img_url)
                time.sleep(0.5)
                img_resp = self.session.get(img_url, timeout=15)
                img_resp.raise_for_status()
                IMAGE_MIMETYPE = img_resp.headers.get("Content-Type", "image/jpeg")
                if len(img_resp.content) <= 1000000:
                    self.logger.debug(f"Uploading image: {img_url}")
                    blob_resp = self.session.post(
                        f"{self.service}/xrpc/com.atproto.repo.uploadBlob",
                        headers={
                            "Content-Type": IMAGE_MIMETYPE,
                            "Authorization": "Bearer " + self.access_jwt,
                        },
                        data=img_resp.content,
                    )
                    blob_resp.raise_for_status()
                    if "blob" in blob_resp.json():
                        card["thumb"] = blob_resp.json()["blob"]
                        self.logger.info("Image uploaded successfully")
                    else:
                        self.logger.warning(f"Image upload response: {blob_resp.text}")

            self.logger.info(f"Successfully created embed with title: {card.get('title','')}")

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching URL: {e}")
            return self.create_simple_embed(url)

        return {
            "$type": "app.bsky.embed.external",
            "external": card,
        }

    def create_facets(self, text, link):
        facets = []
        for m in re.finditer(re.escape(link), text):
            byte_start = len(text[:m.start()].encode('utf-8'))
            byte_end = byte_start + len(link.encode('utf-8'))
            facets.append({
                "index": {"byteStart": byte_start, "byteEnd": byte_end},
                "features": [{
                    "$type": "app.bsky.richtext.facet#link",
                    "uri": link
                }]
            })
        return facets

    def truncate_text(self, text, max_length=None):
        max_length = max_length or self.MAX_POST_LENGTH
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."

    def post_without_preview(self, text, link):
        if not self.access_jwt or not self.did:
            self.create_session()

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        link_length = len(link) + 2
        available_chars = self.MAX_POST_LENGTH - link_length

        if available_chars <= 10:
            truncated_text = self.truncate_text(text, self.MAX_POST_LENGTH)
            full_text = truncated_text
        else:
            truncated_text = self.truncate_text(text, available_chars)
            full_text = f"{truncated_text}\n{link}"

        self.logger.debug(f"Text length: {len(full_text)} characters")
        facets = self.create_facets(full_text, link)

        post = {
            "$type": "app.bsky.feed.post",
            "text": full_text,
            "createdAt": now,
        }

        if facets:
            post["facets"] = facets

        self.logger.info("Posting without preview...")
        self.logger.debug(f"Post content: {full_text[:50]}...")

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
            self.logger.error(f"Error response: {record_resp.status_code} - {record_resp.text}")
            record_resp.raise_for_status()

        return record_resp.json()

    def post_feed(self, description, link, ai_comment=None, title=None, more_info=False):
        """
        Publishes a post to Bluesky with a link preview.
        - If ai_comment is empty or None: posts title, newline, description, newline, link (with preview)
        - If ai_comment is not empty: posts ai_comment, newline, link (with preview)
        Args:
            title (str): The title of the feed.
            description (str): The description of the feed.
            link (str): The URL to preview.
            ai_comment (str, optional): The AI-generated comment.
            more_info (bool): If True, include title/description in preview; if False, only image.
        Returns:
            dict: The server response as a dictionary.
        """
        if not self.access_jwt or not self.did:
            self.create_session()

        if ai_comment:
            text = f"{ai_comment}"
        else:
            text = f"{title or ''}\n{description}"

        truncated_text = self.truncate_text(text)
        self.logger.debug(f"Text length: {len(truncated_text)} characters")
        embed = self.fetch_embed_url_card(link, more_info=more_info)
        # facets = self.create_facets(truncated_text, link) if link in truncated_text else []
        facets = self.create_facets(truncated_text, link)

        post = {
            "$type": "app.bsky.feed.post",
            "text": truncated_text,
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "embed": embed,
        }

        if facets:
            post["facets"] = facets

        self.logger.info("Posting feed to Bluesky...")
        self.logger.debug(json.dumps(post, indent=2, default=str)[:500] + "...")

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
            self.logger.error(f"Error response: {record_resp.status_code} - {record_resp.text}")
            record_resp.raise_for_status()

        return record_resp.json()

# Example usage:
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    title = None
    text = "È stato ribattezzato come Progetto di legge della devastazione, in primo luogo dell’Amazzonia, e mai definizione è stata più calzante. Perché il Pl 2.159/2021 è davvero una delle espressioni più […]"
    link = "https://www.ilgiornale.it/news/nazionale/napoli-turista-uccisa-statuetta-lanciarla-13enne-2486551.html"
    user = "XXXXXXX.bsky.social"  # Replace with your Bluesky handle
    password = "XXXXXXXXXXX" # Replace with your Bluesky password
    service = "https://bsk.social"  # Replace with your Bluesky service URL if different

    poster = BlueskyPoster(user, password, service)
    try:
        response = poster.post_feed(description=text, link=link, title=title, more_info=False)
        print("Successfully posted with preview!")
        print("Server response:")
        print(json.dumps(response, indent=2))
    except Exception as e:
        print(f"Error while posting with preview: {e}")
        try:
            response = poster.post_without_preview(text, link)
            print("Successfully posted without preview!")
            print("Server response:")
            print(json.dumps(response, indent=2))
        except Exception as e2:
            print(f"Error posting without preview: {e2}")
            print("All posting attempts failed.")