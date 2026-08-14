"""Build and install portable, pre-indexed TypEng lexicon databases.

Raw dictionary exports are maintainer inputs.  End users should receive the
small SQLite lookup database produced here instead of multi-gigabyte JSONL and
CSV files that have to be parsed during a request.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


CACHE_SCHEMA_VERSION = 3
CACHE_TABLES = (
    "ecdict_lookup",
    "ecdict_preset_entries",
    "efllex_profiles",
    "wiktionary_examples",
    "wiktionary_definitions",
    "wiktionary_indexed_words",
    "wiktionary_exam_parts",
)
SIGNATURE_KEYS = (
    "ecdict_lookup_signature",
    "efllex_source_signature",
    "wiktionary_lookup_signature",
    "wiktionary_exam_pos_signature",
)


def table_exists(db: sqlite3.Connection, table_name: str, schema: str = "main") -> bool:
    row = db.execute(
        f"SELECT 1 FROM {schema}.sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def lookup_available(db: sqlite3.Connection, table_name: str) -> bool:
    """Return whether a prebuilt or locally generated lookup table is usable."""

    return table_exists(db, table_name)


def _copy_table(source: sqlite3.Connection, destination: sqlite3.Connection, table_name: str) -> None:
    create_row = source.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    if not create_row or not create_row[0]:
        return
    destination.execute(create_row[0])
    columns = [row[1] for row in source.execute(f"PRAGMA table_info({table_name})")]
    placeholders = ",".join("?" for _ in columns)
    insert_sql = f"INSERT INTO {table_name} ({','.join(columns)}) VALUES ({placeholders})"
    cursor = source.execute(f"SELECT {','.join(columns)} FROM {table_name}")
    while rows := cursor.fetchmany(5000):
        destination.executemany(insert_sql, rows)
    for index_row in source.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'index' AND tbl_name = ? AND sql IS NOT NULL",
        (table_name,),
    ):
        destination.execute(index_row[0])


def export_cache(source_path: Path, destination_path: Path) -> dict[str, int]:
    """Export lookup-only tables from an application DB to a portable cache."""

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    if destination_path.exists():
        destination_path.unlink()
    source = sqlite3.connect(source_path)
    destination = sqlite3.connect(destination_path)
    counts: dict[str, int] = {}
    try:
        destination.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        destination.execute(
            "INSERT INTO metadata (key, value) VALUES ('lexicon_cache_schema_version', ?)",
            (str(CACHE_SCHEMA_VERSION),),
        )
        for key in SIGNATURE_KEYS:
            if not table_exists(source, "metadata"):
                break
            row = source.execute("SELECT value FROM metadata WHERE key = ?", (key,)).fetchone()
            if row:
                destination.execute("INSERT INTO metadata (key, value) VALUES (?, ?)", (key, row[0]))
        for table_name in CACHE_TABLES:
            if not table_exists(source, table_name):
                continue
            _copy_table(source, destination, table_name)
            counts[table_name] = int(source.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])
        destination.commit()
        destination.execute("VACUUM")
    finally:
        source.close()
        destination.close()
    return counts


def install_prebuilt_cache(db: sqlite3.Connection, cache_path: Path) -> bool:
    """Seed missing lookup tables from a prebuilt cache.

    Existing tables are preserved so locally indexed Wiktionary data is never
    discarded. The one exception is an older ECDICT table missing columns that
    the cache requires; it is upgraded from the cache. The operation is atomic.
    """

    if not cache_path.is_file():
        return False
    installed_row = db.execute(
        "SELECT value FROM metadata WHERE key = 'installed_lexicon_cache_version'"
    ).fetchone()
    if installed_row and int(installed_row[0]) == CACHE_SCHEMA_VERSION:
        return False
    cache = sqlite3.connect(cache_path)
    try:
        version_row = cache.execute(
            "SELECT value FROM metadata WHERE key = 'lexicon_cache_schema_version'"
        ).fetchone()
        if not version_row or int(version_row[0]) != CACHE_SCHEMA_VERSION:
            raise ValueError("Unsupported TypEng lexicon cache schema")
        db.execute("SAVEPOINT install_lexicon_cache")
        installed_any = False
        try:
            for table_name in CACHE_TABLES:
                if not table_exists(cache, table_name):
                    continue
                if table_exists(db, table_name):
                    cache_columns = {row[1] for row in cache.execute(f"PRAGMA table_info({table_name})")}
                    target_columns = {row[1] for row in db.execute(f"PRAGMA table_info({table_name})")}
                    if not (table_name.startswith("ecdict_") and not cache_columns <= target_columns):
                        continue
                    db.execute(f"DROP TABLE {table_name}")
                _copy_table(cache, db, table_name)
                installed_any = True
            for key in SIGNATURE_KEYS:
                row = cache.execute("SELECT value FROM metadata WHERE key = ?", (key,)).fetchone()
                if row:
                    db.execute(
                        "INSERT INTO metadata (key, value) VALUES (?, ?) "
                        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                        (key, row[0]),
                    )
            db.execute(
                "INSERT INTO metadata (key, value) VALUES ('installed_lexicon_cache_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (str(CACHE_SCHEMA_VERSION),),
            )
            db.execute("RELEASE install_lexicon_cache")
        except Exception:
            db.execute("ROLLBACK TO install_lexicon_cache")
            db.execute("RELEASE install_lexicon_cache")
            raise
    finally:
        cache.close()
    return installed_any
