from urllib.parse import urlparse

import httpx

from .base import Platform, PlatformError


class DevTo(Platform):
    name = "Dev.to"
    required_settings = ["devto_api_key"]

    async def is_public(self, client: httpx.AsyncClient, url: str) -> bool:
        # The public API is more reliable than scraping the HTML page.
        try:
            path = urlparse(url).path.strip("/")  # username/slug
            r = await client.get(f"https://dev.to/api/articles/{path}")
            return r.status_code == 200 and bool(r.json().get("published_at"))
        except Exception:
            return False

    async def publish(self, client: httpx.AsyncClient, message: str, link: str) -> str:
        title = message.replace(link, "").strip(" -:|") or "Update"
        title = title[:80]
        r = await client.post(
            "https://dev.to/api/articles",
            headers={"api-key": self.settings.devto_api_key},
            json={"article": {
                "title": title,
                "body_markdown": message,
                "published": True,
                "tags": ["webdev"],
            }},
        )
        r.raise_for_status()
        url = r.json().get("url")
        if not url:
            raise PlatformError("Dev.to response had no article URL")
        return url
