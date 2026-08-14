"""EFLLex ingestion and CEFR profile lookup.

EFLLex contains normalized frequencies at each CEFR level rather than a
publisher-assigned single label.  ``provisional_level`` is therefore the first
level with a non-zero attestation and must remain auditable, not presented as
an authoritative sense-level rating.
"""

from __future__ import annotations

import csv
import hashlib
import sqlite3
from pathlib import Path

from .parts import canonical_part

LEVELS = ("A1", "A2", "B1", "B2", "C1")
NLP4J_PARTS = {
    "NN": "n", "JJ": "adj", "VB": "v", "RB": "adv", "CD": "num",
    "IN": "prep", "UH": "interj", "PRP": "pron", "PRP$": "pron",
    "WP": "pron", "WP$": "pron", "DT": "det", "WDT": "det",
    "PDT": "det", "RP": "adv", "MD": "aux", "CC": "conj",
    "TO": "prep", "EX": "pron", "WRB": "adv", "PR": "pron",
    "RH": "adv", "FW": "phrase", "XX": "phrase",
}


def normalize_efllex_pos(tag: str) -> str:
    return canonical_part(NLP4J_PARTS.get(tag.strip().upper(), "phrase"))


def normalize_efllex_word(word: str) -> str:
    """Convert EFLLex's underscore-separated multiword notation to text."""
    return " ".join(word.strip().casefold().replace("_", " ").split())


def source_signature(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def provisional_level(row: dict[str, str]) -> str | None:
    for level in LEVELS:
        try:
            if float(row.get(f"level_freq@{level.lower()}", "0") or 0) > 0:
                return level
        except ValueError:
            continue
    return None


def ensure_efllex_index(db: sqlite3.Connection, path: Path) -> int:
    """Build or refresh the compact EFLLex profile table."""
    if not path.is_file():
        return 0
    signature = source_signature(path)
    current = db.execute(
        "SELECT value FROM metadata WHERE key = 'efllex_source_signature'"
    ).fetchone()
    exists = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='efllex_profiles'"
    ).fetchone()
    if current and current[0] == signature and exists:
        return int(db.execute("SELECT COUNT(*) FROM efllex_profiles").fetchone()[0])

    db.execute("DROP TABLE IF EXISTS efllex_profiles")
    db.execute(
        """
        CREATE TABLE efllex_profiles (
            word_key TEXT NOT NULL,
            source_pos TEXT NOT NULL,
            part_group TEXT NOT NULL,
            provisional_level TEXT,
            frequency_a1 REAL NOT NULL,
            frequency_a2 REAL NOT NULL,
            frequency_b1 REAL NOT NULL,
            frequency_b2 REAL NOT NULL,
            frequency_c1 REAL NOT NULL,
            documents_a1 INTEGER NOT NULL,
            documents_a2 INTEGER NOT NULL,
            documents_b1 INTEGER NOT NULL,
            documents_b2 INTEGER NOT NULL,
            documents_c1 INTEGER NOT NULL,
            total_frequency REAL NOT NULL,
            total_documents INTEGER NOT NULL,
            source TEXT NOT NULL DEFAULT 'EFLLex',
            license TEXT NOT NULL DEFAULT 'CC BY-NC-SA 4.0',
            PRIMARY KEY(word_key, source_pos)
        )
        """
    )
    rows: list[tuple[object, ...]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            word = normalize_efllex_word(str(row.get("word") or ""))
            source_pos = str(row.get("tag") or "").strip().upper()
            if not word or not source_pos:
                continue
            rows.append((
                word, source_pos, normalize_efllex_pos(source_pos), provisional_level(row),
                *(float(row.get(f"level_freq@{level.lower()}", "0") or 0) for level in LEVELS),
                *(int(float(row.get(f"nb_doc@{level.lower()}", "0") or 0)) for level in LEVELS),
                float(row.get("total_freq@total", "0") or 0),
                int(float(row.get("nb_doc@total", "0") or 0)),
            ))
    db.executemany(
        """
        INSERT INTO efllex_profiles (
            word_key, source_pos, part_group, provisional_level,
            frequency_a1, frequency_a2, frequency_b1, frequency_b2, frequency_c1,
            documents_a1, documents_a2, documents_b1, documents_b2, documents_c1,
            total_frequency, total_documents
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(word_key, source_pos) DO UPDATE SET
            frequency_a1 = frequency_a1 + excluded.frequency_a1,
            frequency_a2 = frequency_a2 + excluded.frequency_a2,
            frequency_b1 = frequency_b1 + excluded.frequency_b1,
            frequency_b2 = frequency_b2 + excluded.frequency_b2,
            frequency_c1 = frequency_c1 + excluded.frequency_c1,
            documents_a1 = documents_a1 + excluded.documents_a1,
            documents_a2 = documents_a2 + excluded.documents_a2,
            documents_b1 = documents_b1 + excluded.documents_b1,
            documents_b2 = documents_b2 + excluded.documents_b2,
            documents_c1 = documents_c1 + excluded.documents_c1,
            total_frequency = total_frequency + excluded.total_frequency,
            total_documents = total_documents + excluded.total_documents,
            provisional_level = CASE
                WHEN provisional_level IS NULL THEN excluded.provisional_level
                WHEN excluded.provisional_level IS NULL THEN provisional_level
                WHEN excluded.provisional_level < provisional_level THEN excluded.provisional_level
                ELSE provisional_level
            END
        """,
        rows,
    )
    db.execute(
        "CREATE INDEX idx_efllex_word_part ON efllex_profiles(word_key, part_group, provisional_level)"
    )
    db.execute(
        "INSERT INTO metadata(key, value) VALUES('efllex_source_signature', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (signature,),
    )
    db.commit()
    return int(db.execute("SELECT COUNT(*) FROM efllex_profiles").fetchone()[0])
