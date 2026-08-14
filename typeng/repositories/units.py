"""Stable, dynamically compacted 100-word views over a library."""

from __future__ import annotations

import math
import sqlite3

UNIT_SIZE = 100

ORDER_SQL = """
    CASE WHEN frequency IS NULL THEN 1 ELSE 0 END ASC,
    frequency ASC,
    lower(word) ASC,
    part_of_speech ASC,
    id ASC
"""


def count(db: sqlite3.Connection, library_id: int, status: str | None = None) -> int:
    sql = "SELECT COUNT(*) FROM words WHERE library_id = ?"
    params: list[object] = [library_id]
    if status:
        sql += " AND status = ?"
        params.append(status)
    return int(db.execute(sql, params).fetchone()[0])


def summaries(
    db: sqlite3.Connection,
    library_id: int,
    status: str | None = None,
    unit_size: int = UNIT_SIZE,
) -> list[dict[str, int]]:
    total = count(db, library_id, status)
    return [
        {
            "number": number,
            "start": (number - 1) * unit_size + 1,
            "end": min(number * unit_size, total),
            "count": min(unit_size, total - (number - 1) * unit_size),
        }
        for number in range(1, math.ceil(total / unit_size) + 1)
    ]


def fetch(
    db: sqlite3.Connection,
    library_id: int,
    unit_number: int,
    status: str | None = None,
    unit_size: int = UNIT_SIZE,
) -> list[sqlite3.Row]:
    sql = "SELECT * FROM words WHERE library_id = ?"
    params: list[object] = [library_id]
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += f" ORDER BY {ORDER_SQL} LIMIT ? OFFSET ?"
    params.extend([unit_size, max(0, unit_number - 1) * unit_size])
    return db.execute(sql, params).fetchall()

