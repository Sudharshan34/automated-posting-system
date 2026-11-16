"""Fan-out posting: each platform runs independently; one failure never blocks others."""
import asyncio
from datetime import datetime
from typing import List, Optional

import httpx

from app.config import Settings, get_settings
from app.platforms import Platform, PlatformError, get_platforms
from app.schemas import PlatformResult, PostingResponse


async def _verify_public(platform: Platform, client: httpx.AsyncClient, url: str,
                         attempts: int = 4, delay: float = 1.5) -> bool:
    """New posts can take a moment to appear publicly, so retry a few times."""
    for i in range(attempts):
        if await platform.is_public(client, url):
            return True
        if i < attempts - 1:
            await asyncio.sleep(delay)
    return False


CONNECT_RETRIES = 2
CONNECT_RETRY_DELAY = 1.0


async def _publish_with_retry(platform: Platform, client: httpx.AsyncClient, message: str, link: str) -> str:
    """Retry only when the connection could not be established (nothing was sent,
    so a retry cannot create a duplicate post)."""
    for attempt in range(CONNECT_RETRIES + 1):
        try:
            return await platform.publish(client, message, link)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            if attempt == CONNECT_RETRIES:
                raise
            await asyncio.sleep(CONNECT_RETRY_DELAY)


def _failed(name: str, error: str) -> PlatformResult:
    return PlatformResult(platform=name, status="failed", public_access=False, error=error)


async def _run_one(platform: Platform, client: httpx.AsyncClient, message: str, link: str) -> PlatformResult:
    missing = platform.missing_config()
    if missing:
        return _failed(platform.name, f"Missing credentials: {', '.join(missing)}")
    try:
        url = await _publish_with_retry(platform, client, message, link)
        public = await _verify_public(platform, client, url)
        now = datetime.now()
        return PlatformResult(
            platform=platform.name, status="success", posted_url=url, public_access=public,
            date=now.strftime("%Y-%m-%d"), time=now.strftime("%H:%M:%S"),
        )
    except httpx.HTTPStatusError as e:
        return _failed(platform.name, f"HTTP {e.response.status_code}: {e.response.text[:200]}")
    except httpx.TimeoutException:
        return _failed(platform.name, "Request timed out")
    except httpx.HTTPError as e:
        return _failed(platform.name, f"Network error: {type(e).__name__}: {e}".rstrip(": "))
    except PlatformError as e:
        return _failed(platform.name, str(e))
    except Exception as e:  # never let one platform crash the request
        return _failed(platform.name, f"Unexpected error: {e}")


async def post_to_all(message: str, link: str, platforms: Optional[List[Platform]] = None,
                      settings: Optional[Settings] = None) -> PostingResponse:
    settings = settings or get_settings()
    platforms = platforms if platforms is not None else get_platforms(settings)
    async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
        results = await asyncio.gather(*[_run_one(p, client, message, link) for p in platforms])
    return PostingResponse(success=any(r.status == "success" for r in results), results=list(results))
