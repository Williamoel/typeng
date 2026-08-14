"""Batch-index Wiktionary data for every word in the local TypEng database."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app


def main() -> None:
    with app.app.app_context():
        app.init_db()
        app.ensure_ecdict_lookup_index()
        words = {
            str(row["word"]).strip().lower()
            for row in app.get_db().execute("SELECT DISTINCT word FROM words")
            if str(row["word"] or "").strip()
        }
        if app.get_db().execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ecdict_preset_entries'"
        ).fetchone():
            words.update(
                str(row["word"]).strip().lower()
                for row in app.get_db().execute("SELECT DISTINCT word FROM ecdict_preset_entries")
                if str(row["word"] or "").strip()
            )
        if not words:
            print("No vocabulary to index.")
            return
        if not app.wiktionary_jsonl_path():
            raise SystemExit("Wiktionary JSONL was not found; nothing was indexed.")
        print(f"Indexing {len(words):,} current and preset vocabulary spellings in one Wiktionary pass...")
        app.ensure_wiktionary_lookup_index(words)
        db = app.get_db()
        indexed = int(db.execute("SELECT COUNT(*) FROM wiktionary_indexed_words").fetchone()[0])
        examples = int(db.execute("SELECT COUNT(*) FROM wiktionary_examples").fetchone()[0])
        definitions = int(db.execute("SELECT COUNT(*) FROM wiktionary_definitions").fetchone()[0])
        print(f"Done: {indexed:,} indexed words, {definitions:,} definitions, {examples:,} examples.")


if __name__ == "__main__":
    main()
