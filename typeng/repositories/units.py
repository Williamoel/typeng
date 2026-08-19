"""Stable organizational units that do not backfill after word deletion."""

from __future__ import annotations

import sqlite3

UNIT_SIZE = 100

ORDER_SQL = """
    CASE WHEN frequency IS NULL THEN 1 ELSE 0 END ASC,
    frequency ASC,
    lower(word) ASC,
    part_of_speech ASC,
    id ASC
"""


def _has_registry(db: sqlite3.Connection) -> bool:
    return db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'library_units'"
    ).fetchone() is not None


def register_existing(db: sqlite3.Connection, library_id: int) -> None:
    if not _has_registry(db):
        return
    db.execute(
        """
        INSERT OR IGNORE INTO library_units (library_id, unit_number)
        SELECT DISTINCT library_id, unit_number FROM words
        WHERE library_id = ? AND unit_number IS NOT NULL
        """,
        (library_id,),
    )


def create(db: sqlite3.Connection, library_id: int) -> int:
    """Append and persist an empty organizational unit."""
    if not _has_registry(db):
        raise RuntimeError("library unit registry is unavailable")
    register_existing(db, library_id)
    row = db.execute(
        "SELECT COALESCE(MAX(unit_number), 0) + 1 FROM library_units WHERE library_id = ?",
        (library_id,),
    ).fetchone()
    number = max(1, int(row[0]))
    db.execute(
        "INSERT INTO library_units (library_id, unit_number) VALUES (?, ?)",
        (library_id, number),
    )
    db.commit()
    return number


def count(db: sqlite3.Connection, library_id: int, status: str | None = None) -> int:
    sql = "SELECT COUNT(*) FROM words WHERE library_id = ?"
    params: list[object] = [library_id]
    if status:
        sql += " AND status = ?"
        params.append(status)
    return int(db.execute(sql, params).fetchone()[0])


def assign_unassigned(
    db: sqlite3.Connection,
    library_id: int | None = None,
    unit_size: int = UNIT_SIZE,
) -> int:
    """Append words without a unit while preserving all existing boundaries."""
    columns = {str(row[1]) for row in db.execute("PRAGMA table_info(words)").fetchall()}
    if not {"unit_number", "unit_position"} <= columns:
        return 0
    library_sql = "SELECT DISTINCT library_id FROM words WHERE unit_number IS NULL"
    params: list[object] = []
    if library_id is not None:
        library_sql += " AND library_id = ?"
        params.append(library_id)
    library_ids = [int(row[0]) for row in db.execute(library_sql, params).fetchall()]
    assigned = 0

    for current_library_id in library_ids:
        register_existing(db, current_library_id)
        last = db.execute(
            """
            SELECT unit_number, MAX(unit_position) AS last_position
            FROM words
            WHERE library_id = ? AND unit_number IS NOT NULL
            GROUP BY unit_number
            ORDER BY unit_number DESC
            LIMIT 1
            """,
            (current_library_id,),
        ).fetchone()
        unit_number = int(last["unit_number"]) if last else 1
        unit_position = int(last["last_position"] or 0) if last else 0
        if _has_registry(db):
            registered = db.execute(
                "SELECT MAX(unit_number) FROM library_units WHERE library_id = ?",
                (current_library_id,),
            ).fetchone()[0]
            if registered is not None and int(registered) > unit_number:
                unit_number = int(registered)
                unit_position = 0
        rows = db.execute(
            f"""
            SELECT id FROM words
            WHERE library_id = ? AND unit_number IS NULL
            ORDER BY {ORDER_SQL}
            """,
            (current_library_id,),
        ).fetchall()
        for row in rows:
            if unit_position >= unit_size:
                unit_number += 1
                unit_position = 0
            unit_position += 1
            db.execute(
                "UPDATE words SET unit_number = ?, unit_position = ? WHERE id = ?",
                (unit_number, unit_position, int(row["id"])),
            )
            assigned += 1
        register_existing(db, current_library_id)
    return assigned


def compact_empty_units(db: sqlite3.Connection, library_id: int) -> int:
    """Remove numbering gaps only when an entire physical unit is empty."""
    numbers = [
        int(row[0])
        for row in db.execute(
            """
            SELECT DISTINCT unit_number FROM words
            WHERE library_id = ? AND unit_number IS NOT NULL
            ORDER BY unit_number
            """,
            (library_id,),
        ).fetchall()
    ]
    if _has_registry(db):
        db.execute(
            "DELETE FROM library_units WHERE library_id = ? AND unit_number NOT IN "
            "(SELECT DISTINCT unit_number FROM words WHERE library_id = ? AND unit_number IS NOT NULL)",
            (library_id, library_id),
        )
    changed = 0
    for new_number, old_number in enumerate(numbers, start=1):
        if new_number == old_number:
            continue
        cursor = db.execute(
            "UPDATE words SET unit_number = ? WHERE library_id = ? AND unit_number = ?",
            (new_number, library_id, old_number),
        )
        changed += int(cursor.rowcount)
        if _has_registry(db):
            db.execute(
                "UPDATE library_units SET unit_number = ? WHERE library_id = ? AND unit_number = ?",
                (-new_number, library_id, old_number),
            )
    if _has_registry(db):
        db.execute(
            "UPDATE library_units SET unit_number = -unit_number WHERE library_id = ? AND unit_number < 0",
            (library_id,),
        )
    return changed


def place_words(
    db: sqlite3.Connection,
    library_id: int,
    word_ids: list[int],
    unit_number: int,
) -> int:
    """Append selected words to an explicit unit without moving other words."""
    if not word_ids:
        return 0
    unit_number = max(1, unit_number)
    if _has_registry(db):
        db.execute(
            "INSERT OR IGNORE INTO library_units (library_id, unit_number) VALUES (?, ?)",
            (library_id, unit_number),
        )
    last_position = int(
        db.execute(
            "SELECT COALESCE(MAX(unit_position), 0) FROM words WHERE library_id = ? AND unit_number = ?",
            (library_id, unit_number),
        ).fetchone()[0]
    )
    moved = 0
    for offset, word_id in enumerate(word_ids, start=1):
        cursor = db.execute(
            """
            UPDATE words SET unit_number = ?, unit_position = ?
            WHERE id = ? AND library_id = ?
            """,
            (unit_number, last_position + offset, word_id, library_id),
        )
        moved += int(cursor.rowcount)
    return moved


def summaries(
    db: sqlite3.Connection,
    library_id: int,
    status: str | None = None,
    unit_size: int = UNIT_SIZE,
) -> list[dict[str, int]]:
    assign_unassigned(db, library_id, unit_size)
    if status is None:
        status_count_sql = "COUNT(*)"
        params: list[object] = [library_id]
    else:
        status_count_sql = "SUM(CASE WHEN status = ? THEN 1 ELSE 0 END)"
        params = [status, library_id]
    register_existing(db, library_id)
    if _has_registry(db):
        status_join = "COUNT(words.id)" if status is None else "SUM(CASE WHEN words.status = ? THEN 1 ELSE 0 END)"
        join_params: list[object] = [library_id] if status is None else [status, library_id]
        rows = db.execute(
            f"""
            SELECT library_units.unit_number, COUNT(words.id) AS total_count,
                   {status_join} AS status_count
            FROM library_units
            LEFT JOIN words ON words.library_id = library_units.library_id
                           AND words.unit_number = library_units.unit_number
            WHERE library_units.library_id = ?
            GROUP BY library_units.unit_number
            ORDER BY library_units.unit_number
            """,
            join_params,
        ).fetchall()
    else:
        rows = db.execute(
            f"""
            SELECT unit_number, COUNT(*) AS total_count,
                   {status_count_sql} AS status_count
            FROM words
            WHERE library_id = ? AND unit_number IS NOT NULL
            GROUP BY unit_number
            ORDER BY unit_number
            """,
            params,
        ).fetchall()
    cumulative = 0
    result: list[dict[str, int]] = []
    for row in rows:
        total_count = int(row["total_count"])
        result.append(
            {
                "number": int(row["unit_number"]),
                "start": cumulative + 1,
                "end": cumulative + total_count,
                "count": int(row["status_count"] or 0),
                "total_count": total_count,
            }
        )
        cumulative += total_count
    return result


def fetch(
    db: sqlite3.Connection,
    library_id: int,
    unit_number: int,
    status: str | None = None,
    unit_size: int = UNIT_SIZE,
) -> list[sqlite3.Row]:
    assign_unassigned(db, library_id, unit_size)
    sql = "SELECT * FROM words WHERE library_id = ?"
    params: list[object] = [library_id]
    sql += " AND unit_number = ?"
    params.append(max(1, unit_number))
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY unit_position ASC, id ASC"
    return db.execute(sql, params).fetchall()


def search_words(
    db: sqlite3.Connection,
    library_id: int,
    query: str,
    limit: int = 200,
) -> list[sqlite3.Row]:
    """Search English headwords in one library; meanings are never queried."""
    query = query.strip().casefold()
    if not query:
        return []
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return db.execute(
        """
        SELECT * FROM words
        WHERE library_id = ? AND lower(word) LIKE ? ESCAPE '\\'
        ORDER BY
            CASE WHEN lower(word) = ? THEN 0 ELSE 1 END,
            lower(word), part_of_speech, unit_number, unit_position, id
        LIMIT ?
        """,
        (library_id, f"%{escaped}%", query, limit),
    ).fetchall()


def fetch_batch(
    db: sqlite3.Connection,
    library_id: int,
    status: str,
    limit: int,
) -> list[sqlite3.Row]:
    """Build a practice batch across unit boundaries in stable unit order."""
    assign_unassigned(db, library_id)
    return db.execute(
        """
        SELECT id, word, example_sentence FROM words
        WHERE library_id = ? AND status = ?
        ORDER BY unit_number ASC, unit_position ASC, id ASC
        LIMIT ?
        """,
        (library_id, status, limit),
    ).fetchall()
