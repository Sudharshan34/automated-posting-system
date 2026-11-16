import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.platforms.base import Platform, PlatformError
from app.services import posting_service

client = TestClient(app)
VALID = "Check out our latest platform and grow your visibility. https://example.com"


# ---------- validation ----------
def test_empty_message_rejected():
    assert client.post("/posting", json={"message": "  "}).status_code == 422


def test_too_long_rejected():
    msg = "a" * 190 + " https://example.com"
    assert client.post("/posting", json={"message": msg}).status_code == 422


def test_no_link_rejected():
    assert client.post("/posting", json={"message": "no link here"}).status_code == 422


def test_two_links_rejected():
    msg = "see https://a.com and https://b.com"
    assert client.post("/posting", json={"message": msg}).status_code == 422


def test_invalid_url_rejected():
    assert client.post("/posting", json={"message": "visit https://nodot now"}).status_code == 422


def test_missing_field_rejected():
    assert client.post("/posting", json={}).status_code == 422


# ---------- fan-out / isolation ----------
class OkPlatform(Platform):
    name = "Ok"

    async def publish(self, client, message, link):
        return "https://example.com/post/1"


class BoomPlatform(Platform):
    name = "Boom"

    async def publish(self, client, message, link):
        raise PlatformError("Authentication failed")


class CrashPlatform(Platform):
    name = "Crash"

    async def publish(self, client, message, link):
        raise RuntimeError("kaboom")


class NoCredsPlatform(Platform):
    name = "NoCreds"
    required_settings = ["devto_api_key"]

    async def publish(self, client, message, link):
        return "x"


@pytest.fixture(autouse=True)
def no_network_public_check(monkeypatch):
    async def fake(client, url):
        return True
    monkeypatch.setattr(Platform, "is_public", lambda self, client, url: fake(client, url))


@pytest.mark.asyncio
async def test_one_failure_does_not_stop_others():
    s = Settings()
    platforms = [BoomPlatform(s), OkPlatform(s), CrashPlatform(s), NoCredsPlatform(s)]
    resp = await posting_service.post_to_all(VALID, "https://example.com", platforms, s)
    by = {r.platform: r for r in resp.results}
    assert resp.success is True
    assert by["Ok"].status == "success" and by["Ok"].posted_url and by["Ok"].public_access
    assert by["Ok"].date and by["Ok"].time
    assert by["Boom"].status == "failed" and by["Boom"].error == "Authentication failed"
    assert by["Crash"].status == "failed" and "kaboom" in by["Crash"].error
    assert "DEVTO_API_KEY" in by["NoCreds"].error


@pytest.mark.asyncio
async def test_all_fail_means_success_false():
    s = Settings()
    resp = await posting_service.post_to_all(VALID, "https://example.com", [BoomPlatform(s)], s)
    assert resp.success is False


# ---------- Hashnode redirect handling ----------
import httpx  # noqa: E402
from app.platforms.hashnode import Hashnode  # noqa: E402


@pytest.mark.asyncio
async def test_hashnode_follows_post_redirect():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(301, headers={"location": "https://gql.hashnode.com/graphql"})
        assert request.method == "POST" and request.content  # body preserved
        return httpx.Response(200, json={"data": {"publishPost": {"post": {"url": "https://x.hashnode.dev/p"}}}})

    s = Settings(hashnode_token="t", hashnode_publication_id="p")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        url = await Hashnode(s).publish(c, "Hello world https://example.com", "https://example.com")
    assert url == "https://x.hashnode.dev/p" and len(calls) == 2


@pytest.mark.asyncio
async def test_hashnode_refuses_untrusted_redirect():
    handler = lambda req: httpx.Response(301, headers={"location": "https://evil.example.com/"})  # noqa: E731
    s = Settings(hashnode_token="t", hashnode_publication_id="p")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        with pytest.raises(PlatformError):
            await Hashnode(s).publish(c, "Hello world https://example.com", "https://example.com")


# ---------- Telegraph / Gist payloads ----------
from app.platforms.gist import GitHubGist  # noqa: E402
from app.platforms.telegraph import Telegraph  # noqa: E402


@pytest.mark.asyncio
async def test_telegraph_builds_page_and_returns_url():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "result": {"url": "https://telegra.ph/x-11-16"}})

    s = Settings(telegraph_access_token="tok")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        url = await Telegraph(s).publish(c, "Hi there https://example.com", "https://example.com")
    assert url == "https://telegra.ph/x-11-16"
    assert seen["content"][0]["children"][1]["attrs"]["href"] == "https://example.com"


@pytest.mark.asyncio
async def test_gist_returns_html_url_and_is_public():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json
        seen.update(json.loads(request.content))
        return httpx.Response(201, json={"html_url": "https://gist.github.com/u/abc"})

    s = Settings(github_token="tok")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        url = await GitHubGist(s).publish(c, "Hi https://example.com", "https://example.com")
    assert url == "https://gist.github.com/u/abc" and seen["public"] is True


# ---------- Write.as / Bluesky verification ----------
from app.platforms.bluesky import Bluesky  # noqa: E402
from app.platforms.writeas import WriteAs  # noqa: E402


@pytest.mark.asyncio
async def test_writeas_returns_public_url():
    handler = lambda req: httpx.Response(201, json={"code": 201, "data": {"id": "abc123"}})  # noqa: E731
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        url = await WriteAs(Settings()).publish(c, "Hi https://example.com", "https://example.com")
    assert url == "https://write.as/abc123"
    assert WriteAs(Settings()).missing_config() == []


@pytest.mark.asyncio
async def test_bluesky_public_check_reads_repo_record():
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(str(req.url))
        return httpx.Response(200, json={"uri": "x"})

    b = Bluesky(Settings())
    b._record_uri = "at://did:plc:abc/app.bsky.feed.post/3kxyz"
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        assert await b.is_public(c, "https://bsky.app/profile/h/post/3kxyz") is True
    assert "com.atproto.repo.getRecord" in seen[0] and "rkey=3kxyz" in seen[0]


# ---------- GitLab / Write.as blocked ----------
from app.platforms.gitlab import GitLabSnippet  # noqa: E402


@pytest.mark.asyncio
async def test_gitlab_snippet_public_and_url():
    import json
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen.update(json.loads(req.content))
        seen["token"] = req.headers.get("private-token")
        return httpx.Response(201, json={"web_url": "https://gitlab.com/-/snippets/1"})

    s = Settings(gitlab_token="tok")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        url = await GitLabSnippet(s).publish(c, "Hi https://example.com", "https://example.com")
    assert url == "https://gitlab.com/-/snippets/1"
    assert seen["visibility"] == "public" and seen["token"] == "tok"


@pytest.mark.asyncio
async def test_writeas_blocked_content_is_reported_as_failure():
    handler = lambda req: httpx.Response(201, json={"data": {"id": "contentisblocked"}})  # noqa: E731
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        with pytest.raises(PlatformError):
            await WriteAs(Settings()).publish(c, "Hi https://example.com", "https://example.com")


# ---------- connection retry ----------
class FlakyPlatform(Platform):
    name = "Flaky"

    def __init__(self, settings, fail_times):
        super().__init__(settings)
        self.calls, self.fail_times = 0, fail_times

    async def publish(self, client, message, link):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise httpx.ConnectError("")
        return "https://example.com/post/9"


@pytest.mark.asyncio
async def test_connect_error_is_retried_then_succeeds(monkeypatch):
    monkeypatch.setattr(posting_service, "CONNECT_RETRY_DELAY", 0)
    s = Settings()
    p = FlakyPlatform(s, fail_times=2)
    resp = await posting_service.post_to_all(VALID, "https://example.com", [p], s)
    assert resp.results[0].status == "success" and p.calls == 3


@pytest.mark.asyncio
async def test_connect_error_gives_named_error_after_retries(monkeypatch):
    monkeypatch.setattr(posting_service, "CONNECT_RETRY_DELAY", 0)
    s = Settings()
    p = FlakyPlatform(s, fail_times=99)
    resp = await posting_service.post_to_all(VALID, "https://example.com", [p], s)
    assert resp.results[0].status == "failed" and "ConnectError" in resp.results[0].error
