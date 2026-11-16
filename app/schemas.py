"""Request / response models and input validation."""
import re
from typing import List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

MAX_LENGTH = 200
URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
TRAILING_PUNCTUATION = ".,;:!?)]}\"'"


def extract_urls(text: str) -> List[str]:
    return [m.group(0).rstrip(TRAILING_PUNCTUATION) for m in URL_PATTERN.finditer(text)]


def is_valid_url(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return parsed.scheme in ("http", "https") and "." in host and not host.startswith(".") and not host.endswith(".")


class PostingRequest(BaseModel):
    message: str = Field(..., description="Message (max 200 chars) containing exactly one CTA link.")

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message must not be empty.")
        if len(value) > MAX_LENGTH:
            raise ValueError(f"Message must not exceed {MAX_LENGTH} characters (got {len(value)}).")
        urls = extract_urls(value)
        if len(urls) != 1:
            raise ValueError(f"Message must contain exactly one CTA link (found {len(urls)}).")
        if not is_valid_url(urls[0]):
            raise ValueError(f"Invalid URL: {urls[0]}")
        return value

    @property
    def link(self) -> str:
        return extract_urls(self.message)[0]


class PlatformResult(BaseModel):
    platform: str
    status: str  # "success" | "failed"
    posted_url: Optional[str] = None
    public_access: bool = False
    date: Optional[str] = None
    time: Optional[str] = None
    error: Optional[str] = None


class PostingResponse(BaseModel):
    success: bool
    results: List[PlatformResult]
