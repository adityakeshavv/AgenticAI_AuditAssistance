from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any


PBKDF2_ALGORITHM = "sha256"
PBKDF2_ITERATIONS = 390_000
PBKDF2_SALT_BYTES = 16


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def hash_password(password: str, *, salt: bytes | None = None) -> tuple[str, str]:
    """Return (salt_hex, password_hash_hex) using PBKDF2-HMAC."""
    if salt is None:
        salt = secrets.token_bytes(PBKDF2_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return salt.hex(), digest.hex()


def verify_password(password: str, *, salt_hex: str, password_hash_hex: str) -> bool:
    try:
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    _salt_hex, digest_hex = hash_password(password, salt=salt)
    return hmac.compare_digest(digest_hex, password_hash_hex)


def create_signed_token(
    payload: dict[str, Any],
    *,
    secret: str,
) -> str:
    """Create a compact HMAC-signed token for auth/session state."""
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    body_part = _b64encode(body)
    signature = hmac.new(secret.encode("utf-8"), body_part.encode("ascii"), hashlib.sha256).digest()
    return f"{body_part}.{_b64encode(signature)}"


def verify_signed_token(
    token: str,
    *,
    secret: str,
    expected_type: str | None = None,
) -> dict[str, Any] | None:
    try:
        body_part, signature_part = token.split(".", 1)
    except ValueError:
        return None

    expected_signature = hmac.new(secret.encode("utf-8"), body_part.encode("ascii"), hashlib.sha256).digest()
    try:
        actual_signature = _b64decode(signature_part)
    except ValueError:
        return None
    if not hmac.compare_digest(expected_signature, actual_signature):
        return None

    try:
        payload = json.loads(_b64decode(body_part).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None

    exp = payload.get("exp")
    if isinstance(exp, (int, float)) and time.time() > float(exp):
        return None
    if expected_type and payload.get("type") != expected_type:
        return None
    return payload

