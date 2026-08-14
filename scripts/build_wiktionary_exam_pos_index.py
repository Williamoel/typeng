"""Build a compact POS-presence index for ECDICT exam candidates."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audit_lexicon_sources import load_candidates
from typeng.domain import normalize_wiktionary_pos
from typeng.parts import lexical_part


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ecdict", type=Path, required=True)
    parser.add_argument("--wiktionary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    targets = {word for word, _part in load_candidates(args.ecdict)}
    found: dict[str, set[str]] = defaultdict(set)
    with args.wiktionary.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line_number % 1_000_000 == 0:
                print(f"scanned {line_number:,} Wiktionary records", flush=True)
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("lang_code") != "en":
                continue
            word = str(entry.get("word") or "").strip().casefold()
            if word not in targets:
                continue
            part = lexical_part(
                normalize_wiktionary_pos(str(entry.get("pos") or "")), unknown=""
            )
            if part:
                found[word].add(part)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(("word", "parts"))
        for word in sorted(targets):
            writer.writerow((word, "|".join(sorted(found.get(word, set())))))
    print(f"wrote {len(targets):,} candidates; {len(found):,} found lexemes to {args.output}")


if __name__ == "__main__":
    main()
