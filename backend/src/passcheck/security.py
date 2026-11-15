"""Security headers and log redaction."""

from __future__ import annotations

import logging
import re

from starlette.types import ASGIApp, Message, Receive, Scope, Send

CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "manifest-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
        "frame-ancestors 'none'",
    ]
)

SECURITY_HEADERS: list[tuple[bytes, bytes]] = [
    (b"content-security-policy", CSP.encode()),
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
]


class SecurityHeadersMiddleware:
    """Pure ASGI middleware (works with streaming responses)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers: list[tuple[bytes, bytes]] = list(message.get("headers", []))
                existing = {k.lower() for k, _ in headers}
                headers.extend((k, v) for k, v in SECURITY_HEADERS if k not in existing)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


_KEY_RE = re.compile(r"((?:api)?key=)[^&\s'\"]+", re.IGNORECASE)


def redact(text: str) -> str:
    return _KEY_RE.sub(r"\1REDACTED", text)


class RedactingFilter(logging.Filter):
    """Rewrites ``key=...`` / ``apiKey=...`` in every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Format first so keys passed as %-args are redacted too, then freeze the message.
        try:
            message = record.getMessage()
        except (TypeError, ValueError):
            message = str(record.msg)
        record.msg = redact(message)
        record.args = None
        return True


def configure_logging(level: str) -> None:
    root = logging.getLogger()
    if not any(isinstance(f, RedactingFilter) for f in root.filters):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        handler.addFilter(RedactingFilter())
        root.addHandler(handler)
        root.addFilter(RedactingFilter())
    root.setLevel(level.upper())
    # httpx logs full request URLs (including ?apiKey=) at INFO.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
