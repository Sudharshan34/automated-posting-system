import httpx

from .base import Platform, PlatformError


class Mastodon(Platform):
    name = "Mastodon"
    required_settings = ["mastodon_instance_url", "mastodon_access_token"]

    async def publish(self, client: httpx.AsyncClient, message: str, link: str) -> str:
        s = self.settings
        r = await client.post(
            f"{s.mastodon_instance_url}/api/v1/statuses",
            headers={"Authorization": f"Bearer {s.mastodon_access_token}"},
            json={"status": message, "visibility": "public"},
        )
        r.raise_for_status()
        url = r.json().get("url")
        if not url:
            raise PlatformError("Mastodon response had no post URL")
        return url
