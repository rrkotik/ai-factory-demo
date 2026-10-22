"""Bound product image uploads before FastAPI buffers and parses the JSON body."""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

MAX_PRODUCT_BODY_BYTES = 32 * 1024 * 1024


class ProductBodyLimit:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or scope.get("path", "").rstrip("/") != "/products/verify"
        ):
            await self.app(scope, receive, send)
            return
        messages: list[Message] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > MAX_PRODUCT_BODY_BYTES:
                response = JSONResponse(
                    status_code=422,
                    content={"detail": "Product request body must be at most 32 MiB."},
                )
                await response(scope, receive, send)
                return
            messages.append(message)
            if not message.get("more_body", False):
                break
        buffered = iter(messages)

        async def replay() -> Message:
            message = next(buffered, None)
            return message if message is not None else await receive()

        await self.app(scope, replay, send)
