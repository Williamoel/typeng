"""Report provisional EFLLex coverage for ECDICT exam candidates."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audit_lexicon_sources import EXAM_TAGS, load_candidates
from typeng.cefr import LEVELS, normalize_efllex_pos, normalize_efllex_word, provisional_level
from typeng.preset_policy import EXAM_MIN_LEVEL, LEVEL_RANK


def load_levels(path: Path) -> dict[tuple[str, str], str]:
    rank = {level: index for index, level in enumerate(LEVELS)}
    levels: dict[tuple[str, str], str] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            level = provisional_level(row)
            if level is None:
                continue
            key = (
                normalize_efllex_word(str(row.get("word") or "")),
                normalize_efllex_pos(str(row.get("tag") or "")),
            )
            current = levels.get(key)
            if current is None or rank[level] < rank[current]:
                levels[key] = level
    return levels


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# Provisional EFLLex distribution",
        "",
        "EFLLex publishes frequency profiles, not authoritative single CEFR labels.",
        "For this audit, a word+POS receives the earliest level with a non-zero attestation.",
        "EFLLex is used only to remove entries confirmed below each exam threshold; unclassified entries remain.",
        "",
        "| Exam | Pairs | A1 | A2 | B1 | B2 | C1 | Unclassified | Threshold | CEFR-retained |",
        "|---|---:|---:|---:|---:|---:|---:|---|---:|",
    ]
    for exam, values in report["exams"].items():
        counts = values["counts"]
        lines.append(
            f"| {exam.upper()} | {values['candidate_pairs']:,} | {counts['A1']:,} | "
            f"{counts['A2']:,} | {counts['B1']:,} | {counts['B2']:,} | {counts['C1']:,} | "
            f"{counts['unclassified']:,} | {values['minimum']}+ | "
            f"{values['policy_retained']:,} ({values['policy_retained_percent']}%) |"
        )
    lines.extend([
        "",
        "`Unclassified` includes genuine advanced vocabulary, proper/specialist terms, spelling",
        "mismatches, and noisy ECDICT records. It is retained for review and is never treated as invalid.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ecdict", type=Path, required=True)
    parser.add_argument("--efllex", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    args = parser.parse_args()

    candidates = load_candidates(args.ecdict)
    levels = load_levels(args.efllex)
    exams: dict[str, object] = {}
    for exam in EXAM_TAGS:
        pairs = {pair for pair, tags in candidates.items() if exam in tags}
        counts = Counter(levels.get(pair, "unclassified") for pair in pairs)
        normalized_counts = {level: counts[level] for level in (*LEVELS, "unclassified")}
        minimum = EXAM_MIN_LEVEL[exam]
        policy_retained = counts["unclassified"] + sum(
            counts[level] for level in LEVELS if LEVEL_RANK[level] >= LEVEL_RANK[minimum]
        )
        exams[exam] = {
            "candidate_pairs": len(pairs),
            "counts": normalized_counts,
            "minimum": minimum,
            "policy_retained": policy_retained,
            "policy_retained_percent": round(100 * policy_retained / len(pairs), 2) if pairs else 0,
            "unclassified_samples": [
                f"{word}/{part}" for word, part in sorted(pair for pair in pairs if pair not in levels)[:40]
            ],
        }
    report = {
        "method": "earliest_nonzero_efllex_attestation_by_exact_word_and_pos",
        "policy": {exam: f"{minimum}+ plus unclassified" for exam, minimum in EXAM_MIN_LEVEL.items()},
        "exams": exams,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.output_markdown.write_text(render_markdown(report), encoding="utf-8")
    print(render_markdown(report))


if __name__ == "__main__":
    main()
