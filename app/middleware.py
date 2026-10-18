import asyncio
import json
import os
import time
from collections import deque

MAX_JSON_BODY_BYTES = 1_500_000
MAX_MULTIPART_BODY_BYTES = 6_000_000
MAX_DRAIN_BYTES = 2_000_000
DRAIN_TIMEOUT_SECONDS = 5.0
MAX_RATE_LIMIT_KEYS = 10_000

RATE_LIMIT_REQUESTS = 60
RATE_LIMIT_WINDOW_SECONDS = 60.0

TRUST_PROXY = os.environ.get("TRUST_PROXY", "").strip().lower() in {
    "1",
    "true",
    "yes",
}

PAYLOAD_TOO_LARGE_MESSAGE = (
    "This request is too large to process. Send less text or a smaller file "
    "and try again."
)
RATE_LIMITED_MESSAGE = "Too many requests. Please wait a moment and try again."


def _request_id(scope):
    state = scope.get("state") or {}
    return state.get("request_id") or "unknown"


def _json_response(status_code, code, message, scope, extra_headers=None):
    body = json.dumps(
        {
            "detail": {"code": code, "message": message},
            "request_id": _request_id(scope),
        }
    ).encode("utf-8")
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode()),
    ]
    for name, value in (extra_headers or {}).items():
        headers.append((name.encode(), value.encode()))
    return status_code, headers, body


class BodyTooLarge(Exception):
    pass


class BodyLimitMiddleware:
    def __init__(
        self,
        app,
        json_limit=MAX_JSON_BODY_BYTES,
        multipart_limit=MAX_MULTIPART_BODY_BYTES,
    ):
        self.app = app
        self.json_limit = json_limit
        self.multipart_limit = multipart_limit

    def _limit_for(self, scope):
        content_type = ""
        for name, value in scope.get("headers", []):
            if name == b"content-type":
                content_type = value.decode("latin-1").lower()
                break
        if content_type.startswith("multipart/form-data"):
            return self.multipart_limit
        return self.json_limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limit = self._limit_for(scope)

        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    continue
                if declared > limit:
                    await self._drain(receive)
                    await self._reject(scope, send)
                    return

        received = 0
        stream_complete = False

        async def limited_receive():
            nonlocal received, stream_complete
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if not message.get("more_body", False):
                    stream_complete = True
                if received > limit:
                    raise BodyTooLarge()
            return message

        try:
            await self.app(scope, limited_receive, send)
        except BodyTooLarge:
            if not stream_complete:
                await self._drain(receive)
            await self._reject(scope, send)

    async def _drain(self, receive):
        async def consume():
            total = 0
            while total <= MAX_DRAIN_BYTES:
                message = await receive()
                if message["type"] != "http.request":
                    return
                total += len(message.get("body", b""))
                if not message.get("more_body", False):
                    return

        try:
            await asyncio.wait_for(consume(), timeout=DRAIN_TIMEOUT_SECONDS)
        except Exception:
            return

    async def _reject(self, scope, send):
        status_code, headers, body = _json_response(
            413, "payload_too_large", PAYLOAD_TOO_LARGE_MESSAGE, scope
        )
        await send(
            {"type": "http.response.start", "status": status_code, "headers": headers}
        )
        await send({"type": "http.response.body", "body": body})


class RateLimitMiddleware:
    def __init__(
        self,
        app,
        max_requests=RATE_LIMIT_REQUESTS,
        window_seconds=RATE_LIMIT_WINDOW_SECONDS,
    ):
        self.app = app
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") not in {
            "POST",
            "PUT",
            "PATCH",
        }:
            await self.app(scope, receive, send)
            return

        key = _client_key(scope)

        if is_rate_limited(key, self.max_requests, self.window_seconds):
            status_code, headers, body = _json_response(
                429,
                "rate_limited",
                RATE_LIMITED_MESSAGE,
                scope,
                extra_headers={
                    "retry-after": str(int(self.window_seconds)),
                },
            )
            await send(
                {
                    "type": "http.response.start",
                    "status": status_code,
                    "headers": headers,
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        await self.app(scope, receive, send)


def _client_key(scope):
    if TRUST_PROXY:
        for name, value in scope.get("headers", []):
            if name == b"x-forwarded-for":
                forwarded = value.decode("latin-1").split(",")[0].strip()
                if forwarded:
                    return forwarded
    client = scope.get("client")
    return client[0] if client else "unknown"


_hits = {}


def _prune_hits(now, window_seconds):
    if len(_hits) <= MAX_RATE_LIMIT_KEYS:
        return
    stale = [
        key
        for key, entries in _hits.items()
        if not entries or now - entries[-1] > window_seconds
    ]
    for key in stale:
        _hits.pop(key, None)


def is_rate_limited(
    key, max_requests=RATE_LIMIT_REQUESTS, window_seconds=RATE_LIMIT_WINDOW_SECONDS
):
    now = time.monotonic()
    _prune_hits(now, window_seconds)
    entries = _hits.setdefault(key, deque())
    while entries and now - entries[0] > window_seconds:
        entries.popleft()
    if len(entries) >= max_requests:
        return True
    entries.append(now)
    return False


def reset_rate_limits():
    _hits.clear()
