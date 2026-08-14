"""Wiktionary/Kaikki streaming index and lookup engine."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from pathlib import Path

from ..parts import CANONICAL_PARTS

from ..domain import (
    english_word_count,
    extract_example_sentence,
    normalize_wiktionary_pos,
    sentence_quality_score,
    spelling_variants,
    usable_wiktionary_example,
    wiktionary_usage_label,
    wiktionary_example_rank,
    wiktionary_lookup_groups,
)

_db_provider: Callable[[], sqlite3.Connection] | None = None
_path_provider: Callable[[], Path | None] | None = None
_signature_provider: Callable[[], str | None] | None = None
_available_provider: Callable[[], bool] | None = None


def configure(db_provider, path_provider, signature_provider, available_provider) -> None:
    global _db_provider, _path_provider, _signature_provider, _available_provider
    _db_provider = db_provider
    _path_provider = path_provider
    _signature_provider = signature_provider
    _available_provider = available_provider


def get_db() -> sqlite3.Connection:
    if _db_provider is None:
        raise RuntimeError("Wiktionary engine is not configured")
    return _db_provider()


def _path() -> Path | None:
    return _path_provider() if _path_provider else None


def _signature() -> str | None:
    return _signature_provider() if _signature_provider else None


def _available() -> bool:
    return _available_provider() if _available_provider else False


def ensure_wiktionary_lookup_index(target_words: set[str] | None = None) -> None:
    """Batch-build local lookup rows from the raw multi-gigabyte export.

    This function is intentionally reserved for maintenance/import workflows.
    Request-time lookup functions must query SQLite only and must never call it.
    """
    path = _path()
    signature = _signature()
    if not path or not signature:
        return

    db = get_db()
    existing = db.execute("SELECT value FROM metadata WHERE key = ?", ("wiktionary_lookup_signature",)).fetchone()
    table_exists = db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        ("wiktionary_examples",),
    ).fetchone()
    definition_table_exists = db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        ("wiktionary_definitions",),
    ).fetchone()
    indexed_table_exists = db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        ("wiktionary_indexed_words",),
    ).fetchone()
    needs_rebuild = not (table_exists and definition_table_exists and indexed_table_exists and existing and existing["value"] == signature)
    normalized_targets = {word.strip().lower() for word in target_words if word.strip()} if target_words is not None else None
    if target_words is not None and not normalized_targets:
        return
    if not needs_rebuild and normalized_targets is None:
        return

    if not needs_rebuild and normalized_targets is not None:
        placeholders = ",".join("?" for _ in normalized_targets)
        indexed_rows = db.execute(
            f"SELECT word_key FROM wiktionary_indexed_words WHERE word_key IN ({placeholders})",
            sorted(normalized_targets),
        ).fetchall()
        indexed_words = {row["word_key"] for row in indexed_rows}
        normalized_targets = normalized_targets - indexed_words
        if not normalized_targets:
            return

    if needs_rebuild:
        db.execute("DROP TABLE IF EXISTS wiktionary_examples")
        db.execute("DROP TABLE IF EXISTS wiktionary_definitions")
        db.execute("DROP TABLE IF EXISTS wiktionary_indexed_words")
        db.execute(
            """
            CREATE TABLE wiktionary_examples (
                word_key TEXT NOT NULL,
                part_group TEXT NOT NULL,
                example_sentence TEXT NOT NULL,
                definition TEXT,
                example_type TEXT,
                sense_tags TEXT,
                sense_rank INTEGER NOT NULL DEFAULT 0,
                example_rank INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        db.execute(
            """
            CREATE TABLE wiktionary_definitions (
                word_key TEXT NOT NULL,
                part_group TEXT NOT NULL,
                definition TEXT NOT NULL,
                sense_tags TEXT,
                sense_rank INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        db.execute(
            """
            CREATE TABLE wiktionary_indexed_words (
                word_key TEXT PRIMARY KEY
            )
            """
        )
        db.execute(
            """
            INSERT INTO metadata (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            ("wiktionary_lookup_signature", signature),
        )
    else:
        db.execute("DROP INDEX IF EXISTS idx_wiktionary_examples_word_part")
        db.execute("DROP INDEX IF EXISTS idx_wiktionary_definitions_word_part")

    words_to_index = normalized_targets

    rows: list[tuple[str, str, str, str | None, str | None, str | None, int, int]] = []
    definition_rows: list[tuple[str, str, str, str | None, int]] = []
    seen: set[tuple[str, str, str]] = set()
    seen_definitions: set[tuple[str, str, str]] = set()

    def flush_rows() -> None:
        nonlocal rows, definition_rows
        if rows:
            db.executemany(
                """
                INSERT INTO wiktionary_examples (
                    word_key, part_group, example_sentence, definition,
                    example_type, sense_tags, sense_rank, example_rank
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        if definition_rows:
            db.executemany(
                """
                INSERT INTO wiktionary_definitions (
                    word_key, part_group, definition, sense_tags, sense_rank
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                definition_rows,
            )
        rows = []
        definition_rows = []

    with path.open("rt", encoding="utf-8") as handle:
        for line in handle:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("lang_code") != "en":
                continue
            word_key = str(entry.get("word") or "").lower().strip()
            if words_to_index is not None and word_key not in words_to_index:
                continue
            part_group = normalize_wiktionary_pos(str(entry.get("pos") or ""))
            if not word_key or part_group not in (CANONICAL_PARTS - {"aux"}):
                continue
            senses = entry.get("senses") or []
            if not isinstance(senses, list):
                continue
            for sense_rank, sense in enumerate(senses):
                if not isinstance(sense, dict):
                    continue
                definition = "\n".join(str(item).strip() for item in sense.get("glosses", []) if str(item).strip()) or None
                sense_tags = ",".join(str(item).strip().lower() for item in sense.get("tags", []) if str(item).strip()) or None
                tag_set = {str(tag).strip().lower() for tag in sense.get("tags", []) if str(tag).strip()}
                if definition and not ({"archaic", "obsolete", "dated", "rare", "form-of"} & tag_set):
                    definition_key = (word_key, part_group, definition)
                    if definition_key not in seen_definitions:
                        seen_definitions.add(definition_key)
                        definition_rows.append((word_key, part_group, definition, sense_tags, sense_rank))
                examples = sense.get("examples") or []
                if not isinstance(examples, list):
                    continue
                if {"archaic", "obsolete"} & tag_set:
                    continue
                for example in examples:
                    if not isinstance(example, dict):
                        continue
                    sentence = extract_example_sentence(str(example.get("text") or ""), word_key)
                    if not usable_wiktionary_example(sentence, word_key):
                        continue
                    key = (word_key, part_group, sentence)
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(
                        (
                            word_key,
                            part_group,
                            sentence,
                            definition,
                            str(example.get("type") or ""),
                            sense_tags,
                            sense_rank,
                            wiktionary_example_rank(example, sentence),
                        )
                    )
                    if len(rows) >= 5000:
                        flush_rows()
                if len(definition_rows) >= 5000:
                    flush_rows()
    flush_rows()
    if words_to_index is not None:
        db.executemany(
            "INSERT OR IGNORE INTO wiktionary_indexed_words (word_key) VALUES (?)",
            [(word,) for word in sorted(words_to_index)],
        )
    db.execute("CREATE INDEX idx_wiktionary_examples_word_part ON wiktionary_examples(word_key, part_group, sense_rank, example_rank)")
    db.execute("CREATE INDEX idx_wiktionary_definitions_word_part ON wiktionary_definitions(word_key, part_group, sense_rank)")
    db.commit()


def ranked_wiktionary_example_candidates(
    word: str,
    part_of_speech: str,
    limit: int | None = 8,
    include_tagged: bool = False,
) -> list[sqlite3.Row]:
    if not word.strip() or not _available():
        return []
    word_keys = sorted(spelling_variants(word))
    lookup_groups = wiktionary_lookup_groups(part_of_speech, word)
    group_placeholders = ",".join("?" for _ in lookup_groups)
    key_placeholders = ",".join("?" for _ in word_keys)
    rows = get_db().execute(
        f"""
        SELECT example_sentence, definition, example_type, sense_tags, part_group
        FROM wiktionary_examples
        WHERE word_key IN ({key_placeholders}) AND part_group IN ({group_placeholders})
        ORDER BY example_rank ASC, sense_rank ASC, length(example_sentence) ASC
        """,
        (*word_keys, *lookup_groups),
    ).fetchall()
    blocked_tags = {"archaic", "obsolete"}
    dislike_tags = {"dated", "rare"}
    suitable: list[dict[str, object]] = []
    for row in rows:
        s = row["example_sentence"]
        if not usable_wiktionary_example(s, word):
            continue
        tags = {tag.strip() for tag in str(row["sense_tags"] or "").split(",") if tag.strip()}
        if blocked_tags & tags:
            continue
        suitable.append((row, tags))
    preferred = [(row, tags) for row, tags in suitable if not (dislike_tags & tags)]
    candidates = suitable if include_tagged else (preferred if preferred else suitable)

    scored: list[tuple[tuple[int, int, bool, int, int, str], dict[str, object]]] = []
    for row, tags in candidates:
        sentence = row["example_sentence"]
        tg_pen = 0
        if "obsolete" in tags: tg_pen += 18
        if "archaic" in tags: tg_pen += 12
        if "dated" in tags: tg_pen += 8
        if "rare" in tags: tg_pen += 5
        sq = sentence_quality_score(sentence, word, part_of_speech, source="wiktionary")
        if sq[1] > 10:
            continue
        sp = 0 if english_word_count(sentence) >= 6 else 1
        ranked_score = (tg_pen, sp, row["example_type"] == "quotation", sq[2], sq[3], sq[4])
        scored.append((ranked_score, row))
    scored.sort(key=lambda item: item[0])
    ranked = [row for _, row in scored]
    return ranked if limit is None else ranked[:limit]


def lookup_wiktionary_example(word: str, part_of_speech: str) -> sqlite3.Row | None:
    candidates = ranked_wiktionary_example_candidates(word, part_of_speech, limit=1)
    return candidates[0] if candidates else None


def lookup_wiktionary_definition(word: str, part_of_speech: str) -> str | None:
    if not word.strip() or not _available():
        return None
    word_keys = sorted(spelling_variants(word))
    lookup_groups = wiktionary_lookup_groups(part_of_speech, word)
    group_placeholders = ",".join("?" for _ in lookup_groups)
    key_placeholders = ",".join("?" for _ in word_keys)
    rows = get_db().execute(
        f"""
        SELECT definition, sense_tags, part_group, sense_rank
        FROM wiktionary_definitions
        WHERE word_key IN ({key_placeholders}) AND part_group IN ({group_placeholders})
        ORDER BY sense_rank ASC, length(definition) ASC
        LIMIT 12
        """,
        (*word_keys, *lookup_groups),
    ).fetchall()
    if not rows:
        return None
    definitions: list[str] = []
    seen: set[str] = set()
    for row in rows:
        tags = {tag.strip() for tag in str(row["sense_tags"] or "").split(",") if tag.strip()}
        if {"archaic", "obsolete", "dated", "rare", "form-of"} & tags:
            continue
        definition = str(row["definition"] or "").strip()
        if not definition or definition in seen:
            continue
        seen.add(definition)
        usage_label = wiktionary_usage_label(str(row["sense_tags"] or ""))
        definitions.append(f"[{usage_label}] {definition}" if usage_label else definition)
        if len(definitions) >= 4:
            break
    return "\n".join(definitions) if definitions else None
