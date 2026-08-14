# TypEng performance baseline

Performance work must be measured on the same data path users exercise. This
document records the first baseline and the budgets that future changes should
preserve.

## 2026-08-13 baseline

Test data:

- 3.15 GB Kaikki English Wiktionary JSONL
- 770,611 normalized ECDICT lookup rows
- 15,280 EFLLex lexical profiles
- 9,392 words in the development library

Observed on the development machine:

| Scenario | Before | After |
| --- | ---: | ---: |
| Cold lookup for an unindexed Wiktionary target | 20.29 s | built before deployment |
| Fresh install from a prebuilt lookup cache | n/a | 2.3 s, once |
| Warm startup plus dictionary lookup | n/a | 0.11 s |
| Python test suite | 0.22 s | 0.19 s |

The cache now also includes the Chinese translations and tags needed to create
exam presets and EFLLex difficulty profiles, replacing runtime resource parsing.
The exact size changes with source versions.

## Runtime budgets

- Warm application startup: under 500 ms on a typical laptop.
- Ordinary HTML/API request p95: under 200 ms for a 10,000-entry library.
- Answer submission p95: under 100 ms excluding page rendering/network time.
- Recorded pronunciation start: 550 ms before browser-voice fallback.
- No raw CSV, TSV, or JSONL parsing inside an ordinary user request
  in release and hosted builds.

Every response includes a `Server-Timing: app;dur=...` header. Requests over
500 ms are logged by `typeng.performance`, making regressions visible without
requiring a hosted metrics service for local development.

## Building the runtime lexicon

Place maintainer-only inputs under a temporary build home:

```text
build-home/
  resources/
    ecdict.csv
    efllex/EFLLex.tsv
    wiktionary/exam-pos-index.tsv
    wiktionary/kaikki.org-dictionary-English.jsonl  # optional
```

Then run:

```bash
.venv/bin/python scripts/prepare_lexicon_cache.py \
  --build-home /tmp/typeng-lexicon-build \
  --output resources/lexicon/typeng-lexicon.sqlite3
```

Wiktionary extraction is deliberately limited to a curated word list:

```bash
.venv/bin/python scripts/prepare_lexicon_cache.py \
  --build-home /tmp/typeng-lexicon-build \
  --wiktionary-words data/curated-vocabulary.txt \
  --output resources/lexicon/typeng-lexicon.sqlite3
```

Raw Wiktionary JSONL is never scanned from a web request. In a development
checkout, index every word already present in the local database in one batch:

```bash
.venv/bin/python scripts/index_current_vocabulary.py
```

Word-detail requests only query the resulting SQLite indexes. New words that
have not been batch-indexed may temporarily have no English definition or
example; clicking them remains fast.

Release CI performs the ECDICT and EFLLex build and imports the compact exam
POS-presence index before PyInstaller runs. Raw
maintainer inputs are not placed in the release bundle.
