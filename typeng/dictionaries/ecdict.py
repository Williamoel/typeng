"""ECDICT loading, normalization, preset materialization, and lookup."""

from __future__ import annotations

import csv
import io
import sqlite3
import urllib.request
from collections.abc import Callable
from pathlib import Path

from ..constants import ECDICT_MEANING_CORRECTIONS, ECDICT_PRESET_LIBRARIES
from ..domain import (
    format_ecdict_definition,
    infer_ecdict_fallback_pos,
    merge_text_values,
    normalize_ecdict_frequency,
    normalize_user_pos,
    split_ecdict_tags,
    split_ecdict_translation,
)

_db_provider: Callable[[], sqlite3.Connection] | None = None
_bundled_path_provider = None
_cache_path_provider = None
_data_dir_provider = None
_source_url_provider = None
_schema_provider = None
_loader_provider = None


def configure(db_provider, bundled_path_provider, cache_path_provider, data_dir_provider,
              source_url_provider, schema_provider, loader_provider) -> None:
    global _db_provider, _bundled_path_provider, _cache_path_provider
    global _data_dir_provider, _source_url_provider, _schema_provider, _loader_provider
    _db_provider = db_provider
    _bundled_path_provider = bundled_path_provider
    _cache_path_provider = cache_path_provider
    _data_dir_provider = data_dir_provider
    _source_url_provider = source_url_provider
    _schema_provider = schema_provider
    _loader_provider = loader_provider


def get_db() -> sqlite3.Connection:
    if _db_provider is None:
        raise RuntimeError("ECDICT engine is not configured")
    return _db_provider()


def _bundled_path() -> Path: return _bundled_path_provider()
def _cache_path() -> Path: return _cache_path_provider()
def _data_dir() -> Path: return _data_dir_provider()
def _source_url() -> str: return _source_url_provider()
def _schema_version() -> int: return _schema_provider()
def _configured_loader() -> bytes: return _loader_provider()


def ecdict_entries_for_word(
    word: str,
    part_of_speech: str = "",
    meaning: str = "",
    raw: bytes | None = None,
) -> list[dict[str, object]]:
    word_key = word.strip().lower()
    if not word_key:
        return []

    requested_part = normalize_user_pos(part_of_speech.strip()) if part_of_speech else ""
    source_rows = []
    if raw is None:
        try:
            lookup = get_db().execute(
                """
                SELECT word, translation, raw_pos, exchange, phonetic,
                       definition, frequency, source_tags
                FROM ecdict_lookup WHERE word_key = ?
                """,
                (word_key,),
            ).fetchone()
        except sqlite3.OperationalError:
            lookup = None
        if lookup is not None and lookup["translation"]:
            source_rows.append(
                {
                    "word": str(lookup["word"] or ""),
                    "translation": str(lookup["translation"] or ""),
                    "pos": str(lookup["raw_pos"] or ""),
                    "exchange": str(lookup["exchange"] or ""),
                    "phonetic": str(lookup["phonetic"] or ""),
                    "definition": str(lookup["definition"] or ""),
                    "frq": str(lookup["frequency"] or ""),
                    "tag": str(lookup["source_tags"] or ""),
                }
            )
        else:
            try:
                raw = _configured_loader()
            except Exception:
                return []
    if raw is not None:
        text = raw.decode("utf-8-sig")
        source_rows = (
            {(key or "").strip().lower(): (value or "").strip() for key, value in row.items()}
            for row in csv.DictReader(io.StringIO(text))
        )

    merged: dict[str, dict[str, object]] = {}
    for normalized in source_rows:
        if normalized.get("word", "").lower() != word_key:
            continue

        fallback_pos = infer_ecdict_fallback_pos(normalized)
        translations = split_ecdict_translation(normalized.get("translation", ""), fallback_pos)
        for entry_part, entry_meaning in translations:
            part = normalize_user_pos(entry_part)
            if requested_part and part != requested_part:
                continue
            if not entry_meaning and not meaning:
                continue
            existing = merged.setdefault(
                part,
                {
                    "word": normalized.get("word") or word,
                    "part_of_speech": part,
                    "meaning_parts": [],
                    "phonetic": normalized.get("phonetic") or None,
                    "definition": format_ecdict_definition(normalized.get("definition", "")) or None,
                    "frequency": normalize_ecdict_frequency(normalized),
                    "source": "ECDICT",
                    "source_tags": normalized.get("tag") or None,
                },
            )
            if entry_meaning:
                existing["meaning_parts"].append(entry_meaning)

    entries: list[dict[str, object]] = []
    for part, entry in merged.items():
        selected_meaning = meaning or merge_text_values(*(entry.pop("meaning_parts") or []))
        if selected_meaning:
            entry["meaning"] = selected_meaning
            entries.append(entry)

    if requested_part and meaning and not entries:
        entries.append({"word": word, "part_of_speech": requested_part, "meaning": meaning})

    return entries


def load_ecdict_data() -> bytes:
    if _bundled_path().exists():
        return _bundled_path().read_bytes()

    if _cache_path().exists():
        return _cache_path().read_bytes()

    _data_dir().mkdir(exist_ok=True)
    with urllib.request.urlopen(_source_url(), timeout=30) as response:
        raw = response.read()
    _cache_path().write_bytes(raw)
    return raw


def ecdict_source_signature() -> str | None:
    if _bundled_path().exists():
        path = _bundled_path()
    elif _cache_path().exists():
        path = _cache_path()
    else:
        return None
    stat = path.stat()
    return f"{path.name}:{stat.st_size}:{int(stat.st_mtime)}:{_schema_version()}"


def ensure_ecdict_lookup_index() -> None:
    signature = ecdict_source_signature()
    if not signature:
        return

    db = get_db()
    existing = db.execute("SELECT value FROM metadata WHERE key = ?", ("ecdict_lookup_signature",)).fetchone()
    table_exists = db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        ("ecdict_lookup",),
    ).fetchone()
    if table_exists and existing and existing["value"] == signature:
        return

    try:
        raw = _configured_loader()
    except OSError:
        # No bundled/cached ECDICT and the download failed (e.g. offline).
        # Skip enrichment instead of turning an import/edit into a 500.
        return
    db.execute("DROP TABLE IF EXISTS ecdict_lookup")
    db.execute("DROP TABLE IF EXISTS ecdict_preset_entries")
    db.execute(
        """
        CREATE TABLE ecdict_lookup (
            word_key TEXT PRIMARY KEY,
            word TEXT NOT NULL,
            translation TEXT,
            raw_pos TEXT,
            exchange TEXT,
            phonetic TEXT,
            definition TEXT,
            frequency INTEGER,
            source_tags TEXT
        )
        """
    )
    db.execute(
        """
        CREATE TABLE ecdict_preset_entries (
            word TEXT NOT NULL,
            part_of_speech TEXT NOT NULL,
            meaning TEXT NOT NULL,
            phonetic TEXT,
            definition TEXT,
            frequency INTEGER,
            source_tags TEXT,
            UNIQUE(word, part_of_speech)
        )
        """
    )

    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    lookup_rows: list[tuple[object, ...]] = []
    preset_rows: list[tuple[object, ...]] = []
    supported_preset_tags = {
        tag
        for preset in ECDICT_PRESET_LIBRARIES.values()
        for tag in set(preset["tags"])
    }

    def flush_ecdict_rows() -> None:
        if lookup_rows:
            db.executemany(
                """
                INSERT INTO ecdict_lookup (
                    word_key, word, translation, raw_pos, exchange,
                    phonetic, definition, frequency, source_tags
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(word_key) DO UPDATE SET
                    word = excluded.word,
                    translation = excluded.translation,
                    raw_pos = excluded.raw_pos,
                    exchange = excluded.exchange,
                    phonetic = excluded.phonetic,
                    definition = excluded.definition,
                    frequency = excluded.frequency,
                    source_tags = excluded.source_tags
                WHERE (ecdict_lookup.frequency IS NULL AND excluded.frequency IS NOT NULL)
                   OR (ecdict_lookup.frequency IS NOT NULL AND excluded.frequency IS NOT NULL
                       AND excluded.frequency < ecdict_lookup.frequency)
                """,
                lookup_rows,
            )
            lookup_rows.clear()
        if preset_rows:
            db.executemany(
                """
                INSERT INTO ecdict_preset_entries (
                    word, part_of_speech, meaning, phonetic,
                    definition, frequency, source_tags
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(word, part_of_speech) DO UPDATE SET
                    meaning = CASE
                        WHEN instr(ecdict_preset_entries.meaning, excluded.meaning) > 0
                            THEN ecdict_preset_entries.meaning
                        ELSE ecdict_preset_entries.meaning || '；' || excluded.meaning
                    END,
                    phonetic = COALESCE(ecdict_preset_entries.phonetic, excluded.phonetic),
                    definition = COALESCE(ecdict_preset_entries.definition, excluded.definition),
                    frequency = CASE
                        WHEN ecdict_preset_entries.frequency IS NULL THEN excluded.frequency
                        WHEN excluded.frequency IS NULL THEN ecdict_preset_entries.frequency
                        ELSE MIN(ecdict_preset_entries.frequency, excluded.frequency)
                    END,
                    source_tags = COALESCE(ecdict_preset_entries.source_tags, excluded.source_tags)
                """,
                preset_rows,
            )
            preset_rows.clear()

    for row in reader:
        normalized = {(key or "").strip().lower(): (value or "").strip() for key, value in row.items()}
        word = normalized.get("word", "")
        word_key = word.lower()
        if not word_key:
            continue

        row_tags = split_ecdict_tags(normalized.get("tag", ""))
        if row_tags & supported_preset_tags and normalized.get("translation"):
            fallback_pos = infer_ecdict_fallback_pos(normalized)
            for part_of_speech, entry_meaning in split_ecdict_translation(
                normalized.get("translation", ""), fallback_pos
            ):
                if entry_meaning:
                    normalized_part = normalize_user_pos(part_of_speech)
                    entry_meaning = ECDICT_MEANING_CORRECTIONS.get(
                        (word_key, normalized_part), entry_meaning
                    )
                    preset_rows.append(
                        (
                            word,
                            normalized_part,
                            entry_meaning,
                            normalized.get("phonetic") or None,
                            format_ecdict_definition(normalized.get("definition", "")) or None,
                            normalize_ecdict_frequency(normalized),
                            normalized.get("tag") or None,
                        )
                    )

        lookup_rows.append(
            (
                word_key,
                word,
                normalized.get("translation") or None,
                normalized.get("pos") or None,
                normalized.get("exchange") or None,
                normalized.get("phonetic") or None,
                format_ecdict_definition(normalized.get("definition", "")) or None,
                normalize_ecdict_frequency(normalized),
                normalized.get("tag") or None,
            )
        )
        if len(lookup_rows) >= 5000 or len(preset_rows) >= 5000:
            flush_ecdict_rows()
    flush_ecdict_rows()
    db.execute(
        "CREATE INDEX idx_ecdict_preset_tags_frequency "
        "ON ecdict_preset_entries(source_tags, frequency, word)"
    )
    db.execute(
        """
        INSERT INTO metadata (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        ("ecdict_lookup_signature", signature),
    )
    db.commit()


def lookup_ecdict_word(word: str) -> sqlite3.Row | None:
    if not word.strip():
        return None
    ensure_ecdict_lookup_index()
    # When no ECDICT resource is available (e.g. released packages ship without
    # the large csv), ensure_ecdict_lookup_index() returns early and the
    # ecdict_lookup table is never created. Treat that as "no enrichment
    # available" instead of letting the missing table raise a 500.
    try:
        return get_db().execute(
            """
            SELECT phonetic, definition, frequency, source_tags
            FROM ecdict_lookup
            WHERE word_key = ?
            """,
            (word.strip().lower(),),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
