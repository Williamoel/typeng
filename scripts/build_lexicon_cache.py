"""Build the compact lexicon shipped to users or deployed to the web server.

Example:
    .venv/bin/python scripts/build_lexicon_cache.py \
        --source-db data/typeng.db \
        --output resources/lexicon/typeng-lexicon.sqlite3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from typeng.lexicon_cache import export_cache


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    counts = export_cache(args.source_db.resolve(), args.output.resolve())
    print(f"Created {args.output.resolve()}")
    for table_name, count in sorted(counts.items()):
        print(f"  {table_name}: {count:,}")


if __name__ == "__main__":
    main()
