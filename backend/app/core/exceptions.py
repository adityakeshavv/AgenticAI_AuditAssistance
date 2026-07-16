from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from fastapi import HTTPException, status


_DB_ERROR_PATTERNS = [
    re.compile(r'FATAL:\s*(.*?)(?:\s+Multiple connection attempts failed|$)', re.IGNORECASE | re.DOTALL),
    re.compile(r'password authentication failed for user\s+"([^"]+)"', re.IGNORECASE),
    re.compile(r'database\s+"([^"]+)"\s+does not exist', re.IGNORECASE),
    re.compile(r'could not connect to server:\s*(.*?)(?:\s+Is the server running|$)', re.IGNORECASE | re.DOTALL),
]


def _extract_database_cause(text: str) -> str | None:
    normalized = " ".join(text.split())
    for pattern in _DB_ERROR_PATTERNS:
        match = pattern.search(normalized)
        if not match:
            continue
        if pattern.pattern.startswith("password authentication failed"):
            return f'Password authentication failed for user "{match.group(1)}".'
        if pattern.pattern.startswith("database"):
            return f'Database "{match.group(1)}" does not exist.'
        cause = match.group(1).strip().rstrip(".")
        if not cause:
            continue
        if cause:
            lowered = cause.lower()
            if "connection failed:" in lowered:
                cause = cause.split("connection failed:", 1)[-1].strip()
                lowered = cause.lower()
            if "furthermore" in lowered:
                cause = cause.split("Furthermore", 1)[0].strip()
            if "multiple connection attempts failed" in lowered:
                cause = cause.split("Multiple connection attempts failed", 1)[0].strip()
            if "all failures were" in lowered:
                cause = cause.split("All failures were", 1)[0].strip()
            if "background on this error" in lowered:
                cause = cause.split("(Background on this error", 1)[0].strip()
            if "host:" in lowered and "port:" in lowered:
                cause = cause.split("- host:", 1)[0].strip()
            cause = cause.strip(" :-")
            return cause[:1].upper() + cause[1:] + ("." if not cause.endswith(".") else "")
    if "psycopg" in normalized.lower() or "sqlalchemy" in normalized.lower():
        return "Database connection failed. Please verify the host, port, database name, username, and password."
    return None


def format_human_error(error: object, default_message: str = "An unexpected error occurred.") -> str:
    if isinstance(error, HTTPException):
        return format_human_error(error.detail, default_message)

    if isinstance(error, str):
        message = error.strip()
        if not message:
          return default_message
        database_message = _extract_database_cause(message)
        return database_message or message

    if isinstance(error, Mapping):
        for key in ("detail", "message", "error", "errors"):
            if key in error:
                message = format_human_error(error[key], default_message)
                if message:
                    return message

        parts: list[str] = []
        for key, value in error.items():
            text = format_human_error(value, "")
            if text:
                parts.append(f"{key}: {text}" if key else text)
        return "; ".join(parts) or default_message

    if isinstance(error, Sequence) and not isinstance(error, (bytes, bytearray, str)):
        parts = [format_human_error(item, "") for item in error]
        parts = [part for part in parts if part]
        return "; ".join(parts) or default_message

    if error is None:
        return default_message

    text = str(error).strip()
    if not text:
        return default_message
    database_message = _extract_database_cause(text)
    return database_message or text


def safe_detail(detail: object, default_message: str = "Request failed.") -> str:
    message = format_human_error(detail, default_message)
    return message or default_message


class AuditAssistantException(Exception):
    """Base application exception."""


class ResourceNotFoundError(AuditAssistantException):
    """Raised when a requested resource does not exist."""


def not_found_exception(resource: str, identifier: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"{resource} not found: {identifier}",
    )
