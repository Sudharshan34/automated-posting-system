import httpx

from .base import Platform, PlatformError


class GitLabSnippet(Platform):
    """GitLab Snippets: free, public snippet per post (token needs the `api` scope)."""

    name = "GitLab Snippets"
    required_settings = ["gitlab_token"]

    async def publish(self, client: httpx.AsyncClient, message: str, link: str) -> str:
        title = (message.replace(link, "").strip(" -:|") or "Update")[:100]
        r = await client.post(
            "https://gitlab.com/api/v4/snippets",
            headers={"PRIVATE-TOKEN": self.settings.gitlab_token},
            json={
                "title": title,
                "visibility": "public",
                "files": [{"file_path": "message.md", "content": message}],
            },
        )
        r.raise_for_status()
        url = r.json().get("web_url")
        if not url:
            raise PlatformError("GitLab response had no snippet URL")
        return url
