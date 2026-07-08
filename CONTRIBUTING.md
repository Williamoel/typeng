# Contributing to typeng

Thanks for considering a contribution. typeng is still a student-scale local app, so small, focused pull requests are easiest to review.

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

For the desktop-style launcher:

```bash
python run_typeng.py
```

## Before Opening a Pull Request

- Keep changes focused on one feature or bug.
- Do not commit local app data from `data/`.
- Do not commit large dictionary resources such as `ecdict.csv`, Wiktionary JSONL, or WordNet zip files.
- Run at least:

```bash
python -m py_compile app.py run_typeng.py
python -m pytest
```

`pytest` is only needed for running the test suite:

```bash
pip install pytest
```

If your change affects practice flow, review scheduling, import behavior, or example matching, please describe how you tested it manually.

## Data Sources

typeng can use third-party dictionary resources. Those resources keep their own licenses; see [SOURCES.md](SOURCES.md) and [resources/README.md](resources/README.md).
