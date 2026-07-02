"""HTTP middleware: request context, access logs, and a stdlib rate limiter.

The rate limiter is a per-process fixed-window counter keyed by client identity.
It protects a single API process against a request flood without adding a
dependency; a multi-replica deployment should still enforce quotas at the load
balancer, but app-level protection keeps one process from being trivially
exhausted. It reads its limit from the environment on every request so it can be
toggled at runtime and in tests; when unset it is a no-op.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from collections.abc import Callable, Mapping
from threading import Lock

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from wayfinder.api.logging_config import (
    bind_request_id,
    configure_logging,
    log_event,
    new_request_id,
)

_REQUEST_ID_HEADER = "x-request-id"

EnvProvider = Callable[[], Mapping[str, str]]


class FixedWindowRateLimiter:
    """Per-client fixed-window request counter."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()

    def allow(self, client_key: str, *, limit: int, window_seconds: float, now: float) -> bool:
        if limit <= 0:
            return True
        threshold = now - window_seconds
        with self._lock:
            bucket = self._hits.setdefault(client_key, deque())
            while bucket and bucket[0] <= threshold:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True


def _rate_limit_per_minute(env: Mapping[str, str]) -> int:
    raw = env.get("WAYFINDER_RATE_LIMIT_PER_MINUTE", "").strip()
    if not raw:
        return 0
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    client = request.client
    return client.host if client is not None else "unknown"


def install_middleware(
    app: FastAPI,
    *,
    env: Mapping[str, str],
    env_provider: EnvProvider | None = None,
) -> None:
    """Register request-context, access-log, and rate-limit middleware.

    ``env`` configures logging at startup; ``env_provider`` (defaulting to the
    static ``env``) is consulted per request so the rate limit can react to
    runtime environment changes and test monkeypatching.
    """

    logger = configure_logging(env)
    limiter = FixedWindowRateLimiter()
    provide_env = env_provider or (lambda: env)

    @app.middleware("http")
    async def _request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get(_REQUEST_ID_HEADER) or new_request_id()
        bind_request_id(request_id)

        runtime_env = provide_env()
        limit = _rate_limit_per_minute(runtime_env)
        if limit > 0 and not limiter.allow(
            _client_key(request), limit=limit, window_seconds=60.0, now=time.monotonic()
        ):
            log_event(
                logger,
                logging.WARNING,
                "request rate limited",
                method=request.method,
                path=request.url.path,
                client=_client_key(request),
            )
            response: Response = JSONResponse(
                status_code=429,
                content={"detail": "rate limit exceeded"},
            )
            response.headers[_REQUEST_ID_HEADER] = request_id
            return response

        started = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            log_event(
                logger,
                logging.ERROR,
                "request failed",
                method=request.method,
                path=request.url.path,
            )
            raise
        duration_ms = round((time.monotonic() - started) * 1000, 2)
        response.headers[_REQUEST_ID_HEADER] = request_id
        log_event(
            logger,
            logging.INFO,
            "request completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response
