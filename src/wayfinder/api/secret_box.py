"""Small stdlib-only secret envelope for workspace runtime keys."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

_VERSION_PREFIX = "v1:"
_NONCE_BYTES = 16
_TAG_BYTES = 32


def encrypt_secret(plaintext: str, key_material: str) -> str:
    if not key_material.strip():
        raise ValueError("key material is required")
    if plaintext == "":
        raise ValueError("secret must not be empty")

    nonce = os.urandom(_NONCE_BYTES)
    plaintext_bytes = plaintext.encode("utf-8")
    ciphertext = _xor_bytes(plaintext_bytes, _keystream(key_material, nonce, len(plaintext_bytes)))
    tag = _tag(key_material, nonce + ciphertext)
    return _VERSION_PREFIX + base64.urlsafe_b64encode(nonce + ciphertext + tag).decode("ascii")


def decrypt_secret(envelope: str, key_material: str) -> str:
    if not key_material.strip():
        raise ValueError("key material is required")
    if not envelope.startswith(_VERSION_PREFIX):
        raise ValueError("unsupported secret envelope")

    try:
        payload = base64.urlsafe_b64decode(envelope[len(_VERSION_PREFIX) :].encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise ValueError("invalid secret envelope") from exc

    if len(payload) <= _NONCE_BYTES + _TAG_BYTES:
        raise ValueError("invalid secret envelope")

    nonce = payload[:_NONCE_BYTES]
    ciphertext = payload[_NONCE_BYTES:-_TAG_BYTES]
    expected_tag = payload[-_TAG_BYTES:]
    actual_tag = _tag(key_material, nonce + ciphertext)
    if not hmac.compare_digest(expected_tag, actual_tag):
        raise ValueError("secret envelope authentication failed")

    plaintext = _xor_bytes(ciphertext, _keystream(key_material, nonce, len(ciphertext)))
    return plaintext.decode("utf-8")


def _tag(key_material: str, payload: bytes) -> bytes:
    return hmac.new(_derive_key(key_material, "mac"), payload, hashlib.sha256).digest()


def _keystream(key_material: str, nonce: bytes, length: int) -> bytes:
    encryption_key = _derive_key(key_material, "enc")
    chunks: list[bytes] = []
    counter = 0
    while sum(len(chunk) for chunk in chunks) < length:
        counter_bytes = counter.to_bytes(4, "big")
        chunks.append(hashlib.sha256(encryption_key + nonce + counter_bytes).digest())
        counter += 1
    return b"".join(chunks)[:length]


def _derive_key(key_material: str, purpose: str) -> bytes:
    payload = f"wayfinder:{purpose}:".encode("ascii") + key_material.encode("utf-8")
    return hashlib.sha256(payload).digest()


def _xor_bytes(left: bytes, right: bytes) -> bytes:
    return bytes(left_byte ^ right_byte for left_byte, right_byte in zip(left, right, strict=True))
