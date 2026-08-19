"""Apply the current Wiktionary/EFLLex policy to existing preset libraries."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app


def main() -> None:
    with app.app.app_context():
        app.init_db()
        db = app.get_db()
        preset_keys = {
            str(config["name"]): key
            for key, config in app.ECDICT_PRESET_LIBRARIES.items()
        }
        libraries = db.execute("SELECT id, name FROM libraries ORDER BY id").fetchall()
        clean_meanings = {
            (str(row["word"]).casefold(), app.normalize_user_pos(str(row["part_of_speech"]))): str(row["meaning"])
            for row in db.execute(
                "SELECT word, part_of_speech, meaning FROM ecdict_preset_entries"
            )
            if str(row["meaning"] or "").strip()
        }
        total_removed = 0
        total_updated = 0
        for library in libraries:
            name = str(library["name"])
            base_name = next(
                (base for base in preset_keys if name == base or name.startswith(f"{base} (")),
                None,
            )
            if base_name is None:
                continue
            rows = db.execute(
                "SELECT * FROM words WHERE library_id = ? AND source = 'ECDICT'",
                (int(library["id"]),),
            ).fetchall()
            entries = []
            for row in rows:
                entry = dict(row)
                clean_meaning = clean_meanings.get(
                    (str(row["word"]).casefold(), app.normalize_user_pos(str(row["part_of_speech"])))
                )
                if clean_meaning:
                    entry["meaning"] = clean_meaning
                entries.append(entry)
            if not entries:
                continue
            kept, stats = app.apply_exam_policy(db, preset_keys[base_name], entries)
            if stats.get("wiktionary_definitions_unavailable"):
                raise SystemExit("Wiktionary English definitions are unavailable; no libraries were changed.")
            kept_by_id = {int(entry["id"]): entry for entry in kept}
            removed_ids = [int(row["id"]) for row in rows if int(row["id"]) not in kept_by_id]
            for start in range(0, len(removed_ids), 500):
                batch = removed_ids[start:start + 500]
                placeholders = ",".join("?" for _ in batch)
                db.execute(
                    f"DELETE FROM words WHERE library_id = ? AND id IN ({placeholders})",
                    [int(library["id"]), *batch],
                )
            for word_id, entry in kept_by_id.items():
                db.execute(
                    "UPDATE words SET word = ?, part_of_speech = ?, meaning = ?, definition = ?, updated_at = CURRENT_TIMESTAMP "
                    "WHERE id = ? AND library_id = ?",
                    (
                        entry["word"],
                        entry["part_of_speech"],
                        entry["meaning"],
                        entry["definition"],
                        word_id,
                        int(library["id"]),
                    ),
                )
            db.commit()
            total_removed += len(removed_ids)
            total_updated += len(kept_by_id)
            print(
                f"{name}: kept {len(kept_by_id):,}, removed {len(removed_ids):,} "
                f"(missing definition {stats.get('removed_missing_definition', 0):,})."
            )
        print(f"Done: updated {total_updated:,} entries and removed {total_removed:,} invalid entries.")


if __name__ == "__main__":
    main()
