"""Fixed expressions attached to one library word."""

from __future__ import annotations

import sqlite3


def fetch_user_patterns(db: sqlite3.Connection, word_id: int) -> list[sqlite3.Row]:
    return db.execute(
        """
        SELECT id, expression, definition, sense_rank, usage_label, source,
               enabled_for_cloze, rank
        FROM word_patterns
        WHERE word_id = ? AND source = 'user'
        ORDER BY rank, id
        """,
        (word_id,),
    ).fetchall()


def fetch_user_pattern(db: sqlite3.Connection, pattern_id: int, word_id: int) -> sqlite3.Row | None:
    return db.execute(
        "SELECT * FROM word_patterns WHERE id = ? AND word_id = ? AND source = 'user'",
        (pattern_id, word_id),
    ).fetchone()


def add_user_pattern(
    db: sqlite3.Connection, word_id: int, expression: str,
    definition: str | None, sense_rank: int | None,
    usage_label: str | None, enabled_for_cloze: bool,
) -> int:
    cursor = db.execute(
        """
        INSERT INTO word_patterns (
            word_id, expression, definition, sense_rank, usage_label,
            source, enabled_for_cloze
        ) VALUES (?, ?, ?, ?, ?, 'user', ?)
        """,
        (word_id, expression, definition, sense_rank, usage_label, 1 if enabled_for_cloze else 0),
    )
    db.commit()
    return int(cursor.lastrowid)


def update_user_pattern(
    db: sqlite3.Connection, pattern_id: int, word_id: int, expression: str,
    definition: str | None, sense_rank: int | None,
    usage_label: str | None, enabled_for_cloze: bool,
) -> bool:
    cursor = db.execute(
        """
        UPDATE word_patterns
        SET expression = ?, definition = ?, sense_rank = ?, usage_label = ?,
            enabled_for_cloze = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND word_id = ? AND source = 'user'
        """,
        (expression, definition, sense_rank, usage_label, 1 if enabled_for_cloze else 0, pattern_id, word_id),
    )
    db.commit()
    return bool(cursor.rowcount)


def delete_user_pattern(db: sqlite3.Connection, pattern_id: int, word_id: int) -> bool:
    cursor = db.execute(
        "DELETE FROM word_patterns WHERE id = ? AND word_id = ? AND source = 'user'",
        (pattern_id, word_id),
    )
    db.commit()
    return bool(cursor.rowcount)
