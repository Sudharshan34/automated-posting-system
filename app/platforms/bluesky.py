from datetime import datetime, timezone

import httpx

from .base import Platform, PlatformError

PDS = "https://bsky.social"


class Bluesky(Platform):
    name = "Bluesky"
    required_settings = ["bluesky_handle", "bluesky_app_password"]
    _record_uri = ""

    async def is_public(self, client: httpx.AsyncClient, url: str) -> bool:
        # bsky.app is a JS app that can block scripted requests, so verify through
        # unauthenticated AT Protocol endpoints instead. Reading the record straight
        # from the user's repo is immediate; the AppView index can lag a few seconds.
        try:
            parts = self._record_uri.removeprefix("at://").split("/")
            if len(parts) == 3:
                repo, collection, rkey = parts
                r = await client.get(
                    f"{PDS}/xrpc/com.atproto.repo.getRecord",
                    params={"repo": repo, "collection": collection, "rkey": rkey},
                )
                if r.status_code == 200:
                    return True
            r = await client.get(
                "https://public.api.bsky.app/xrpc/app.bsky.feed.getPostThread",
                params={"uri": self._record_uri, "depth": 0},
            )
            return r.status_code == 200
        except Exception:
            return False

    async def publish(self, client: httpx.AsyncClient, message: str, link: str) -> str:
        s = self.settings
        auth = await client.post(
            f"{PDS}/xrpc/com.atproto.server.createSession",
            json={"identifier": s.bluesky_handle, "password": s.bluesky_app_password},
        )
        auth.raise_for_status()
        session = auth.json()

        record = {
            "$type": "app.bsky.feed.post",
            "text": message,
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        # Make the CTA link clickable (facets use UTF-8 byte offsets).
        idx = message.find(link)
        if idx != -1:
            start = len(message[:idx].encode("utf-8"))
            record["facets"] = [{
                "index": {"byteStart": start, "byteEnd": start + len(link.encode("utf-8"))},
                "features": [{"$type": "app.bsky.richtext.facet#link", "uri": link}],
            }]

        r = await client.post(
            f"{PDS}/xrpc/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {session['accessJwt']}"},
            json={"repo": session["did"], "collection": "app.bsky.feed.post", "record": record},
        )
        r.raise_for_status()
        uri = r.json().get("uri", "")
        if not uri:
            raise PlatformError("Bluesky response had no record URI")
        self._record_uri = uri
        rkey = uri.rsplit("/", 1)[-1]
        return f"https://bsky.app/profile/{session.get('handle', s.bluesky_handle)}/post/{rkey}"
