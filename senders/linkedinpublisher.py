import requests

class LinkedInPublisher:
    """
    Class to publish posts and comments on LinkedIn using the v2 API.

    Args:
        access_token (str): OAuth2 access token with the required scopes.
    """

    def __init__(self, access_token):
        self.access_token = access_token
        self.api_url = "https://api.linkedin.com/v2"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }
        self.urn = self.get_user_urn()

    def get_user_urn(self):
        """
        Retrieves the user's URN (unique LinkedIn identifier).
        """
        response = requests.get(f"{self.api_url}/me", headers=self.headers)
        response.raise_for_status()
        return response.json()['id']

    def post_link(self, text, link):
        """
        Publishes a post with a link.

        Args:
            text (str): The text/comment to include in the post.
            link (str): The URL to share.

        Returns:
            dict: The LinkedIn API response.
        """
        payload = {
            "author": f"urn:li:person:{self.urn}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": text
                    },
                    "shareMediaCategory": "ARTICLE",
                    "media": [{
                        "status": "READY",
                        "description": {"text": text},
                        "originalUrl": link,
                        "title": {"text": text}
                    }]
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "CONNECTIONS"
            }
        }
        response = requests.post(f"{self.api_url}/ugcPosts", headers=self.headers, json=payload)
        response.raise_for_status()
        return response.json()

    def comment_on_post(self, post_urn, comment_text):
        """
        Publishes a comment on a given post.

        Args:
            post_urn (str): The URN of the post to comment on (e.g., "urn:li:share:POST_ID").
            comment_text (str): The comment text.

        Returns:
            dict: The LinkedIn API response.
        """
        payload = {
            "actor": f"urn:li:person:{self.urn}",
            "message": {"text": comment_text}
        }
        response = requests.post(
            f"{self.api_url}/ugcPosts/{post_urn}/comments",
            headers=self.headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()

# Example usage:
if __name__ == "__main__":
    ACCESS_TOKEN = "AQV0Sz9fSXAIuRsrIrGlQytW0tA4xp_qR-z1xRWwCLUD_UZ1x_o-rCIQFIbqQ_aOcEKvtD9HUFxXwTK8naF19Y5aArFTU0WgasPD-CKQY_bWBRh4wXegkQwcaiQWk0XwLtuCD8TMwDhbu0he9JHvuU4gLDIZisYvfV8Qqcj0BRUsa5bd-biJp62C64SagAIVi4NtKrcrSCwBjVTcGUJssilxwTopeEAdGnRTiUF6IgBikP3-m7p0J5QEFMInLzePyxobizfGpRthyv2W_c2JqrX9MzGGpmQmVA599S7Uy-OghDkkK8BT_Oc_-g2rZzwMeQTeOp4hO9_7Uihvi4DbVuseLqadDg"  # Replace with your valid LinkedIn access token

    publisher = LinkedInPublisher(ACCESS_TOKEN)

    # 1. Publish a post with a link
    try:
        print("Publishing a post with a link...")
        post_response = publisher.post_link(
            text="Check out this interesting article!",
            link="https://www.example.com/article"
        )
        print("Post published:", post_response)
        post_urn = post_response.get("id") or post_response.get("urn")  # Save the post URN for commenting
    except Exception as e:
        print("Error publishing post:", e)
        post_urn = None

    # 2. Comment on the post (if published successfully)
    if post_urn:
        try:
            print("Commenting on the post...")
            comment_response = publisher.comment_on_post(post_urn, "This is a test comment!")
            print("Comment published:", comment_response)
        except Exception as e:
            print("Error commenting on post:", e)