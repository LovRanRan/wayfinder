"""Structured logging and request-context helpers for the API.

Enterprise deployments need machine-parseable logs that can be correlated with a
single request and the run/job it started. This module provides an opt-in JSON
formatter (``WAYFINDER_LOG_FORMAT=json``) and a per-request id that is bound to a
``contextvars`` slot so any log emitted while handling a request carries the same
``request_id`` without threading it through every call.
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from collections.abc import Mapping
from contextvars import ContextVar
from typing import Any

_REQUEST_ID: ContextVar[str] = ContextVar("wayfinder_request_id", default="-")

_LOGGER_NAME = "wayfinder.api"
_configured = False


def new_request_id() -> str:
    return uuid.uuid4().hex


def bind_request_id(request_id: str) -> None:
    _REQUEST_ID.set(request_id)


def current_request_id() -> str:
    return _REQUEST_ID.get()


class _JsonLogFormatter(logging.Formatter):
    """Render log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", current_request_id()),
        }
        extra_fields = getattr(record, "extra_fields", None)
        if isinstance(extra_fields, Mapping):
            for key, value in extra_fields.items():
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(env: Mapping[str, str]) -> logging.Logger:
    """Configure and return the API logger. Idempotent across calls."""

    global _configured
    logger = logging.getLogger(_LOGGER_NAME)
    if _configured:
        return logger

    handler = logging.StreamHandler(sys.stderr)
    if env.get("WAYFINDER_LOG_FORMAT", "").strip().lower() == "json":
        handler.setFormatter(_JsonLogFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(levelname)s %(name)s [%(request_id)s] %(message)s")
        )
        handler.addFilter(_RequestIdFilter())

    level_name = env.get("WAYFINDER_LOG_LEVEL", "INFO").strip().upper()
    logger.setLevel(getattr(logging, level_name, logging.INFO))
    logger.handlers = [handler]
    logger.propagate = False
    _configured = True
    return logger


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = current_request_id()
        return True


def log_event(logger: logging.Logger, level: int, message: str, **fields: Any) -> None:
    """Emit a log line with structured fields and the active request id."""

    logger.log(
        level,
        message,
        extra={"request_id": current_request_id(), "extra_fields": fields},
    )
