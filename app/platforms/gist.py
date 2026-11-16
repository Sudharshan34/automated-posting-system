import httpx

from .base import Platform, PlatformError


class GitHubGist(Platform):
    """GitHub Gist: free, public gist per post (token needs the `gist` scope)."""

    name = "GitHub Gist"
    required_settings = ["github_token"]

    async def publish(self, client: httpx.AsyncClient, message: str, link: str) -> str:
        r = await client.post(
            "https://api.github.com/gists",
            headers={
                "Authorization": f"Bearer {self.settings.github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={
                "description": message,
                "public": True,
                "files": {"message.md": {"content": message}},
            },
        )
        r.raise_for_status()
        url = r.json().get("html_url")
        if not url:
            raise PlatformError("GitHub response had no gist URL")
        return url
