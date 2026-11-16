import httpx

from .base import Platform, PlatformError


class Telegraph(Platform):
    """Telegraph (telegra.ph): free publishing API, public page per post."""

    name = "Telegraph"
    required_settings = ["telegraph_access_token"]

    async def publish(self, client: httpx.AsyncClient, message: str, link: str) -> str:
        before, _, after = message.partition(link)
        children = [c for c in (before, {"tag": "a", "attrs": {"href": link}, "children": [link]}, after) if c]
        title = (message.replace(link, "").strip(" -:|") or "Update")[:100]
        r = await client.post(
            "https://api.telegra.ph/createPage",
            json={
                "access_token": self.settings.telegraph_access_token,
                "title": title,
                "author_name": "Automated Posting",
                "content": [{"tag": "p", "children": children}],
            },
        )
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            raise PlatformError(data.get("error", "Telegraph API error"))
        return data["result"]["url"]
