"""Report the exact effects of the exam preset filtering policy."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from typeng.cefr import ensure_efllex_index
from typeng.constants import ECDICT_PRESET_LIBRARIES
from typeng.domain import parse_ecdict_csv
from typeng.parts import lexical_part
from typeng.preset_policy import EXAM_MIN_LEVEL, apply_exam_policy, ensure_wiktionary_exam_pos_index


def unique_pairs(entries: list[dict[str, object]]) -> set[tuple[str, str]]:
    return {
        (
            str(entry.get("word") or "").strip().casefold(),
            lexical_part(str(entry.get("part_of_speech") or "")),
        )
        for entry in entries
    }


def render(report: dict[str, object]) -> str:
    lines = [
        "# Exam preset policy audit",
        "",
        "Wiktionary POS validation uses the normalized POS-presence index and does not require an example.",
        "EFLLex removes only classified entries below each exam's minimum; unclassified entries stay.",
        "",
        "| Exam | Minimum | Candidates | Removed POS | Removed basic | Retained | Retained % |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for key, row in report["exams"].items():
        lines.append(
            f"| {key.upper()} | {row['minimum']}+ | {row['candidate_pairs']:,} | "
            f"{row['removed_wiktionary_pos']:,} | {row['removed_basic']:,} | "
            f"{row['retained_pairs']:,} | {row['retained_percent']}% |"
        )
    lines.extend([
        "",
        "Entries absent from EFLLex are retained. Entries without usable Wiktionary examples are retained.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ecdict", type=Path, required=True)
    parser.add_argument("--efllex", type=Path, required=True)
    parser.add_argument("--wiktionary-pos", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    args = parser.parse_args()

    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    ensure_efllex_index(db, args.efllex)
    ensure_wiktionary_exam_pos_index(db, args.wiktionary_pos)
    grouped, errors = parse_ecdict_csv(args.ecdict.read_bytes())
    if errors:
        raise SystemExit(" ".join(errors))

    exams: dict[str, object] = {}
    for key, config in ECDICT_PRESET_LIBRARIES.items():
        source = grouped.get(str(config["name"]), [])
        unique_source = list({
            (
                str(entry.get("word") or "").strip().casefold(),
                lexical_part(str(entry.get("part_of_speech") or "")),
            ): entry
            for entry in source
        }.values())
        filtered, stats = apply_exam_policy(db, key, unique_source)
        candidates = unique_pairs(unique_source)
        retained = unique_pairs(filtered)
        exams[key] = {
            "minimum": EXAM_MIN_LEVEL[key],
            "candidate_pairs": len(candidates),
            "removed_wiktionary_pos": stats.get("removed_wiktionary_pos", 0),
            "removed_basic": stats.get("removed_basic", 0),
            "retained_pairs": len(retained),
            "retained_percent": round(100 * len(retained) / len(candidates), 2) if candidates else 0,
        }
    report: dict[str, object] = {
        "policy": {key: f"{level}+" for key, level in EXAM_MIN_LEVEL.items()},
        "exams": exams,
    }
    markdown = render(report)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.output_markdown.write_text(markdown, encoding="utf-8")
    print(markdown)


if __name__ == "__main__":
    main()
