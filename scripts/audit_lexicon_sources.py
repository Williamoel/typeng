"""Audit normalized exam candidates against Wiktionary and historical WordNet.

The script distinguishes POS presence from usable-example presence and never
modifies the user's TypEng database.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from typeng.constants import ECDICT_PRESET_LIBRARIES
from typeng.parts import CANONICAL_PARTS
from typeng.domain import (
    extract_example_sentence,
    infer_ecdict_fallback_pos,
    normalize_part_group,
    normalize_wiktionary_pos,
    split_ecdict_tags,
    split_ecdict_translation,
    usable_wiktionary_example,
)

EXAM_TAGS = {
    preset: set(config["tags"])
    for preset, config in ECDICT_PRESET_LIBRARIES.items()
}
WIKTIONARY_PARTS = CANONICAL_PARTS - {"aux"}


def load_candidates(path: Path) -> dict[tuple[str, str], set[str]]:
    candidates: dict[tuple[str, str], set[str]] = defaultdict(set)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            normalized = {(key or "").strip().lower(): (value or "").strip() for key, value in row.items()}
            tags = split_ecdict_tags(normalized.get("tag", ""))
            exams = {exam for exam, source_tags in EXAM_TAGS.items() if tags & source_tags}
            word = normalized.get("word", "").casefold()
            translation = normalized.get("translation", "")
            if not word or not translation or not exams:
                continue
            fallback = infer_ecdict_fallback_pos(normalized)
            parts = {
                normalize_part_group(part)
                for part, _meaning in split_ecdict_translation(translation, fallback)
            }
            for part in parts or {normalize_part_group(fallback)}:
                candidates[(word, part)].update(exams)
    return dict(candidates)


def scan_wiktionary(
    path: Path,
    target_words: set[str],
) -> tuple[set[str], set[tuple[str, str]], set[tuple[str, str]]]:
    lexemes: set[str] = set()
    parts: set[tuple[str, str]] = set()
    examples: set[tuple[str, str]] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line_number % 1_000_000 == 0:
                print(f"  scanned {line_number:,} Wiktionary records", flush=True)
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("lang_code") != "en":
                continue
            word = str(entry.get("word") or "").strip().casefold()
            if word not in target_words:
                continue
            lexemes.add(word)
            part = normalize_wiktionary_pos(str(entry.get("pos") or ""))
            if part not in WIKTIONARY_PARTS:
                continue
            pair = (word, normalize_part_group(part))
            parts.add(pair)
            if pair in examples:
                continue
            for sense in entry.get("senses") or []:
                if not isinstance(sense, dict):
                    continue
                for example in sense.get("examples") or []:
                    if not isinstance(example, dict):
                        continue
                    sentence = extract_example_sentence(str(example.get("text") or ""), word)
                    if usable_wiktionary_example(sentence, word):
                        examples.add(pair)
                        break
                if pair in examples:
                    break
    return lexemes, parts, examples


def load_wordnet_pairs(path: Path) -> set[tuple[str, str]]:
    if not path.exists():
        return set()
    db = sqlite3.connect(path)
    table = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='wordnet_examples'"
    ).fetchone()
    if table is None:
        return set()
    return {
        (str(word).casefold(), normalize_part_group(str(part)))
        for word, part in db.execute("SELECT DISTINCT word_key, part_group FROM wordnet_examples")
    }


def ratio(count: int, total: int) -> float:
    return round(100.0 * count / total, 2) if total else 0.0


def build_metrics(
    candidates: dict[tuple[str, str], set[str]],
    wiki_lexemes: set[str],
    wiki_parts: set[tuple[str, str]],
    wiki_examples: set[tuple[str, str]],
    wordnet_examples: set[tuple[str, str]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for exam in EXAM_TAGS:
        pairs = {pair for pair, exams in candidates.items() if exam in exams}
        words = {word for word, _part in pairs}
        lexeme_matches = {word for word in words if word in wiki_lexemes}
        pos_matches = pairs & wiki_parts
        wiki_example_matches = pairs & wiki_examples
        wordnet_matches = pairs & wordnet_examples
        wordnet_only = wordnet_matches - wiki_example_matches
        result[exam] = {
            "candidate_words": len(words),
            "candidate_word_pos_pairs": len(pairs),
            "wiktionary_lexeme_matches": len(lexeme_matches),
            "wiktionary_lexeme_match_percent": ratio(len(lexeme_matches), len(words)),
            "wiktionary_pos_matches": len(pos_matches),
            "wiktionary_pos_match_percent": ratio(len(pos_matches), len(pairs)),
            "wiktionary_example_pairs": len(wiki_example_matches),
            "wordnet_example_pairs": len(wordnet_matches),
            "wordnet_only_example_pairs": len(wordnet_only),
            "wordnet_only_percent": ratio(len(wordnet_only), len(pairs)),
            "wordnet_only_samples": [f"{word}/{part}" for word, part in sorted(wordnet_only)[:25]],
            "wiktionary_unverified_lexeme_samples": sorted(words - lexeme_matches)[:25],
            "wiktionary_unverified_pos_samples": [
                f"{word}/{part}" for word, part in sorted(pairs - pos_matches)[:25]
            ],
            "wiktionary_no_usable_example_samples": [
                f"{word}/{part}" for word, part in sorted(pos_matches - wiki_example_matches)[:25]
            ],
        }
    return result


def render_markdown(metrics: dict[str, object]) -> str:
    lines = [
        "# Lexicon source audit",
        "",
        "POS presence is measured after canonical normalization. Preset generation removes a",
        "candidate when that normalized POS is absent from the complete snapshot index.",
        "Multiword phrases may match a compatible lexical POS rather than only `phrase`.",
        "Example absence is reported separately and never causes removal.",
        "",
        "| Exam | Words | Word+POS | Wiki lexeme | Wiki POS | Wiki example | WordNet example | WordNet-only |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for exam, values in metrics.items():
        row = values
        lines.append(
            f"| {exam.upper()} | {row['candidate_words']:,} | {row['candidate_word_pos_pairs']:,} | "
            f"{row['wiktionary_lexeme_matches']:,} ({row['wiktionary_lexeme_match_percent']}%) | "
            f"{row['wiktionary_pos_matches']:,} ({row['wiktionary_pos_match_percent']}%) | "
            f"{row['wiktionary_example_pairs']:,} | {row['wordnet_example_pairs']:,} | "
            f"{row['wordnet_only_example_pairs']:,} ({row['wordnet_only_percent']}%) |"
        )
    lines.extend([
        "",
        "`WordNet-only` means WordNet has an indexed example for that word+POS while Wiktionary",
        "has no example passing TypEng's current filters. It does not mean Wiktionary lacks the word.",
        "",
    ])
    for exam, values in metrics.items():
        lines.extend([
            f"## {exam.upper()} samples",
            "",
            f"- WordNet-only examples: {', '.join(values['wordnet_only_samples']) or 'none'}",
            f"- Lexemes absent from snapshot: {', '.join(values['wiktionary_unverified_lexeme_samples']) or 'none'}",
            f"- Normalized word+POS misses: {', '.join(values['wiktionary_unverified_pos_samples']) or 'none'}",
            f"- Wiktionary word+POS without a usable example: {', '.join(values['wiktionary_no_usable_example_samples']) or 'none'}",
            "",
        ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ecdict", type=Path, required=True)
    parser.add_argument("--wiktionary", type=Path, required=True)
    parser.add_argument(
        "--wordnet-db",
        type=Path,
        help="Optional historical WordNet database used only to quantify its former contribution.",
    )
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    args = parser.parse_args()

    print("Loading ECDICT exam candidates...", flush=True)
    candidates = load_candidates(args.ecdict)
    target_words = {word for word, _part in candidates}
    print(f"  {len(target_words):,} words / {len(candidates):,} word+POS pairs", flush=True)
    print("Streaming Wiktionary...", flush=True)
    wiki_lexemes, wiki_parts, wiki_examples = scan_wiktionary(args.wiktionary, target_words)
    wordnet_examples: set[tuple[str, str]] = set()
    if args.wordnet_db:
        print("Loading historical WordNet index...", flush=True)
        wordnet_examples = load_wordnet_pairs(args.wordnet_db)
    metrics = build_metrics(candidates, wiki_lexemes, wiki_parts, wiki_examples, wordnet_examples)
    payload = {
        "policy": "remove_normalized_pos_miss_but_keep_example_miss",
        "candidate_words": len(target_words),
        "candidate_word_pos_pairs": len(candidates),
        "wiktionary_snapshot": str(args.wiktionary),
        "metrics": metrics,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.output_markdown.write_text(render_markdown(metrics), encoding="utf-8")
    print(f"Wrote {args.output_json} and {args.output_markdown}", flush=True)


if __name__ == "__main__":
    main()
