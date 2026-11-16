"""Base class every platform integration implements."""
from abc import ABC, abstractmethod
from typing import List

import httpx

from app.config import Settings


class PlatformError(Exception):
    """Raised when a platform rejects or fails a post."""


class Platform(ABC):
    name: str = "base"
    # Names of Settings attributes that must be non-empty for this platform.
    required_settings: List[str] = []

    def __init__(self, settings: Settings):
        self.settings = settings

    def missing_config(self) -> List[str]:
        return [k.upper() for k in self.required_settings if not getattr(self.settings, k)]

    async def is_public(self, client: httpx.AsyncClient, url: str) -> bool:
        """Best-effort check that the post is reachable without authentication."""
        try:
            r = await client.get(url, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
            return r.status_code < 400
        except Exception:
            return False

    @abstractmethod
    async def publish(self, client: httpx.AsyncClient, message: str, link: str) -> str:
        """Publish the message and return the public URL of the post."""
