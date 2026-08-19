"""User authentication and lightweight registration throttling."""

from __future__ import annotations

import sqlite3


def fetch_by_id(db: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return db.execute(
        "SELECT id, username, password_hash, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()


def fetch_by_key(db: sqlite3.Connection, username_key: str) -> sqlite3.Row | None:
    return db.execute(
        "SELECT id, username, password_hash, created_at FROM users WHERE username_key = ?",
        (username_key,),
    ).fetchone()


def create(db: sqlite3.Connection, username: str, username_key: str, password_hash: str) -> int:
    cursor = db.execute(
        "INSERT INTO users (username, username_key, password_hash) VALUES (?, ?, ?)",
        (username, username_key, password_hash),
    )
    return int(cursor.lastrowid)


def mark_login(db: sqlite3.Connection, user_id: int) -> None:
    db.execute(
        "UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?",
        (user_id,),
    )
    db.commit()


def registration_attempt_count(db: sqlite3.Connection, device_hash: str, attempted_on: str) -> int:
    row = db.execute(
        "SELECT COUNT(*) AS count FROM registration_attempts WHERE device_hash = ? AND attempted_on = ?",
        (device_hash, attempted_on),
    ).fetchone()
    return int(row["count"])


def record_registration_attempt(
    db: sqlite3.Connection, device_hash: str, attempted_on: str, success: bool
) -> None:
    db.execute(
        "INSERT INTO registration_attempts (device_hash, attempted_on, success) VALUES (?, ?, ?)",
        (device_hash, attempted_on, 1 if success else 0),
    )
    # The limiter only needs a short audit window.
    db.execute(
        "DELETE FROM registration_attempts WHERE attempted_on < date(?, '-7 days')",
        (attempted_on,),
    )
    db.commit()
