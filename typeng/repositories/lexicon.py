"""Repository for the source-neutral Word -> Sense -> Example graph."""

from __future__ import annotations

import sqlite3


def sync_learning_word(db: sqlite3.Connection, word_id: int) -> int | None:
    """Project one legacy learning row into the canonical lexical graph."""
    schema_ready = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'lexemes'"
    ).fetchone()
    if schema_ready is None:
        # Maintenance scripts and compatibility tests may intentionally use a
        # minimal legacy schema without running application initialization.
        return None
    row = db.execute("SELECT * FROM words WHERE id = ?", (word_id,)).fetchone()
    if row is None:
        return None
    lemma = str(row["word"]).strip()
    normalized = lemma.casefold()
    db.execute(
        "INSERT OR IGNORE INTO lexemes (lemma, normalized_lemma) VALUES (?, ?)",
        (lemma, normalized),
    )
    lexeme_id = int(db.execute(
        "SELECT id FROM lexemes WHERE language = 'en' AND normalized_lemma = ?",
        (normalized,),
    ).fetchone()["id"])
    gloss = str(row["meaning"] or "").strip()
    definition = str(row["definition"] or "").strip()
    part = str(row["part_of_speech"] or "phrase")
    db.execute(
        """
        INSERT OR IGNORE INTO senses (
            lexeme_id, part_of_speech, chinese_gloss, english_definition,
            phonetic, frequency, source, source_ref, source_tags
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (lexeme_id, part, gloss, definition, row["phonetic"], row["frequency"],
         row["source"], f"legacy-word:{word_id}", row["source_tags"]),
    )
    sense_id = int(db.execute(
        """
        SELECT id FROM senses WHERE lexeme_id = ? AND part_of_speech = ?
          AND chinese_gloss = ? AND english_definition = ?
        """,
        (lexeme_id, part, gloss, definition),
    ).fetchone()["id"])
    db.execute(
        """
        INSERT INTO word_sense_links (word_id, sense_id) VALUES (?, ?)
        ON CONFLICT(word_id) DO UPDATE SET sense_id = excluded.sense_id
        """,
        (word_id, sense_id),
    )
    sentence = str(row["example_sentence"] or "").strip()
    if sentence:
        db.execute(
            """
            INSERT OR IGNORE INTO sense_examples
                (sense_id, sentence, translation, note, source, source_ref)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (sense_id, sentence, row["example_translation"], row["example_note"],
             row["source"], f"legacy-word:{word_id}"),
        )
    return sense_id


def fetch_senses(db: sqlite3.Connection, lemma: str, language: str = "en") -> list[sqlite3.Row]:
    return db.execute(
        """
        SELECT senses.*, lexemes.lemma, lexemes.language
        FROM senses JOIN lexemes ON lexemes.id = senses.lexeme_id
        WHERE lexemes.language = ? AND lexemes.normalized_lemma = ?
        ORDER BY senses.part_of_speech, senses.id
        """,
        (language, lemma.strip().casefold()),
    ).fetchall()


def fetch_examples(db: sqlite3.Connection, sense_id: int) -> list[sqlite3.Row]:
    return db.execute(
        "SELECT * FROM sense_examples WHERE sense_id = ? ORDER BY rank, id",
        (sense_id,),
    ).fetchall()
