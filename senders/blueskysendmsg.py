from atproto import Client, exceptions

class BlueskyPublisher:
    """
    Class to publish a post on Bluesky using atproto Client.

    Args:
        handle (str): Your Bluesky handle, e.g. "username.bsky.social".
        password (str): Your Bluesky password.
        service (str, optional): The Bluesky service URL. Default is 'https://bsky.social'.
    """

    def __init__(self, handle, password, service='https://bsky.social'):
        self.client = Client(base_url=service)
        try:
            self.client.login(handle, password)
        except exceptions.UnauthorizedError:
            raise ValueError("Authentication failed: invalid handle or password.")
        except Exception as e:
            raise ValueError(f"An unexpected error occurred during login: {e}")

    def publish_post(self, text):
        """
        Publishes a post to Bluesky.

        Args:
            text (str): The text content of the post.

        Returns:
            dict: The JSON response from the Bluesky API.
        """
        try:
            post = self.client.send_post(text)
            return post
        except exceptions.UnauthorizedError:
            return {"error": "Authentication required. Please check your credentials."}
        except Exception as e:
            return {"error": f"An error occurred while publishing the post: {e}"}

def main():
    """
    Example usage:
    Publishes a test post to Bluesky and prints the API response.

    Args:
        handle (str): Your Bluesky handle, e.g. "username.bsky.social".
        password (str): Your Bluesky password.
        service (str): The Bluesky service URL.
        message (str): The text content of the post to publish.
    """
    handle = "gscafo78.bsky.social"               # Replace with your handle
    password = "xxxxxxxxxxxx"                     # Replace with your password
    service = "https://bsky.social"               # Replace with your service URL
    message = "Hello, this is an automatic test with atproto!"
    try:
        publisher = BlueskyPublisher(handle, password, service)
        response = publisher.publish_post(message)
        print("Bluesky API response:", response)
    except ValueError as e:
        print(f"Login failed: {e}")

if __name__ == "__main__":
    main()