"""Library persistence operations."""

from __future__ import annotations

import sqlite3


def fetch_all(db: sqlite3.Connection, user_id: int | None = None) -> list[sqlite3.Row]:
    return db.execute(
        """
        SELECT libraries.*, COUNT(words.id) AS word_count
        FROM libraries
        LEFT JOIN words ON words.library_id = libraries.id
        WHERE libraries.user_id IS ?
        GROUP BY libraries.id
        ORDER BY libraries.id ASC
        """,
        (user_id,),
    ).fetchall()


def fetch_one(db: sqlite3.Connection, library_id: int, user_id: int | None = None) -> sqlite3.Row | None:
    return db.execute(
        "SELECT * FROM libraries WHERE id = ? AND user_id IS ?",
        (library_id, user_id),
    ).fetchone()


def get_or_create(db: sqlite3.Connection, name: str, user_id: int | None = None) -> int:
    row = db.execute(
        "SELECT id FROM libraries WHERE name = ? AND user_id IS ?",
        (name, user_id),
    ).fetchone()
    if row:
        return int(row["id"])
    cursor = db.execute("INSERT INTO libraries (user_id, name) VALUES (?, ?)", (user_id, name))
    db.commit()
    return int(cursor.lastrowid)


def delete_source_words(db: sqlite3.Connection, library_id: int, source: str) -> None:
    db.execute("DELETE FROM words WHERE library_id = ? AND source = ?", (library_id, source))
    db.commit()


def rename(db: sqlite3.Connection, library_id: int, name: str) -> None:
    db.execute(
        "UPDATE libraries SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (name, library_id),
    )
    db.commit()


def delete(db: sqlite3.Connection, library_id: int) -> None:
    db.execute("DELETE FROM libraries WHERE id = ?", (library_id,))
    db.commit()
