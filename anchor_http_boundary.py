"""Bound mutating requests and reject browser origins before route execution."""
from __future__ import annotations

from starlette.responses import JSONResponse


class LocalRequestBoundary:
    def __init__(self, app, *, origins: list[str], max_body: int = 1024 * 1024):
        self.app = app
        self.origins = set(origins)
        self.max_body = max_body

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] in {"GET", "HEAD", "OPTIONS"}:
            await self.app(scope, receive, send)
            return
        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        origin = headers.get(b"origin")
        if origin is not None and origin.decode("latin1") not in self.origins:
            await JSONResponse({"detail": "Browser origin is not allowed"}, status_code=403)(scope, receive, send)
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.max_body:
                await JSONResponse({"detail": "Request exceeds body limit"}, status_code=413)(scope, receive, send)
                return
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
