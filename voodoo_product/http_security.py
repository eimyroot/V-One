from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

CONTENT_SECURITY_POLICY = (
    "default-src 'none'; "
    "base-uri 'none'; "
    "connect-src 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "img-src 'self' data:; "
    "manifest-src 'self'; "
    "object-src 'none'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "worker-src 'none'"
)

_BASE_HEADERS = (
    (b"cache-control", b"no-store"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"cross-origin-resource-policy", b"same-origin"),
    (b"permissions-policy", b"camera=(), geolocation=(), microphone=(), payment=(), usb=()"),
    (b"referrer-policy", b"no-referrer"),
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
)
_CONTENT_SECURITY_POLICY_HEADER = (
    b"content-security-policy",
    CONTENT_SECURITY_POLICY.encode("ascii"),
)
_HSTS_HEADER = (b"strict-transport-security", b"max-age=31536000")


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, *, enable_hsts: bool):
        self.app = app
        self.headers = (*_BASE_HEADERS, *([_HSTS_HEADER] if enable_hsts else []))
        self.header_names = {name for name, _ in self.headers}
        self.header_names.add(_CONTENT_SECURITY_POLICY_HEADER[0])

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path", ""))

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() not in self.header_names
                ]
                headers.extend(self.headers)
                if path == "/" or path.startswith(("/api/", "/console")):
                    headers.append(_CONTENT_SECURITY_POLICY_HEADER)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_security_headers)
