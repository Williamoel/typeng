"""Security helpers shared by the desktop entry point and future web app."""

from __future__ import annotations

import secrets
from pathlib import Path
from urllib.parse import urlsplit


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

