"""Auditable Wiktionary validation and EFLLex filtering for exam presets."""

from __future__ import annotations

import csv
import hashlib
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Iterable

from .constants import BLOCKED_WIKTIONARY_DEFINITION_TAGS
from .domain import wiktionary_usage_label
from .parts import compatible_parts, lexical_part

LEVEL_RANK = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5}
EXAM_MIN_LEVEL = {
    "zk": "A1",
    "gk": "A2",
    "cet4": "B1",
    "cet6": "B2",
    "kaoyan": "B2",
    "ielts": "B2",
    "toefl": "B2",
    "gre": "B2",
}


def _table_exists(db: sqlite3.Connection, table_name: str) -> bool:
    return db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
    ).fetchone() is not None


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_wiktionary_exam_pos_index(db: sqlite3.Connection, path: Path) -> int:
    """Import the small, snapshot-derived POS presence index."""
    if not path.is_file():
        return 0
    signature = _file_hash(path)
    current = db.execute(
        "SELECT value FROM metadata WHERE key='wiktionary_exam_pos_signature'"
    ).fetchone()
    if current and current[0] == signature and _table_exists(db, "wiktionary_exam_parts"):
        return int(db.execute("SELECT COUNT(*) FROM wiktionary_exam_parts").fetchone()[0])

    db.execute("DROP TABLE IF EXISTS wiktionary_exam_parts")
    db.execute(
        """
        CREATE TABLE wiktionary_exam_parts (
            word_key TEXT NOT NULL,
            part_group TEXT NOT NULL,
            PRIMARY KEY (word_key, part_group)
        )
        """
    )
    rows: list[tuple[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            word = str(row.get("word") or "").strip().casefold()
            for part in str(row.get("parts") or "").split("|"):
                normalized = lexical_part(part, unknown="")
                if word and normalized:
                    rows.append((word, normalized))
    db.executemany(
        "INSERT OR IGNORE INTO wiktionary_exam_parts(word_key, part_group) VALUES (?, ?)",
        rows,
    )
    db.execute(
        "INSERT INTO metadata(key, value) VALUES('wiktionary_exam_pos_signature', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (signature,),
    )
    db.commit()
    return int(db.execute("SELECT COUNT(*) FROM wiktionary_exam_parts").fetchone()[0])


def _chunks(values: list[str], size: int = 800) -> Iterable[list[str]]:
    for start in range(0, len(values), size):
        yield values[start:start + size]


def _wiktionary_parts(db: sqlite3.Connection, words: set[str]) -> dict[str, set[str]] | None:
    if not _table_exists(db, "wiktionary_exam_parts"):
        return None
    result: dict[str, set[str]] = {}
    for chunk in _chunks(sorted(words)):
        placeholders = ",".join("?" for _ in chunk)
        for row in db.execute(
            f"SELECT word_key, part_group FROM wiktionary_exam_parts WHERE word_key IN ({placeholders})",
            chunk,
        ):
            result.setdefault(str(row[0]), set()).add(lexical_part(str(row[1])))
    return result


def _wiktionary_definitions(
    db: sqlite3.Connection, words: set[str]
) -> dict[tuple[str, str], list[str]] | None:
    """Load modern English definitions grouped by exact word and POS."""
    if not _table_exists(db, "wiktionary_definitions"):
        return None
    result: dict[tuple[str, str], list[str]] = {}
    for chunk in _chunks(sorted(words)):
        placeholders = ",".join("?" for _ in chunk)
        rows = db.execute(
            f"SELECT word_key, part_group, definition, sense_tags "
            f"FROM wiktionary_definitions WHERE word_key IN ({placeholders}) "
            "ORDER BY word_key, part_group, sense_rank, length(definition)",
            chunk,
        )
        for row in rows:
            tags = {tag.strip() for tag in str(row[3] or "").split(",") if tag.strip()}
            if BLOCKED_WIKTIONARY_DEFINITION_TAGS & tags:
                continue
            definition = str(row[2] or "").strip()
            usage_label = wiktionary_usage_label(str(row[3] or ""))
            displayed_definition = f"[{usage_label}] {definition}" if usage_label else definition
            key = (str(row[0]), lexical_part(str(row[1])))
            bucket = result.setdefault(key, [])
            if definition and displayed_definition not in bucket:
                bucket.append(displayed_definition)
    return result


def _wiktionary_headwords(
    db: sqlite3.Connection, words: set[str]
) -> dict[str, str]:
    if not _table_exists(db, "wiktionary_headwords"):
        return {}
    result: dict[str, str] = {}
    for chunk in _chunks(sorted(words)):
        placeholders = ",".join("?" for _ in chunk)
        for row in db.execute(
            f"SELECT word_key, canonical_word FROM wiktionary_headwords "
            f"WHERE word_key IN ({placeholders})",
            chunk,
        ):
            result[str(row[0])] = str(row[1])
    return result


def _efllex_levels(db: sqlite3.Connection, words: set[str]) -> dict[tuple[str, str], str]:
    if not _table_exists(db, "efllex_profiles"):
        return {}
    result: dict[tuple[str, str], str] = {}
    for chunk in _chunks(sorted(words)):
        placeholders = ",".join("?" for _ in chunk)
        for row in db.execute(
            f"SELECT word_key, part_group, provisional_level FROM efllex_profiles "
            f"WHERE word_key IN ({placeholders}) AND provisional_level IS NOT NULL",
            chunk,
        ):
            key = (str(row[0]), lexical_part(str(row[1])))
            level = str(row[2])
            current = result.get(key)
            if current is None or LEVEL_RANK[level] < LEVEL_RANK[current]:
                result[key] = level
    return result


def apply_exam_policy(
    db: sqlite3.Connection,
    preset_key: str,
    entries: list[dict[str, object]],
) -> tuple[list[dict[str, object]], dict[str, int]]:
    """Require a matching English definition and remove too-basic entries.

    Wiktionary is authoritative for English POS and definitions; ECDICT only
    supplies the Chinese meaning. Missing EFLLex classifications are retained.
    Example availability remains intentionally irrelevant to this policy.
    """
    minimum = EXAM_MIN_LEVEL[preset_key]
    words = {str(entry.get("word") or "").strip().casefold() for entry in entries}
    wiki = _wiktionary_parts(db, words)
    definitions = _wiktionary_definitions(db, words)
    headwords = _wiktionary_headwords(db, words)
    levels = _efllex_levels(db, words)
    kept: list[dict[str, object]] = []
    stats: Counter[str] = Counter(total=len(entries))

    if definitions is None:
        stats["wiktionary_definitions_unavailable"] = len(entries)
        stats["kept"] = 0
        return [], dict(stats)

    for entry in entries:
        word = str(entry.get("word") or "").strip().casefold()
        part = lexical_part(str(entry.get("part_of_speech") or ""))
        if wiki is not None and not (compatible_parts(part, word) & wiki.get(word, set())):
            stats["removed_wiktionary_pos"] += 1
            continue
        compatible = compatible_parts(part, word)
        ordered_parts = [part, *sorted(compatible - {part})]
        english_definitions: list[str] = []
        for definition_part in ordered_parts:
            for definition in definitions.get((word, definition_part), []):
                if definition not in english_definitions:
                    english_definitions.append(definition)
                if len(english_definitions) >= 4:
                    break
            if len(english_definitions) >= 4:
                break
        if not english_definitions:
            stats["removed_missing_definition"] += 1
            continue
        level = levels.get((word, part))
        if level and LEVEL_RANK[level] < LEVEL_RANK[minimum]:
            stats["removed_basic"] += 1
            continue
        normalized = dict(entry)
        normalized["word"] = headwords.get(word, str(entry.get("word") or "").strip())
        normalized["part_of_speech"] = part
        normalized["definition"] = "\n".join(english_definitions)
        kept.append(normalized)
        stats["kept_unclassified" if level is None else "kept_classified"] += 1

    stats["kept"] = len(kept)
    return kept, dict(stats)
