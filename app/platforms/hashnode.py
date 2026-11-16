from urllib.parse import urljoin, urlparse

import httpx

from .base import Platform, PlatformError

ENDPOINT = "https://gql.hashnode.com/"
MAX_REDIRECTS = 3
MUTATION = """
mutation PublishPost($input: PublishPostInput!) {
  publishPost(input: $input) { post { url } }
}
"""


class Hashnode(Platform):
    name = "Hashnode"
    required_settings = ["hashnode_token", "hashnode_publication_id"]

    async def _post_following_redirects(self, client: httpx.AsyncClient, payload: dict) -> httpx.Response:
        """POST to the GraphQL endpoint, re-sending the POST if Hashnode redirects.

        httpx would turn a 301 POST into a GET and drop the body, so redirects are
        handled manually. The token is only re-sent to hashnode.com hosts.
        """
        url = ENDPOINT
        headers = {"Authorization": self.settings.hashnode_token}
        for _ in range(MAX_REDIRECTS + 1):
            r = await client.post(url, headers=headers, json=payload)
            if r.status_code in (301, 302, 307, 308) and r.headers.get("location"):
                url = urljoin(url, r.headers["location"])
                host = urlparse(url).hostname or ""
                if not (host == "hashnode.com" or host.endswith(".hashnode.com")):
                    raise PlatformError(f"Refusing redirect to untrusted host: {host}")
                continue
            return r
        raise PlatformError("Too many redirects from Hashnode")

    async def publish(self, client: httpx.AsyncClient, message: str, link: str) -> str:
        s = self.settings
        title = (message.replace(link, "").strip(" -:|") or "Update")[:80]
        if len(title) < 6:
            title = f"Update: {title}"
        r = await self._post_following_redirects(client, {
            "query": MUTATION,
            "variables": {"input": {
                "title": title,
                "contentMarkdown": message,
                "publicationId": s.hashnode_publication_id,
            }},
        })
        if r.status_code >= 300:
            loc = r.headers.get("location", "")
            raise PlatformError(f"HTTP {r.status_code} from Hashnode {('-> ' + loc) if loc else ''}".strip())
        data = r.json()
        if data.get("errors"):
            raise PlatformError(data["errors"][0].get("message", "Hashnode GraphQL error"))
        url = (((data.get("data") or {}).get("publishPost") or {}).get("post") or {}).get("url")
        if not url:
            raise PlatformError("Hashnode response had no post URL")
        return url
