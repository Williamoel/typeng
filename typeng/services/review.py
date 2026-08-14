"""Spaced-review use cases, independent of Flask request state."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable


def due_count(
    db: sqlite3.Connection, library_id: int, status: str, date_column: str,
    today: str, require_incomplete_review: bool = False,
) -> int:
    if date_column not in {"next_review_at", "wrong_next_review_at"}:
        raise ValueError("unsupported review date column")
    join = "JOIN libraries ON libraries.id = words.library_id" if require_incomplete_review else ""
    incomplete = "AND words.review_correct_count < libraries.review_target_count" if require_incomplete_review else ""
    row = db.execute(
        f"""
        SELECT COUNT(*) AS count FROM words {join}
        WHERE words.library_id = ? AND words.status = ?
          {incomplete} AND words.{date_column} IS NOT NULL
          AND date(words.{date_column}) <= ?
        """,
        (library_id, status, today),
    ).fetchone()
    return int(row["count"])


def schedule_initial(
    db: sqlite3.Connection, library_id: int, word_id: int,
    next_date: Callable[[int], str],
) -> None:
    db.execute(
        """
        UPDATE words SET review_stage = 0, next_review_at = COALESCE(next_review_at, ?),
            updated_at = CURRENT_TIMESTAMP WHERE id = ? AND library_id = ?
        """,
        (next_date(0), word_id, library_id),
    )


def complete(
    db: sqlite3.Connection, library_id: int, word_id: int, target: int,
    learned_status: str, next_date: Callable[[int], str],
) -> None:
    word = db.execute(
        "SELECT * FROM words WHERE id = ? AND library_id = ?", (word_id, library_id)
    ).fetchone()
    if word is None:
        return
    new_count = int(word["review_correct_count"]) + 1
    new_stage = int(word["review_stage"]) + 1
    next_at = None if new_count >= target else next_date(new_stage)
    db.execute(
        """
        UPDATE words SET status = ?, review_correct_count = ?, review_stage = ?,
            next_review_at = ?, last_reviewed_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP WHERE id = ? AND library_id = ?
        """,
        (learned_status, new_count, new_stage, next_at, word_id, library_id),
    )


def reset(db: sqlite3.Connection, library_id: int, word_id: int) -> None:
    db.execute(
        """
        UPDATE words SET review_correct_count = 0, review_stage = 0,
            next_review_at = NULL, last_reviewed_at = NULL,
            updated_at = CURRENT_TIMESTAMP WHERE id = ? AND library_id = ?
        """,
        (word_id, library_id),
    )
