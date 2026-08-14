"""Preprocess raw dictionaries into the compact cache used at runtime."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--build-home",
        type=Path,
        required=True,
        help="Temporary TypEng home containing resources/ecdict.csv",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--wiktionary-words",
        type=Path,
        help="Optional newline-delimited curated vocabulary to extract from Wiktionary JSONL",
    )
    args = parser.parse_args()

    build_home = args.build_home.resolve()
    build_home.mkdir(parents=True, exist_ok=True)
    os.environ["TYPENG_HOME"] = str(build_home)

    # Import only after TYPENG_HOME is fixed; app paths are resolved at import.
    import app
    from typeng.lexicon_cache import export_cache

    with app.app.app_context():
        app.init_db()
        app.ensure_ecdict_lookup_index()
        app.ensure_efllex_index(app.get_db(), app.EFLLEx_PATH)
        if args.wiktionary_words:
            target_words = {
                line.strip().lower()
                for line in args.wiktionary_words.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            }
            app.ensure_wiktionary_lookup_index(target_words)

    counts = export_cache(app.DB_PATH, args.output.resolve())
    print(f"Created {args.output.resolve()}")
    for table_name, count in sorted(counts.items()):
        print(f"  {table_name}: {count:,}")


if __name__ == "__main__":
    main()
