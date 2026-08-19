"""Persistence operations for per-library learning words."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

from .examples import replace_user_example
from .units import assign_unassigned


def count(db: sqlite3.Connection, library_id: int, status: str | None = None) -> int:
    sql = "SELECT COUNT(*) AS count FROM words WHERE library_id = ?"
    params: list[object] = [library_id]
    if status is not None:
        sql += " AND status = ?"
        params.append(status)
    return int(db.execute(sql, params).fetchone()["count"])


def fetch_all(db: sqlite3.Connection, library_id: int, status: str | None = None) -> list[sqlite3.Row]:
    sql = "SELECT * FROM words WHERE library_id = ?"
    params: list[object] = [library_id]
    if status is not None:
        sql += " AND status = ?"
        params.append(status)
    return db.execute(sql + " ORDER BY id ASC", params).fetchall()


def fetch_for_export(
    db: sqlite3.Connection,
    library_id: int,
    unit_number: int | None = None,
) -> list[sqlite3.Row]:
    """Return one library in stable unit order with only authored examples.

    Dictionary examples are intentionally not exported as user examples: if a
    CSV is imported again, TypEng must not accidentally promote a Wiktionary
    quotation to user-authored priority.
    """
    sql = """
        SELECT words.*,
               COALESCE(
                   (
                       SELECT sentence FROM word_examples
                       WHERE word_examples.word_id = words.id
                         AND word_examples.source = 'user'
                       ORDER BY word_examples.rank, word_examples.id
                       LIMIT 1
                   ),
                   CASE WHEN words.example_source = 'user'
                        THEN words.example_sentence END
               ) AS exported_example_sentence,
               COALESCE(
                   (
                       SELECT translation FROM word_examples
                       WHERE word_examples.word_id = words.id
                         AND word_examples.source = 'user'
                       ORDER BY word_examples.rank, word_examples.id
                       LIMIT 1
                   ),
                   CASE WHEN words.example_source = 'user'
                        THEN words.example_translation END
               ) AS exported_example_translation
        FROM words
        WHERE words.library_id = ?
    """
    params: list[object] = [library_id]
    if unit_number is not None:
        sql += " AND words.unit_number = ?"
        params.append(max(1, unit_number))
    sql += """
        ORDER BY CASE WHEN words.unit_number IS NULL THEN 1 ELSE 0 END,
                 words.unit_number, words.unit_position, words.id
    """
    return db.execute(sql, params).fetchall()


def fetch_one(db: sqlite3.Connection, library_id: int, word_id: int) -> sqlite3.Row | None:
    return db.execute(
        "SELECT * FROM words WHERE id = ? AND library_id = ?", (word_id, library_id)
    ).fetchone()


def fetch_by_ids(db: sqlite3.Connection, library_id: int, ids: list[int]) -> list[sqlite3.Row]:
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    rows = db.execute(
        f"SELECT * FROM words WHERE library_id = ? AND id IN ({placeholders})",
        [library_id, *ids],
    ).fetchall()
    by_id = {int(row["id"]): row for row in rows}
    return [by_id[word_id] for word_id in ids if word_id in by_id]


def import_entries(
    db: sqlite3.Connection,
    library_id: int,
    entries: list[dict[str, object]],
    normalize_pos: Callable[[str], str],
    sync_word: Callable[[sqlite3.Connection, int], int | None],
    update_existing: bool = True,
) -> tuple[int, int, int]:
    inserted = updated = skipped = 0
    word_columns = {row[1] for row in db.execute("PRAGMA table_info(words)")}
    has_example_source = "example_source" in word_columns
    has_word_examples = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='word_examples'"
    ).fetchone() is not None
    for entry in entries:
        entry["part_of_speech"] = normalize_pos(str(entry["part_of_speech"]))
        existing = db.execute(
            "SELECT id FROM words WHERE library_id = ? AND word = ? AND part_of_speech = ?",
            (library_id, entry["word"], entry["part_of_speech"]),
        ).fetchone()
        if existing and not update_existing:
            skipped += 1
            continue
        values = (
            entry["meaning"], entry.get("example_sentence"), entry.get("example_translation"),
            entry.get("example_source"),
            entry.get("phonetic"), entry.get("definition"), entry.get("frequency"),
            entry.get("source"), entry.get("source_tags"),
        )
        if existing:
            if has_example_source:
                db.execute(
                    """
                    UPDATE words SET meaning = ?, example_sentence = COALESCE(?, example_sentence),
                        example_translation = COALESCE(?, example_translation),
                        example_source = COALESCE(?, example_source),
                        phonetic = COALESCE(?, phonetic), definition = COALESCE(?, definition),
                        frequency = COALESCE(?, frequency), source = COALESCE(?, source),
                        source_tags = COALESCE(?, source_tags), updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND library_id = ?
                    """,
                    (*values, existing["id"], library_id),
                )
            else:
                db.execute(
                    """
                    UPDATE words SET meaning = ?, example_sentence = COALESCE(?, example_sentence),
                        example_translation = COALESCE(?, example_translation),
                        phonetic = COALESCE(?, phonetic), definition = COALESCE(?, definition),
                        frequency = COALESCE(?, frequency), source = COALESCE(?, source),
                        source_tags = COALESCE(?, source_tags), updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND library_id = ?
                    """,
                    (*values[:3], *values[4:], existing["id"], library_id),
                )
            word_id = int(existing["id"])
            updated += 1
        else:
            if has_example_source:
                cursor = db.execute(
                    """
                    INSERT INTO words (library_id, word, part_of_speech, meaning,
                        example_sentence, example_translation, example_source, phonetic, definition,
                        frequency, source, source_tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (library_id, entry["word"], entry["part_of_speech"], *values),
                )
            else:
                cursor = db.execute(
                    """
                    INSERT INTO words (library_id, word, part_of_speech, meaning,
                        example_sentence, example_translation, phonetic, definition,
                        frequency, source, source_tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (library_id, entry["word"], entry["part_of_speech"], *values[:3], *values[4:]),
                )
            word_id = int(cursor.lastrowid)
            inserted += 1
        sync_word(db, word_id)
        if has_word_examples and entry.get("example_source") == "user" and entry.get("example_sentence"):
            replace_user_example(
                db, word_id, str(entry["example_sentence"]),
                str(entry.get("example_translation") or "") or None,
            )
    assign_unassigned(db, library_id)
    db.commit()
    return inserted, updated, skipped
