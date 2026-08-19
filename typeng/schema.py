"""SQLite schema creation and versioned data migrations."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from .constants import (
    DEFAULT_REVIEW_TARGET_COUNT, DEFAULT_WRONG_REVIEW_TARGET_COUNT,
    STATUS_LEARNED, STATUS_NEW, STATUS_WRONG,
)
from .domain import (
    contains_blocked_example_word, infer_pos_from_ecdict_definition,
    infer_pos_from_word_shape, merge_text_values, next_review_date,
    simplify_chinese, valid_example_sentence,
)
from .lexicon_cache import install_prebuilt_cache
from .repositories.lexicon import sync_learning_word
from .repositories.units import assign_unassigned


def table_columns(db: sqlite3.Connection, table_name: str) -> set[str]:
    return {row["name"] for row in db.execute(f"PRAGMA table_info({table_name})").fetchall()}


def merge_verb_part_duplicates(db: sqlite3.Connection) -> None:
    rows = db.execute(
        """
        SELECT *
        FROM words
        WHERE part_of_speech IN ('vi', 'vt', 'verb', 'aux', 'v')
        ORDER BY library_id ASC, lower(word) ASC, id ASC
        """
    ).fetchall()
    groups: dict[tuple[int, str], list[sqlite3.Row]] = {}
    for row in rows:
        groups.setdefault((int(row["library_id"]), str(row["word"]).lower()), []).append(row)

    status_rank = {STATUS_NEW: 0, STATUS_LEARNED: 1, STATUS_WRONG: 2}
    for (library_id, _word_key), group in groups.items():
        if not group:
            continue
        target = next((row for row in group if row["part_of_speech"] == "v"), group[0])
        duplicate_rows = [row for row in group if int(row["id"]) != int(target["id"])]
        if not duplicate_rows and target["part_of_speech"] == "v":
            continue

        all_rows = [target, *duplicate_rows]
        best_status = max((row["status"] for row in all_rows), key=lambda status: status_rank.get(status, 0))
        meaning = merge_text_values(*(row["meaning"] for row in all_rows)) or target["meaning"]
        definition = merge_text_values(*(row["definition"] for row in all_rows))
        source_tags = merge_text_values(*(row["source_tags"] for row in all_rows))
        example_row = next((row for row in all_rows if row["example_sentence"]), target)
        phonetic_row = next((row for row in all_rows if row["phonetic"]), target)
        source_row = next((row for row in all_rows if row["source"]), target)
        frequency_values = [int(row["frequency"]) for row in all_rows if row["frequency"] is not None]
        frequency = min(frequency_values) if frequency_values else None
        wrong_correct_count = max(int(row["wrong_correct_count"]) for row in all_rows)
        review_correct_count = max(int(row["review_correct_count"]) for row in all_rows)
        review_stage = max(int(row["review_stage"]) for row in all_rows)
        total_attempts = sum(int(row["total_attempts"]) for row in all_rows)
        correct_attempts = sum(int(row["correct_attempts"]) for row in all_rows)
        wrong_next_review_at = min((row["wrong_next_review_at"] for row in all_rows if row["wrong_next_review_at"]), default=None)
        next_review_at = min((row["next_review_at"] for row in all_rows if row["next_review_at"]), default=None)
        last_reviewed_at = max((row["last_reviewed_at"] for row in all_rows if row["last_reviewed_at"]), default=None)

        try:
            db.execute(
                """
                UPDATE words
                SET part_of_speech = ?,
                    meaning = ?,
                    example_sentence = ?,
                    example_translation = ?,
                    phonetic = ?,
                    definition = ?,
                    frequency = ?,
                    source = ?,
                    source_tags = ?,
                    status = ?,
                    wrong_correct_count = ?,
                    wrong_next_review_at = ?,
                    review_correct_count = ?,
                    review_stage = ?,
                    next_review_at = ?,
                    last_reviewed_at = ?,
                    total_attempts = ?,
                    correct_attempts = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND library_id = ?
                """,
                (
                    "v",
                    meaning,
                    example_row["example_sentence"],
                    example_row["example_translation"],
                    phonetic_row["phonetic"],
                    definition,
                    frequency,
                    source_row["source"],
                    source_tags,
                    best_status,
                    wrong_correct_count,
                    wrong_next_review_at,
                    review_correct_count,
                    review_stage,
                    next_review_at,
                    last_reviewed_at,
                    total_attempts,
                    correct_attempts,
                    target["id"],
                    library_id,
                ),
            )
        except sqlite3.IntegrityError:
            existing = db.execute(
                """
                SELECT *
                FROM words
                WHERE library_id = ? AND lower(word) = lower(?) AND part_of_speech = 'v'
                """,
                (library_id, target["word"]),
            ).fetchone()
            if existing and int(existing["id"]) != int(target["id"]):
                duplicate_rows.append(target)
                target = existing
                db.execute(
                    """
                    UPDATE words
                    SET meaning = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND library_id = ?
                    """,
                    (merge_text_values(existing["meaning"], meaning) or meaning, existing["id"], library_id),
                )

        duplicate_ids = [int(row["id"]) for row in duplicate_rows]
        if duplicate_ids:
            placeholders = ",".join("?" for _ in duplicate_ids)
            if db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='word_examples'"
            ).fetchone():
                db.execute(
                    f"""
                    INSERT OR IGNORE INTO word_examples
                        (word_id, sentence, translation, note, source, rank)
                    SELECT ?, sentence, translation, note, source, rank
                    FROM word_examples
                    WHERE word_id IN ({placeholders})
                    """,
                    [target["id"], *duplicate_ids],
                )
            db.execute(
                f"""
                DELETE FROM words
                WHERE library_id = ? AND id IN ({placeholders})
                """,
                [library_id, *duplicate_ids],
            )


def migrate_plural_phrase_entries(db: sqlite3.Connection) -> None:
    rows = db.execute(
        """
        SELECT *
        FROM words
        WHERE part_of_speech = 'phrase'
          AND lower(trim(meaning)) LIKE 'pl.%'
        ORDER BY library_id ASC, lower(word) ASC, id ASC
        """
    ).fetchall()
    for row in rows:
        existing = db.execute(
            """
            SELECT *
            FROM words
            WHERE library_id = ?
              AND lower(word) = lower(?)
              AND part_of_speech = 'n'
              AND id != ?
            """,
            (row["library_id"], row["word"], row["id"]),
        ).fetchone()
        if existing:
            merged_meaning = merge_text_values(existing["meaning"], row["meaning"]) or existing["meaning"]
            db.execute(
                """
                UPDATE words
                SET meaning = ?,
                    example_sentence = COALESCE(example_sentence, ?),
                    example_translation = COALESCE(example_translation, ?),
                    phonetic = COALESCE(phonetic, ?),
                    definition = COALESCE(definition, ?),
                    frequency = COALESCE(frequency, ?),
                    source = COALESCE(source, ?),
                    source_tags = COALESCE(source_tags, ?),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND library_id = ?
                """,
                (
                    merged_meaning,
                    row["example_sentence"],
                    row["example_translation"],
                    row["phonetic"],
                    row["definition"],
                    row["frequency"],
                    row["source"],
                    row["source_tags"],
                    existing["id"],
                    existing["library_id"],
                ),
            )
            db.execute("DELETE FROM words WHERE id = ? AND library_id = ?", (row["id"], row["library_id"]))
        else:
            db.execute(
                """
                UPDATE words
                SET part_of_speech = 'n',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND library_id = ?
                """,
                (row["id"], row["library_id"]),
            )


def update_word_part_preserving_duplicate(db: sqlite3.Connection, row: sqlite3.Row, target_part: str) -> None:
    existing = db.execute(
        """
        SELECT *
        FROM words
        WHERE library_id = ?
          AND lower(word) = lower(?)
          AND part_of_speech = ?
          AND id != ?
        """,
        (row["library_id"], row["word"], target_part, row["id"]),
    ).fetchone()
    if existing:
        merged_meaning = merge_text_values(existing["meaning"], row["meaning"]) or existing["meaning"]
        db.execute(
            """
            UPDATE words
            SET meaning = ?,
                example_sentence = COALESCE(example_sentence, ?),
                example_translation = COALESCE(example_translation, ?),
                phonetic = COALESCE(phonetic, ?),
                definition = COALESCE(definition, ?),
                frequency = COALESCE(frequency, ?),
                source = COALESCE(source, ?),
                source_tags = COALESCE(source_tags, ?),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND library_id = ?
            """,
            (
                merged_meaning,
                row["example_sentence"],
                row["example_translation"],
                row["phonetic"],
                row["definition"],
                row["frequency"],
                row["source"],
                row["source_tags"],
                existing["id"],
                existing["library_id"],
            ),
        )
        db.execute("DELETE FROM words WHERE id = ? AND library_id = ?", (row["id"], row["library_id"]))
    else:
        db.execute(
            """
            UPDATE words
            SET part_of_speech = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND library_id = ?
            """,
            (target_part, row["id"], row["library_id"]),
        )


def migrate_inferred_phrase_entries(db: sqlite3.Connection) -> None:
    rows = db.execute(
        """
        SELECT *
        FROM words
        WHERE part_of_speech = 'phrase'
          AND instr(trim(word), ' ') = 0
        ORDER BY library_id ASC, lower(word) ASC, id ASC
        """
    ).fetchall()
    for row in rows:
        inferred = infer_pos_from_ecdict_definition(row["definition"] or "")
        if not inferred:
            inferred = infer_pos_from_word_shape(row["word"] or "", row["meaning"] or "")
        if inferred and inferred != "phrase":
            update_word_part_preserving_duplicate(db, row, inferred)


def create_lexical_tables(db: sqlite3.Connection) -> None:
    """Create the source-neutral Word -> Sense -> Example model.

    The legacy ``words`` table remains the per-library learning record.  Its
    lexical content is linked to a reusable sense through ``word_sense_links``.
    """
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS lexemes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lemma TEXT NOT NULL,
            normalized_lemma TEXT NOT NULL,
            language TEXT NOT NULL DEFAULT 'en',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(language, normalized_lemma)
        );

        CREATE TABLE IF NOT EXISTS senses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lexeme_id INTEGER NOT NULL,
            part_of_speech TEXT NOT NULL,
            chinese_gloss TEXT NOT NULL DEFAULT '',
            english_definition TEXT NOT NULL DEFAULT '',
            phonetic TEXT,
            frequency INTEGER,
            source TEXT,
            source_ref TEXT,
            source_tags TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(lexeme_id, part_of_speech, chinese_gloss, english_definition),
            FOREIGN KEY(lexeme_id) REFERENCES lexemes(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS sense_examples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sense_id INTEGER NOT NULL,
            sentence TEXT NOT NULL,
            translation TEXT,
            note TEXT,
            source TEXT,
            source_ref TEXT,
            rank INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(sense_id, sentence),
            FOREIGN KEY(sense_id) REFERENCES senses(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS word_sense_links (
            word_id INTEGER PRIMARY KEY,
            sense_id INTEGER NOT NULL,
            FOREIGN KEY(word_id) REFERENCES words(id) ON DELETE CASCADE,
            FOREIGN KEY(sense_id) REFERENCES senses(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS word_examples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER NOT NULL,
            sentence TEXT NOT NULL,
            translation TEXT,
            note TEXT,
            source TEXT NOT NULL DEFAULT 'user',
            rank INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(word_id, sentence),
            FOREIGN KEY(word_id) REFERENCES words(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS word_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER NOT NULL,
            expression TEXT NOT NULL,
            definition TEXT,
            sense_rank INTEGER,
            usage_label TEXT,
            source TEXT NOT NULL DEFAULT 'user',
            enabled_for_cloze INTEGER NOT NULL DEFAULT 1,
            rank INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(word_id, expression, source),
            FOREIGN KEY(word_id) REFERENCES words(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS cloze_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feedback_token TEXT NOT NULL UNIQUE,
            library_id INTEGER,
            user_id INTEGER,
            word_id INTEGER,
            word TEXT NOT NULL,
            part_of_speech TEXT NOT NULL,
            sentence TEXT NOT NULL,
            sentence_hash TEXT NOT NULL,
            material_type TEXT NOT NULL DEFAULT 'example',
            material_source TEXT,
            rating TEXT NOT NULL CHECK (
                rating IN ('too_hard', 'too_easy', 'unsuitable', 'incorrect')
            ),
            answer_correct INTEGER NOT NULL DEFAULT 0,
            practice_mode TEXT NOT NULL DEFAULT 'normal',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE SET NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY(word_id) REFERENCES words(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_senses_lexeme_pos
            ON senses(lexeme_id, part_of_speech);
        CREATE INDEX IF NOT EXISTS idx_examples_sense_rank
            ON sense_examples(sense_id, rank, id);
        CREATE INDEX IF NOT EXISTS idx_word_examples_source_rank
            ON word_examples(word_id, source, rank, id);
        CREATE INDEX IF NOT EXISTS idx_word_patterns_source_rank
            ON word_patterns(word_id, source, rank, id);
        CREATE INDEX IF NOT EXISTS idx_cloze_feedback_sentence_rating
            ON cloze_feedback(sentence_hash, rating, created_at);
        """
    )


def create_account_tables(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            username_key TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_login_at TEXT
        );

        CREATE TABLE IF NOT EXISTS registration_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_hash TEXT NOT NULL,
            attempted_on TEXT NOT NULL,
            success INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_registration_attempts_device_day
            ON registration_attempts(device_hash, attempted_on);
        """
    )


def migrate_library_ownership(db: sqlite3.Connection) -> None:
    """Add per-user library ownership and replace the old global name key."""
    if "user_id" in table_columns(db, "libraries"):
        return

    # SQLite cannot drop the old UNIQUE(name) constraint in place. Rebuild the
    # parent table while FK enforcement is temporarily disabled; child tables
    # continue to reference the final `libraries` table name.
    db.commit()
    db.execute("PRAGMA foreign_keys = OFF")
    try:
        db.execute("BEGIN")
        db.execute(
            """
            CREATE TABLE libraries_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                review_target_count INTEGER NOT NULL DEFAULT 3,
                wrong_review_target_count INTEGER NOT NULL DEFAULT 3,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, name),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        db.execute(
            """
            INSERT INTO libraries_new (
                id, user_id, name, review_target_count,
                wrong_review_target_count, created_at, updated_at
            )
            SELECT id, NULL, name, review_target_count,
                   wrong_review_target_count, created_at, updated_at
            FROM libraries
            """
        )
        db.execute("DROP TABLE libraries")
        db.execute("ALTER TABLE libraries_new RENAME TO libraries")
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.execute("PRAGMA foreign_keys = ON")


def backfill_lexical_model(db: sqlite3.Connection) -> None:
    """Idempotently project legacy learning rows into the lexical model."""
    word_ids = db.execute(
        """
        SELECT words.id
        FROM words
        LEFT JOIN word_sense_links ON word_sense_links.word_id = words.id
        WHERE word_sense_links.word_id IS NULL
        ORDER BY words.id
        """
    ).fetchall()
    for row in word_ids:
        sync_learning_word(db, int(row["id"]))


def migrate_db(db: sqlite3.Connection, app_schema_version: int) -> None:
    create_account_tables(db)
    db.execute(
        """
        INSERT OR IGNORE INTO libraries (id, name)
        VALUES (1, 'Default Library')
        """
    )

    library_columns = table_columns(db, "libraries")
    if "review_target_count" not in library_columns:
        db.execute(
            f"ALTER TABLE libraries ADD COLUMN review_target_count INTEGER NOT NULL DEFAULT {DEFAULT_REVIEW_TARGET_COUNT}"
        )
    if "wrong_review_target_count" not in library_columns:
        db.execute(
            f"ALTER TABLE libraries ADD COLUMN wrong_review_target_count INTEGER NOT NULL DEFAULT {DEFAULT_WRONG_REVIEW_TARGET_COUNT}"
        )
    migrate_library_ownership(db)

    columns = table_columns(db, "words")
    if "library_id" not in columns:
        db.execute("ALTER TABLE words RENAME TO words_legacy")
        db.execute(
            """
            CREATE TABLE words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                library_id INTEGER NOT NULL DEFAULT 1,
                word TEXT NOT NULL,
                part_of_speech TEXT NOT NULL,
                meaning TEXT NOT NULL,
                example_sentence TEXT,
                example_translation TEXT,
                phonetic TEXT,
                definition TEXT,
                frequency INTEGER,
                source TEXT,
                source_tags TEXT,
                unit_number INTEGER,
                unit_position INTEGER,
                status TEXT NOT NULL DEFAULT 'new',
                wrong_correct_count INTEGER NOT NULL DEFAULT 0,
                wrong_next_review_at TEXT,
                review_correct_count INTEGER NOT NULL DEFAULT 0,
                review_stage INTEGER NOT NULL DEFAULT 0,
                next_review_at TEXT,
                last_reviewed_at TEXT,
                total_attempts INTEGER NOT NULL DEFAULT 0,
                correct_attempts INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(library_id, word, part_of_speech),
                FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE CASCADE
            )
            """
        )
        db.execute(
            """
            INSERT INTO words (
                id, library_id, word, part_of_speech, meaning, status,
                wrong_correct_count, total_attempts, correct_attempts,
                created_at, updated_at
            )
            SELECT
                id, 1, word, part_of_speech, meaning, status,
                wrong_correct_count, total_attempts, correct_attempts,
                created_at, updated_at
            FROM words_legacy
            """
        )
        db.execute("DROP TABLE words_legacy")
        columns = table_columns(db, "words")

    for column_name, column_sql in {
        "phonetic": "ALTER TABLE words ADD COLUMN phonetic TEXT",
        "example_sentence": "ALTER TABLE words ADD COLUMN example_sentence TEXT",
        "example_translation": "ALTER TABLE words ADD COLUMN example_translation TEXT",
        "definition": "ALTER TABLE words ADD COLUMN definition TEXT",
        "frequency": "ALTER TABLE words ADD COLUMN frequency INTEGER",
        "source": "ALTER TABLE words ADD COLUMN source TEXT",
        "source_tags": "ALTER TABLE words ADD COLUMN source_tags TEXT",
        "unit_number": "ALTER TABLE words ADD COLUMN unit_number INTEGER",
        "unit_position": "ALTER TABLE words ADD COLUMN unit_position INTEGER",
        "wrong_next_review_at": "ALTER TABLE words ADD COLUMN wrong_next_review_at TEXT",
        "review_correct_count": "ALTER TABLE words ADD COLUMN review_correct_count INTEGER NOT NULL DEFAULT 0",
        "review_stage": "ALTER TABLE words ADD COLUMN review_stage INTEGER NOT NULL DEFAULT 0",
        "next_review_at": "ALTER TABLE words ADD COLUMN next_review_at TEXT",
        "last_reviewed_at": "ALTER TABLE words ADD COLUMN last_reviewed_at TEXT",
        "example_note": "ALTER TABLE words ADD COLUMN example_note TEXT",
        "example_source": "ALTER TABLE words ADD COLUMN example_source TEXT",
    }.items():
        if column_name not in columns:
            db.execute(column_sql)

    version_row = db.execute(
        "SELECT value FROM metadata WHERE key = 'app_schema_version'"
    ).fetchone()
    current_version = int(version_row["value"]) if version_row else 0
    if current_version < 1:
        # These are data migrations, not request-time maintenance.  Earlier
        # versions ran all five full-table scans on every process start.
        db.execute(
            """
            UPDATE words
            SET next_review_at = ?
            WHERE status = ?
              AND next_review_at IS NULL
              AND review_correct_count = 0
            """,
            (next_review_date(0), STATUS_LEARNED),
        )
        db.execute(
            """
            UPDATE words
            SET wrong_next_review_at = ?
            WHERE status = ?
              AND wrong_next_review_at IS NULL
            """,
            (next_review_date(0), STATUS_WRONG),
        )
        clear_invalid_example_sentences(db)
        simplify_existing_example_translations(db)
        merge_verb_part_duplicates(db)
        migrate_plural_phrase_entries(db)
        migrate_inferred_phrase_entries(db)

    create_lexical_tables(db)
    feedback_columns = table_columns(db, "cloze_feedback")
    if "user_id" not in feedback_columns:
        db.execute("ALTER TABLE cloze_feedback ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
    db.execute("CREATE INDEX IF NOT EXISTS idx_cloze_feedback_user_created ON cloze_feedback(user_id, created_at)")
    if current_version < 2:
        backfill_lexical_model(db)
    if current_version < 3:
        # WordNet was removed after an audit showed little unique example
        # coverage. Existing installations should not retain its unused cache.
        db.execute("DROP TABLE IF EXISTS wordnet_examples")
        db.execute("DELETE FROM metadata WHERE key = 'wordnet_lookup_signature'")
    if current_version < 4:
        has_wiktionary = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='wiktionary_examples'"
        ).fetchone() is not None
        rows = db.execute(
            """
            SELECT id, word, part_of_speech, example_sentence,
                   example_translation, example_note
            FROM words
            WHERE example_sentence IS NOT NULL AND trim(example_sentence) != ''
            """
        ).fetchall()
        for row in rows:
            dictionary_match = False
            if has_wiktionary:
                dictionary_match = db.execute(
                    """
                    SELECT 1 FROM wiktionary_examples
                    WHERE word_key = lower(?) AND example_sentence = ?
                    LIMIT 1
                    """,
                    (row["word"], row["example_sentence"]),
                ).fetchone() is not None
            source = "wiktionary" if dictionary_match or row["example_note"] else "user"
            db.execute(
                "UPDATE words SET example_source = ? WHERE id = ?",
                (source, row["id"]),
            )
            if source == "user":
                db.execute(
                    """
                    INSERT OR IGNORE INTO word_examples
                        (word_id, sentence, translation, note, source, rank)
                    VALUES (?, ?, ?, ?, 'user', -100)
                    """,
                    (
                        row["id"], row["example_sentence"],
                        row["example_translation"], row["example_note"],
                    ),
                )

    # v5 removes auxiliary as a learning-word category. Wiktionary exposes
    # auxiliaries under the verb group, so old aux rows are merged into v.
    if 1 <= current_version < 5:
        merge_verb_part_duplicates(db)

    # v6 freezes the former virtual 100-word pages into stable organizational
    # units. Deleting a few words no longer pulls entries from the next unit.
    if current_version < 6:
        assign_unassigned(db)

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS library_units (
            library_id INTEGER NOT NULL,
            unit_number INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (library_id, unit_number),
            FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE CASCADE
        )
        """
    )
    if current_version < 7:
        db.execute(
            """
            INSERT OR IGNORE INTO library_units (library_id, unit_number)
            SELECT DISTINCT library_id, unit_number FROM words
            WHERE unit_number IS NOT NULL
            """
        )

    db.execute("CREATE INDEX IF NOT EXISTS idx_words_library_status_id ON words(library_id, status, id)")
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_words_due_review "
        "ON words(library_id, status, next_review_at, review_correct_count)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_words_due_wrong "
        "ON words(library_id, status, wrong_next_review_at, wrong_correct_count)"
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_words_library_frequency ON words(library_id, frequency, id)")
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_words_library_unit "
        "ON words(library_id, unit_number, unit_position)"
    )
    db.execute(
        "INSERT INTO metadata (key, value) VALUES ('app_schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(app_schema_version),),
    )


def ensure_metadata_table(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )


def initialize(
    db: sqlite3.Connection,
    prebuilt_lexicon_path: Path,
    app_schema_version: int,
) -> None:
    ensure_metadata_table(db)
    create_account_tables(db)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS libraries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            review_target_count INTEGER NOT NULL DEFAULT 3,
            wrong_review_target_count INTEGER NOT NULL DEFAULT 3,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, name),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            library_id INTEGER NOT NULL DEFAULT 1,
            word TEXT NOT NULL,
            part_of_speech TEXT NOT NULL,
            meaning TEXT NOT NULL,
            example_sentence TEXT,
            example_translation TEXT,
            example_note TEXT,
            example_source TEXT,
            phonetic TEXT,
            definition TEXT,
            frequency INTEGER,
            source TEXT,
            source_tags TEXT,
            unit_number INTEGER,
            unit_position INTEGER,
            status TEXT NOT NULL DEFAULT 'new',
            wrong_correct_count INTEGER NOT NULL DEFAULT 0,
            wrong_next_review_at TEXT,
            review_correct_count INTEGER NOT NULL DEFAULT 0,
            review_stage INTEGER NOT NULL DEFAULT 0,
            next_review_at TEXT,
            last_reviewed_at TEXT,
            total_attempts INTEGER NOT NULL DEFAULT 0,
            correct_attempts INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(library_id, word, part_of_speech),
            FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE CASCADE
        )
        """
    )
    # Fresh installations can start from a compact, deployment-built lookup
    # DB and never need the raw multi-gigabyte dictionary files.
    install_prebuilt_cache(db, prebuilt_lexicon_path)
    migrate_db(db, app_schema_version)
    db.commit()


def clear_invalid_example_sentences(db: sqlite3.Connection) -> None:
    rows = db.execute(
        """
        SELECT id, word, example_sentence
        FROM words
        WHERE example_sentence IS NOT NULL
          AND trim(example_sentence) != ''
        """
    ).fetchall()
    invalid_ids = [
        int(row["id"])
        for row in rows
        if not valid_example_sentence(row["example_sentence"], row["word"])
        or contains_blocked_example_word(row["example_sentence"] or "")
    ]
    for start in range(0, len(invalid_ids), 500):
        batch = invalid_ids[start : start + 500]
        placeholders = ",".join("?" for _ in batch)
        db.execute(
            f"""
            UPDATE words
            SET example_sentence = NULL,
                example_note = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id IN ({placeholders})
            """,
            batch,
        )


def simplify_existing_example_translations(db: sqlite3.Connection) -> None:
    rows = db.execute(
        """
        SELECT id, example_translation
        FROM words
        WHERE example_translation IS NOT NULL
          AND trim(example_translation) != ''
        """
    ).fetchall()
    for row in rows:
        simplified = simplify_chinese(row["example_translation"])
        if simplified and simplified != row["example_translation"]:
            db.execute(
                """
                UPDATE words
                SET example_translation = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (simplified, row["id"]),
            )
