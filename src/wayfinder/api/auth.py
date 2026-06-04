"""Workspace authentication helpers for the Wayfinder API."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

_PASSWORD_ITERATIONS = 210_000
_TOKEN_BYTES = 32


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    workspace_id: str
    display_name: str


@dataclass(frozen=True)
class SessionToken:
    token: str
    token_hash: str
    expires_at: datetime


def normalize_workspace_id(workspace_id: str) -> str:
    normalized = workspace_id.strip().lower()
    if not normalized:
        raise ValueError("workspace_id is required")
    if len(normalized) > 64:
        raise ValueError("workspace_id must be at most 64 characters")
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-_")
    if any(character not in allowed for character in normalized):
        raise ValueError("workspace_id may only contain letters, numbers, dashes, and underscores")
    return normalized


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("password must be at least 8 characters")

    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _PASSWORD_ITERATIONS,
    )
    return "pbkdf2_sha256${iterations}${salt}${digest}".format(
        iterations=_PASSWORD_ITERATIONS,
        salt=base64.urlsafe_b64encode(salt).decode("ascii"),
        digest=base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_raw, salt_raw, digest_raw = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        salt = base64.urlsafe_b64decode(salt_raw.encode("ascii"))
        expected_digest = base64.urlsafe_b64decode(digest_raw.encode("ascii"))
    except (ValueError, TypeError):
        return False

    actual_digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual_digest, expected_digest)


def issue_session_token(*, ttl_days: int) -> SessionToken:
    token = secrets.token_urlsafe(_TOKEN_BYTES)
    return SessionToken(
        token=token,
        token_hash=hash_token(token),
        expires_at=datetime.now(UTC) + timedelta(days=ttl_days),
    )


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
