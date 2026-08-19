"""Wiktionary/Kaikki streaming index and lookup engine."""

from __future__ import annotations

import csv
import json
import re
import sqlite3
from collections.abc import Callable
from pathlib import Path

from ..constants import (
    BLOCKED_WIKTIONARY_DEFINITION_TAGS,
    NON_LEXICAL_WIKTIONARY_TAGS,
)
from ..parts import CANONICAL_PARTS

from ..domain import (
    english_word_count,
    cloze_prompt,
    extract_example_sentence,
    normalize_wiktionary_pos,
    sentence_quality_score,
    spelling_variants,
    usable_wiktionary_example,
    wiktionary_usage_label,
    wiktionary_definition_display,
    wiktionary_example_rank,
    wiktionary_lookup_groups,
)

_db_provider: Callable[[], sqlite3.Connection] | None = None
_path_provider: Callable[[], Path | None] | None = None
_signature_provider: Callable[[], str | None] | None = None
_available_provider: Callable[[], bool] | None = None
_usage_patterns_provider: Callable[[], Path] | None = None


def _raw_gloss_labels(sense: dict[str, object]) -> set[str]:
    """Recover labels that Kaikki leaves only in ``raw_glosses``.

    This is deliberately generic: jury's ``nautical`` label is one example,
    but the same rule also retains fields such as medicine, falconry,
    idiomatic, and regional/register qualifiers for every word.
    """
    raw_glosses = sense.get("raw_glosses") or []
    if not isinstance(raw_glosses, list) or not raw_glosses:
        return set()
    match = re.match(r"^\(([^)]{1,160})\)\s*", str(raw_glosses[-1]))
    if not match:
        return set()
    labels: set[str] = set()
    for raw_label in match.group(1).split(","):
        label = raw_label.strip().casefold()
        label = re.sub(r"^now\s+", "", label)
        label = re.sub(r"\s+", "-", label)
        if label:
            labels.add(label)
    return labels


def configure(
    db_provider, path_provider, signature_provider, available_provider,
    usage_patterns_provider=None,
) -> None:
    global _db_provider, _path_provider, _signature_provider, _available_provider
    global _usage_patterns_provider
    _db_provider = db_provider
    _path_provider = path_provider
    _signature_provider = signature_provider
    _available_provider = available_provider
    _usage_patterns_provider = usage_patterns_provider


def _fixed_expression(text: str, word: str) -> str | None:
    """Return a short phrase-like example containing the learning word."""
    expression = re.sub(r"\s+", " ", text).strip()
    if not expression or len(expression) > 140 or "\n" in text:
        return None
    if re.search(r"[.!?;:,]$|[:;]", expression):
        return None
    tokens = re.findall(r"[A-Za-z]+(?:[’'][A-Za-z]+)?", expression)
    if not 2 <= len(tokens) <= 12:
        return None
    return expression if cloze_prompt(expression, word) else None


def _is_fossil_sense(tags: set[str]) -> bool:
    return any("fossil" in tag or tag == "only-used-in" for tag in tags)


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
    headword_table_exists = db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        ("wiktionary_headwords",),
    ).fetchone()
    pattern_table_exists = db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        ("wiktionary_patterns",),
    ).fetchone()
    needs_rebuild = not (
        table_exists
        and definition_table_exists
        and indexed_table_exists
        and headword_table_exists
        and pattern_table_exists
        and existing
        and existing["value"] == signature
    )
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
        db.execute("DROP TABLE IF EXISTS wiktionary_headwords")
        db.execute("DROP TABLE IF EXISTS wiktionary_patterns")
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
            CREATE TABLE wiktionary_headwords (
                word_key TEXT PRIMARY KEY,
                canonical_word TEXT NOT NULL,
                case_rank INTEGER NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE wiktionary_patterns (
                word_key TEXT NOT NULL,
                part_group TEXT NOT NULL,
                expression TEXT NOT NULL,
                definition TEXT,
                sense_tags TEXT,
                sense_rank INTEGER,
                source_ref TEXT,
                UNIQUE(word_key, part_group, expression)
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
        db.execute("DROP INDEX IF EXISTS idx_wiktionary_patterns_word_part")

    words_to_index = normalized_targets

    rows: list[tuple[str, str, str, str | None, str | None, str | None, int, int]] = []
    definition_rows: list[tuple[str, str, str, str | None, int]] = []
    seen: set[tuple[str, str, str]] = set()
    seen_definitions: set[tuple[str, str, str]] = set()
    headwords: dict[str, tuple[int, str]] = {}
    pattern_rows: list[tuple[str, str, str, str | None, str | None, int | None, str | None]] = []
    seen_patterns: set[tuple[str, str, str]] = set()

    def flush_rows() -> None:
        nonlocal rows, definition_rows, pattern_rows
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
        if pattern_rows:
            db.executemany(
                """
                INSERT OR IGNORE INTO wiktionary_patterns (
                    word_key, part_group, expression, definition, sense_tags,
                    sense_rank, source_ref
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                pattern_rows,
            )
        rows = []
        definition_rows = []
        pattern_rows = []

    with path.open("rt", encoding="utf-8") as handle:
        for line in handle:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("lang_code") != "en":
                continue
            canonical_word = str(entry.get("word") or "").strip()
            word_key = canonical_word.casefold()
            if words_to_index is not None and word_key not in words_to_index:
                continue
            case_rank = 0 if canonical_word == word_key else (2 if canonical_word.isupper() else 1)
            current_headword = headwords.get(word_key)
            if current_headword is None or (case_rank, canonical_word) < current_headword:
                headwords[word_key] = (case_rank, canonical_word)
            part_group = normalize_wiktionary_pos(str(entry.get("pos") or ""))
            if not word_key or part_group not in (CANONICAL_PARTS - {"aux"}):
                continue
            senses = entry.get("senses") or []
            if not isinstance(senses, list):
                continue
            for sense_rank, sense in enumerate(senses):
                if not isinstance(sense, dict):
                    continue
                # Kaikki lists the inherited parent glosses first and the
                # concrete leaf sense last.  Joining the path made account v.
                # repeat "To provide explanation" before every real meaning.
                glosses = [
                    str(item).strip()
                    for item in sense.get("glosses", [])
                    if str(item).strip()
                ]
                definition = glosses[-1] if glosses else None
                sense_tags = ",".join(str(item).strip().lower() for item in sense.get("tags", []) if str(item).strip()) or None
                tag_set = {str(tag).strip().lower() for tag in sense.get("tags", []) if str(tag).strip()}
                tag_set.update(_raw_gloss_labels(sense))
                sense_tags = ",".join(sorted(tag_set)) or None
                blocked_definition = BLOCKED_WIKTIONARY_DEFINITION_TAGS & tag_set
                fossil_definition = _is_fossil_sense(tag_set) and not (
                    NON_LEXICAL_WIKTIONARY_TAGS & tag_set
                )
                if definition and (not blocked_definition or fossil_definition):
                    definition_key = (word_key, part_group, definition)
                    if definition_key not in seen_definitions:
                        seen_definitions.add(definition_key)
                        definition_rows.append((word_key, part_group, definition, sense_tags, sense_rank))
                examples = sense.get("examples") or []
                if not isinstance(examples, list):
                    continue
                if _is_fossil_sense(tag_set):
                    for example in examples:
                        if not isinstance(example, dict):
                            continue
                        expression = _fixed_expression(
                            str(example.get("text") or ""), word_key
                        )
                        if not expression:
                            continue
                        pattern_key = (word_key, part_group, expression.casefold())
                        if pattern_key in seen_patterns:
                            continue
                        seen_patterns.add(pattern_key)
                        pattern_rows.append(
                            (
                                word_key, part_group, expression, definition,
                                sense_tags, sense_rank, None,
                            )
                        )
                if BLOCKED_WIKTIONARY_DEFINITION_TAGS & tag_set:
                    continue
                for example in examples:
                    if not isinstance(example, dict):
                        continue
                    sentence = extract_example_sentence(
                        str(example.get("text") or ""),
                        word_key,
                        example.get("bold_text_offsets"),
                    )
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
                    if len(rows) + len(pattern_rows) >= 5000:
                        flush_rows()
                if len(definition_rows) >= 5000:
                    flush_rows()
    flush_rows()
    supplement_path = _usage_patterns_provider() if _usage_patterns_provider else None
    if supplement_path and supplement_path.is_file():
        with supplement_path.open("rt", encoding="utf-8", newline="") as handle:
            supplement_rows = []
            for item in csv.DictReader(handle, delimiter="\t"):
                supplement_word = str(item.get("word") or "").strip().casefold()
                if words_to_index is not None and supplement_word not in words_to_index:
                    continue
                supplement_part = normalize_wiktionary_pos(
                    str(item.get("part_of_speech") or "")
                )
                expression = _fixed_expression(
                    str(item.get("expression") or ""), supplement_word
                )
                if not expression or not supplement_part:
                    continue
                definition = str(item.get("definition") or "").strip() or None
                label = str(item.get("usage_label") or "").strip().replace(" ", "-") or None
                source_ref = str(item.get("source_url") or "").strip() or None
                sense_row = db.execute(
                    """
                    SELECT sense_rank FROM wiktionary_definitions
                    WHERE word_key = ? AND part_group = ? AND definition = ?
                    ORDER BY sense_rank LIMIT 1
                    """,
                    (supplement_word, supplement_part, definition),
                ).fetchone() if definition else None
                supplement_rows.append(
                    (
                        supplement_word, supplement_part, expression, definition,
                        label, int(sense_row["sense_rank"]) if sense_row else None,
                        source_ref,
                    )
                )
            db.executemany(
                """
                INSERT OR IGNORE INTO wiktionary_patterns (
                    word_key, part_group, expression, definition, sense_tags,
                    sense_rank, source_ref
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                supplement_rows,
            )
    if headwords:
        db.executemany(
            """
            INSERT INTO wiktionary_headwords(word_key, canonical_word, case_rank)
            VALUES (?, ?, ?)
            ON CONFLICT(word_key) DO UPDATE SET
                canonical_word = excluded.canonical_word,
                case_rank = excluded.case_rank
            WHERE excluded.case_rank < wiktionary_headwords.case_rank
            """,
            [(word, canonical, rank) for word, (rank, canonical) in headwords.items()],
        )
    if words_to_index is not None:
        db.executemany(
            "INSERT OR IGNORE INTO wiktionary_indexed_words (word_key) VALUES (?)",
            [(word,) for word in sorted(words_to_index)],
        )
    db.execute("CREATE INDEX idx_wiktionary_examples_word_part ON wiktionary_examples(word_key, part_group, sense_rank, example_rank)")
    db.execute("CREATE INDEX idx_wiktionary_definitions_word_part ON wiktionary_definitions(word_key, part_group, sense_rank)")
    db.execute("CREATE INDEX idx_wiktionary_patterns_word_part ON wiktionary_patterns(word_key, part_group, sense_rank)")
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
        SELECT example_sentence, definition, example_type, sense_tags, part_group, sense_rank
        FROM wiktionary_examples
        WHERE word_key IN ({key_placeholders}) AND part_group IN ({group_placeholders})
        ORDER BY example_rank ASC, sense_rank ASC, length(example_sentence) ASC
        """,
        (*word_keys, *lookup_groups),
    ).fetchall()
    blocked_tags = {"archaic", "obsolete"} | NON_LEXICAL_WIKTIONARY_TAGS
    dislike_tags = {"dated", "rare"}
    suitable: list[tuple[sqlite3.Row, set[str]]] = []
    for row in rows:
        s = row["example_sentence"]
        if not usable_wiktionary_example(s, word):
            continue
        tags = {tag.strip() for tag in str(row["sense_tags"] or "").split(",") if tag.strip()}
        if blocked_tags & tags:
            continue
        suitable.append((row, tags))
    complete = [
        (row, tags)
        for row, tags in suitable
        if not str(row["example_sentence"]).startswith("… ")
        and not str(row["example_sentence"]).endswith(" …")
    ]
    if complete:
        suitable = complete
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


def lookup_wiktionary_patterns(word: str, part_of_speech: str) -> list[dict[str, object]]:
    if not word.strip() or not _available():
        return []
    if get_db().execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'wiktionary_patterns'"
    ).fetchone() is None:
        return []
    word_keys = sorted(spelling_variants(word))
    lookup_groups = wiktionary_lookup_groups(part_of_speech, word)
    group_placeholders = ",".join("?" for _ in lookup_groups)
    key_placeholders = ",".join("?" for _ in word_keys)
    rows = get_db().execute(
        f"""
        SELECT expression, definition, sense_tags, sense_rank, source_ref
        FROM wiktionary_patterns
        WHERE word_key IN ({key_placeholders}) AND part_group IN ({group_placeholders})
        ORDER BY sense_rank, length(expression), expression
        """,
        (*word_keys, *lookup_groups),
    ).fetchall()
    result: list[dict[str, object]] = []
    seen: set[str] = set()
    for row in rows:
        expression = str(row["expression"] or "").strip()
        if not expression or expression.casefold() in seen:
            continue
        seen.add(expression.casefold())
        tags = str(row["sense_tags"] or "")
        usage_label = "fossil word" if "fossil" in tags else wiktionary_usage_label(tags)
        result.append(
            {
                "expression": expression,
                "definition": row["definition"],
                "sense_rank": row["sense_rank"],
                "usage_label": usage_label,
                "source": "wiktionary",
                "source_ref": row["source_ref"],
                "enabled_for_cloze": True,
                "is_user": False,
            }
        )
    return result


def lookup_wiktionary_definition_records(
    word: str,
    part_of_speech: str,
    limit: int | None = 4,
) -> list[dict[str, object]]:
    """Return numbered display definitions while retaining Wiktionary sense IDs."""
    if not word.strip() or not _available():
        return []
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
        """,
        (*word_keys, *lookup_groups),
    ).fetchall()
    if not rows:
        return []
    definitions: list[dict[str, object]] = []
    seen: set[str] = set()
    for row in rows:
        tags = {tag.strip() for tag in str(row["sense_tags"] or "").split(",") if tag.strip()}
        if BLOCKED_WIKTIONARY_DEFINITION_TAGS & tags and not (
            _is_fossil_sense(tags) and not (NON_LEXICAL_WIKTIONARY_TAGS & tags)
        ):
            continue
        definition = str(row["definition"] or "").strip()
        if not definition or definition in seen:
            continue
        seen.add(definition)
        usage_label = (
            "fossil word" if _is_fossil_sense(tags)
            else wiktionary_usage_label(str(row["sense_tags"] or ""))
        )
        display = wiktionary_definition_display(definition)
        if usage_label:
            display = f"[{usage_label}] {display}"
        definitions.append(
            {
                "definition": display,
                "raw_definition": definition,
                "sense_rank": int(row["sense_rank"]),
            }
        )
        if limit is not None and len(definitions) >= limit:
            break
    return definitions


def lookup_wiktionary_definition(word: str, part_of_speech: str) -> str | None:
    records = lookup_wiktionary_definition_records(word, part_of_speech)
    return "\n".join(str(record["definition"]) for record in records) if records else None
