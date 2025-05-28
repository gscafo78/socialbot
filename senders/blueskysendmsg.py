import requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

class BlueskyPoster:
    """
    A class to post messages with link previews to the Bluesky network.

    Args:
        handle (str): The Bluesky user handle (e.g., "user.bsky.social").
        app_password (str): The app password for authentication.
        service (str): The Bluesky service URL (default: "https://bsky.social").

    Methods:
        create_session(): Authenticates and stores access token and DID.
        fetch_embed_url_card(url): Fetches metadata and image for a link preview.
        create_facets(text, link): Creates link facets for the post.
        post_with_preview(text, link): Publishes a post with a link preview.
    """

    def __init__(self, handle, app_password, service='https://bsky.social'):
        self.handle = handle
        self.app_password = app_password
        self.service = service
        self.access_jwt = None
        self.did = None

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

    def fetch_embed_url_card(self, url):
        """
        Fetches metadata (title, description, image) from a URL to create a link preview card.

        Args:
            url (str): The URL to preview.

        Returns:
            dict: The Bluesky embed card structure.
        """
        card = {
            "uri": url,
            "title": "",
            "description": "",
        }
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
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
        # Extract image and upload as blob if present
        image_tag = soup.find("meta", property="og:image")
        if image_tag:
            img_url = image_tag.get("content", "")
            img_url = urljoin(url, img_url)
            img_resp = requests.get(img_url, headers={'User-Agent': 'Mozilla/5.0'})
            img_resp.raise_for_status()
            IMAGE_MIMETYPE = img_resp.headers.get("Content-Type", "image/png")
            if len(img_resp.content) <= 1000000:  # Only upload if image is <= 1MB
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
        facets = self.create_facets(text, link)
        embed = self.fetch_embed_url_card(link)
        post = {
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": now,
            "facets": facets,
            "embed": embed,
        }
        record_resp = requests.post(
            f"{self.service}/xrpc/com.atproto.repo.createRecord",
            headers={"Authorization": "Bearer " + self.access_jwt},
            json={
                "repo": self.did,
                "collection": "app.bsky.feed.post",
                "record": post,
            },
        )
        record_resp.raise_for_status()
        return record_resp.json()

# Example usage:
if __name__ == "__main__":
    # Replace these values with your Bluesky credentials and desired post
    text = "Here is the link to the Bluesky site:"
    link = "https://www.example.com"        # Replace with the URL you want to preview
    user = "gs-fanpage-bot.bsky.social"         # Your handle
    password = "Can8d1g0mm4!"              # Your app password
    service = "https://bsky.social"         # Your service URL (default: https://bsky.social)

    poster = BlueskyPoster(user, password, service)
    try:
        response = poster.post_with_preview(f"{text}\n{link}", link)
        print("Server response:")
        print(response)
    except Exception as e:
        print("Error while posting:", e)

"""
How to use this class:

1. Create an instance of BlueskyPoster with your handle, app password, and (optionally) service URL.
2. Call post_with_preview(text, link) to publish a post with a link preview.
3. Handle exceptions as needed.

Example:
    poster = BlueskyPoster("your.handle", "your-app-password")
    response = poster.post_with_preview("Check this out:", "https://example.com")
    print(response)
"""