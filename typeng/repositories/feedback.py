"""Persistence for learner ratings of Cloze material."""

from __future__ import annotations

import sqlite3


RATINGS = {"too_hard", "too_easy", "unsuitable", "incorrect"}


def save(
    db: sqlite3.Connection,
    *,
    feedback_token: str,
    library_id: int,
    user_id: int | None,
    word_id: int,
    word: str,
    part_of_speech: str,
    sentence: str,
    sentence_hash: str,
    material_type: str,
    material_source: str | None,
    rating: str,
    answer_correct: bool,
    practice_mode: str,
) -> None:
    if rating not in RATINGS:
        raise ValueError("unsupported Cloze feedback rating")
    db.execute(
        """
        INSERT INTO cloze_feedback (
            feedback_token, library_id, user_id, word_id, word, part_of_speech,
            sentence, sentence_hash, material_type, material_source, rating,
            answer_correct, practice_mode
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(feedback_token) DO UPDATE SET
            rating = excluded.rating,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            feedback_token, library_id, user_id, word_id, word, part_of_speech,
            sentence, sentence_hash, material_type, material_source, rating,
            1 if answer_correct else 0, practice_mode,
        ),
    )
    db.commit()
