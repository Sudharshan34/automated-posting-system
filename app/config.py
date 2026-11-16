"""Configuration loaded from environment variables (.env supported)."""
import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    mastodon_instance_url: str = ""
    mastodon_access_token: str = ""
    bluesky_handle: str = ""
    bluesky_app_password: str = ""
    devto_api_key: str = ""
    hashnode_token: str = ""
    hashnode_publication_id: str = ""
    telegram_bot_token: str = ""
    telegram_channel: str = ""
    telegraph_access_token: str = ""
    github_token: str = ""
    gitlab_token: str = ""
    request_timeout: float = 20.0


@lru_cache
def get_settings() -> Settings:
    g = lambda k: os.getenv(k, "").strip()  # noqa: E731
    return Settings(
        mastodon_instance_url=g("MASTODON_INSTANCE_URL").rstrip("/"),
        mastodon_access_token=g("MASTODON_ACCESS_TOKEN"),
        bluesky_handle=g("BLUESKY_HANDLE"),
        bluesky_app_password=g("BLUESKY_APP_PASSWORD"),
        devto_api_key=g("DEVTO_API_KEY"),
        hashnode_token=g("HASHNODE_TOKEN"),
        hashnode_publication_id=g("HASHNODE_PUBLICATION_ID"),
        telegram_bot_token=g("TELEGRAM_BOT_TOKEN"),
        telegram_channel=g("TELEGRAM_CHANNEL"),
        telegraph_access_token=g("TELEGRAPH_ACCESS_TOKEN"),
        github_token=g("GITHUB_TOKEN"),
        gitlab_token=g("GITLAB_TOKEN"),
    )
