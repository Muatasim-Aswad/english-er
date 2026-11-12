"""Bound local HTTP work before acquiring database or model resources."""

import asyncio
import time
from collections import deque
from urllib.parse import urlsplit
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from english_er.config import Settings
from english_er.platform.errors import error_response
from english_er.shared.errors import AppError


class LocalHttpBoundary:
    def __init__(self, app: ASGIApp, *, settings: Settings) -> None:
        self.app = app
        self.settings = settings
        self.active = 0
        self.arrivals: deque[float] = deque()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = str(uuid4())
        scope["request_id"] = request_id
        started = False

        async def correlated_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                message["headers"] = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != b"x-request-id"
                ] + [(b"x-request-id", request_id.encode())]
            await send(message)

        admitted = False
        try:
            self._validate_headers(scope)
            self._admit()
            admitted = True
            async with asyncio.timeout(self.settings.request_timeout):
                body = await self._read_body(receive)
                replayed = False

                async def replay() -> Message:
                    nonlocal replayed
                    if replayed:
                        return await receive()
                    replayed = True
                    return {"type": "http.request", "body": body, "more_body": False}

                await self.app(scope, replay, correlated_send)
        except AppError as error:
            if not started:
                await error_response(error, request_id)(scope, receive, correlated_send)
        except TimeoutError:
            if not started:
                await error_response(
                    AppError("request_timeout", "The request timed out."), request_id
                )(scope, receive, correlated_send)
        except Exception:
            if not started:
                await error_response(
                    AppError("internal_error", "The service could not complete the request."),
                    request_id,
                )(scope, receive, correlated_send)
        finally:
            if admitted:
                self.active -= 1

    def _validate_headers(self, scope: Scope) -> None:
        headers = {key.lower(): value.decode("latin-1") for key, value in scope["headers"]}
        for name in (b"host", b"origin", b"content-length"):
            if sum(key.lower() == name for key, _value in scope["headers"]) > 1:
                raise AppError("validation_error", "Duplicate request headers are not allowed.")
        host = headers.get(b"host", "")
        try:
            parsed_host = urlsplit(f"http://{host}")
            hostname = parsed_host.hostname
            _port = parsed_host.port
        except ValueError:
            hostname = None
        if hostname not in self.settings.allowed_hosts or any(
            token in host for token in ("/", "@", "#", "?", "\\")
        ):
            raise AppError("invalid_host", "This host is not allowed.")
        origin = headers.get(b"origin")
        if origin is not None and origin not in self.settings.allowed_origins:
            raise AppError("invalid_origin", "This origin is not allowed.")
        if headers.get(b"sec-fetch-site") == "cross-site":
            raise AppError("invalid_origin", "Cross-site requests are not allowed.")
        length = headers.get(b"content-length")
        if length is not None:
            try:
                size = int(length)
            except ValueError as error:
                raise AppError("validation_error", "Invalid content length.") from error
            if size < 0 or size > self.settings.max_body_bytes:
                raise AppError("request_too_large", "The request is too large.")

    def _admit(self) -> None:
        if self.active >= self.settings.max_concurrent_requests:
            raise AppError("busy", "The local service is busy. Try again shortly.")
        now = time.monotonic()
        while self.arrivals and self.arrivals[0] <= now - 60:
            self.arrivals.popleft()
        if len(self.arrivals) >= self.settings.requests_per_minute:
            raise AppError("rate_limited", "Too many requests. Try again shortly.")
        self.arrivals.append(now)
        self.active += 1

    async def _read_body(self, receive: Receive) -> bytes:
        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                raise AppError("validation_error", "The request was interrupted.")
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.settings.max_body_bytes:
                raise AppError("request_too_large", "The request is too large.")
            chunks.append(chunk)
            if not message.get("more_body", False):
                return b"".join(chunks)
