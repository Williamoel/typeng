"""Security helpers shared by the desktop entry point and future web app."""

from __future__ import annotations

import secrets
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit


def normalize_username(value: str) -> tuple[str, str]:
    """Return a display username and its uniqueness key.

    NFKC prevents visually equivalent full-width Latin names from registering
    twice, while casefold makes English usernames case-insensitively unique.
    Chinese characters are preserved.
    """
    display = unicodedata.normalize("NFKC", value).strip()
    return display, display.casefold()


def load_or_create_secret(data_dir: Path) -> str:
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "secret_key"
    try:
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    except OSError:
        pass
    value = secrets.token_hex(32)
    try:
        path.write_text(value, encoding="utf-8")
    except OSError:
        pass
    return value


def is_local_host(host_or_origin: str | None) -> bool:
    value = (host_or_origin or "").strip()
    if not value:
        return False
    if "://" not in value:
        value = f"http://{value}"
    try:
        hostname = urlsplit(value).hostname or ""
    except ValueError:
        return False
    return hostname.lower() in {"127.0.0.1", "localhost", "::1"}


def is_local_origin(origin: str | None) -> bool:
    return bool(origin and origin != "null" and is_local_host(origin))


def host_name(host_or_origin: str | None) -> str:
    value = (host_or_origin or "").strip()
    if not value:
        return ""
    if "://" not in value:
        value = f"http://{value}"
    try:
        return (urlsplit(value).hostname or "").casefold()
    except ValueError:
        return ""


def is_same_origin(origin: str | None, request_url: str) -> bool:
    """Compare scheme and host for hosted unsafe requests."""
    if not origin or origin == "null":
        return False
    try:
        source = urlsplit(origin)
        target = urlsplit(request_url)
    except ValueError:
        return False
    source_port = source.port or (443 if source.scheme == "https" else 80)
    target_port = target.port or (443 if target.scheme == "https" else 80)
    return (
        source.scheme.casefold() == target.scheme.casefold()
        and (source.hostname or "").casefold() == (target.hostname or "").casefold()
        and source_port == target_port
    )
