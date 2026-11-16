from typing import List

from app.config import Settings

from .base import Platform, PlatformError
from .bluesky import Bluesky
from .devto import DevTo
from .gist import GitHubGist
from .gitlab import GitLabSnippet
from .mastodon import Mastodon
from .telegram import Telegram
from .telegraph import Telegraph

__all__ = ["Platform", "PlatformError", "get_platforms"]


def get_platforms(settings: Settings) -> List[Platform]:
    """Platform selection is handled internally, not by the API caller.

    Not registered (modules kept for reference):
      - hashnode.py: Hashnode's GraphQL API now requires a paid Pro plan.
      - writeas.py:  Write.as's spam filter blocks anonymous posts containing links.
    """
    return [cls(settings) for cls in (Mastodon, Bluesky, DevTo, Telegram, Telegraph, GitHubGist, GitLabSnippet)]
