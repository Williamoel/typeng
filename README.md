<div align="center">

# TypEng

**Type the word. Learn it in context.**

A minimalist, open-source English vocabulary trainer built around keyboard recall,
part-of-speech-aligned definitions, and contextual cloze practice.

[中文说明](README.zh-CN.md) · [Latest release](https://github.com/PeiyanTang/typeng/releases/latest) · [Data sources](SOURCES.md)

![TypEng web workspace](docs/design/web-cloze-feedback-concept.png)

</div>

## What changed in v0.3

TypEng is now both a local desktop-style application and a deployable website.
The hosted mode is open to registration: each learner chooses a unique Chinese or
English username and a password of at least six characters. Libraries, units,
learning progress, review queues, wrong words, and cloze feedback are isolated by
account.

The interface has also been rebuilt around a black navigation rail and two quiet
white work surfaces. Library browsing, editing, preview, practice, review, and word
details stay in one consistent workspace.

## Core learning workflow

- Type answers instead of choosing from multiple-choice options.
- Learn each part of speech as an independent entry with aligned Chinese meanings,
  English definitions, phonetics, examples, and usage labels.
- Practise with normal spelling, cloze-only, or a spelling round followed by cloze.
- Prefer learner-written examples; otherwise rank the available Wiktionary examples.
- Rate cloze material as too hard, too easy, unsuitable, or incorrect.
- Review learned and wrong words independently for every library.
- Keep stable custom units while allowing a study batch to continue across unit
  boundaries.

## Libraries and data

TypEng supports:

- built-in exam-library generation for junior/senior high school, CET4, CET6,
  postgraduate entrance exams, IELTS, TOEFL, and GRE;
- CEFR-oriented basic-word filtering using EFLLex;
- POS validation, definitions, examples, labels, and usage patterns from Wiktionary;
- ECDICT Chinese meanings, phonetics, frequency, and exam tags;
- robust TXT/CSV import, lesson-based units, export, search, batch editing, and
  cross-library deduplication.

The large raw dictionaries are build-time inputs. Releases and web deployments use a
compact SQLite lexicon instead. See [SOURCES.md](SOURCES.md) for provenance and
licensing boundaries.

## Run locally

Python 3.12 is recommended.

```bash
git clone https://github.com/PeiyanTang/typeng.git
cd typeng
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`. Local mode has no account screen and accepts only
loopback traffic. Its data remains under the platform-specific TypEng data directory.

Prebuilt desktop packages for Windows, macOS, and Linux are attached to each
[GitHub release](https://github.com/PeiyanTang/typeng/releases/latest).

## Run the account-enabled web mode

```bash
pip install -r requirements-web.txt
export TYPENG_WEB_MODE=1
export TYPENG_SECRET_KEY='replace-with-a-long-random-secret'
export TYPENG_ALLOWED_HOSTS='127.0.0.1'
export TYPENG_COOKIE_SECURE=0
gunicorn --bind 127.0.0.1:8000 --workers 1 --threads 8 wsgi:app
```

Open `http://127.0.0.1:8000/register`. For a public HTTPS deployment, keep
`TYPENG_COOKIE_SECURE=1`.

### Account rules

- usernames contain 1–32 Chinese characters, English letters, digits, or underscores;
- usernames are unique after Unicode normalization and English case folding;
- passwords contain at least 6 and at most 256 characters and are stored only as
  Werkzeug password hashes;
- each browser device can submit at most 100 registration attempts per day, with
  source IP used as the fallback before a device cookie exists;
- there is currently no email verification or password recovery.

## Deploy to Render

The repository includes `render.yaml`, `Dockerfile`, and a production Gunicorn entry
point. The short path is:

1. Push the repository to GitHub.
2. In Render, create a **Blueprint** and connect this repository.
3. Keep the included paid web-service plan and 1 GB persistent disk.
4. Set `TYPENG_ALLOWED_HOSTS` to the assigned hostname, without `https://`.
5. Deploy, then open `/register` on the generated `onrender.com` URL.

The disk is mounted at `/var/lib/typeng`; never deploy the account-enabled site without
persistent storage. The container downloads the compact lexicon release asset on first
boot and stores the learning database on the same disk. Full instructions and backup
notes are in [docs/web-deployment.zh-CN.md](docs/web-deployment.zh-CN.md).

## Architecture

```text
Flask routes and sessions
        │
        ├── account authentication and device rate limiting
        ├── per-user library ownership
        ├── practice / review services
        └── repository layer
                │
                ├── writable SQLite learning database
                └── compact read-mostly lexicon cache
```

The hosted SQLite configuration intentionally runs one Gunicorn worker with multiple
threads. Moving to multiple application instances requires PostgreSQL or another shared
database.

## Testing

```bash
PYTHONPATH=. pytest -q
```

The suite covers import parsing, lexical cleanup, stable units, library isolation,
practice/review flows, account registration and login, per-user data boundaries,
registration throttling, and the compact lexicon pipeline.

## Project status

TypEng is a student-led portfolio and research-oriented project, not a commercial
language-learning service. The current priorities are data quality, explainable example
selection, learner feedback, and a maintainable web architecture.

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull
request.

## License

The application code is released under the [MIT License](LICENSE). Dictionary datasets
retain their own licenses; review [SOURCES.md](SOURCES.md) before redistributing a build.
