"""Library persistence operations."""

from __future__ import annotations

import sqlite3


def fetch_all(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute(
        """
        SELECT libraries.*, COUNT(words.id) AS word_count
        FROM libraries
        LEFT JOIN words ON words.library_id = libraries.id
        GROUP BY libraries.id
        ORDER BY libraries.id ASC
        """
    ).fetchall()


def fetch_one(db: sqlite3.Connection, library_id: int) -> sqlite3.Row | None:
    return db.execute("SELECT * FROM libraries WHERE id = ?", (library_id,)).fetchone()


def get_or_create(db: sqlite3.Connection, name: str) -> int:
    row = db.execute("SELECT id FROM libraries WHERE name = ?", (name,)).fetchone()
    if row:
        return int(row["id"])
    cursor = db.execute("INSERT INTO libraries (name) VALUES (?)", (name,))
    db.commit()
    return int(cursor.lastrowid)


def delete_source_words(db: sqlite3.Connection, library_id: int, source: str) -> None:
    db.execute("DELETE FROM words WHERE library_id = ? AND source = ?", (library_id, source))
    db.commit()
