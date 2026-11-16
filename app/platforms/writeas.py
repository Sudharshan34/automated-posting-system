import httpx

from .base import Platform, PlatformError


class WriteAs(Platform):
    """Write.as: anonymous publishing API, no credentials required."""

    name = "Write.as"
    required_settings: list = []

    async def publish(self, client: httpx.AsyncClient, message: str, link: str) -> str:
        title = (message.replace(link, "").strip(" -:|") or "Update")[:100]
        r = await client.post(
            "https://write.as/api/posts",
            json={"title": title, "body": message, "font": "sans"},
        )
        r.raise_for_status()
        post_id = (r.json().get("data") or {}).get("id")
        if not post_id:
            raise PlatformError("Write.as response had no post id")
        if post_id == "contentisblocked":
            raise PlatformError("Write.as spam filter blocked the content (post was not published)")
        return f"https://write.as/{post_id}"
