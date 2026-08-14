"""Per-library user examples attached to learning words."""

from __future__ import annotations

import sqlite3


def replace_user_example(
    db: sqlite3.Connection,
    word_id: int,
    sentence: str | None,
    translation: str | None = None,
) -> None:
    db.execute("DELETE FROM word_examples WHERE word_id = ? AND source = 'user'", (word_id,))
    sentence = (sentence or "").strip()
    if sentence:
        db.execute(
            """
            INSERT INTO word_examples(word_id, sentence, translation, source, rank)
            VALUES (?, ?, ?, 'user', -100)
            """,
            (word_id, sentence, translation),
        )


def fetch_user_examples(db: sqlite3.Connection, word_id: int) -> list[sqlite3.Row]:
    return db.execute(
        """
        SELECT id, sentence, translation, note, source, rank
        FROM word_examples
        WHERE word_id = ? AND source = 'user'
        ORDER BY rank, id
        """,
        (word_id,),
    ).fetchall()

