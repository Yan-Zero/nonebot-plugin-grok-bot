from starlette.types import ASGIApp, Receive, Scope, Send


class BearerAuth:
    """校验 `Authorization: Bearer <token>`，不匹配时返回 401"""

    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app = app
        self.expected = f"Bearer {token}".encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and dict(scope["headers"]).get(b"authorization") != self.expected:
            await send({"type": "http.response.start", "status": 401, "headers": []})
            await send({"type": "http.response.body", "body": b"Unauthorized"})
            return
        await self.app(scope, receive, send)
