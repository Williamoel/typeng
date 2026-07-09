"""Unit tests for typeng's pure logic helpers.

These cover the parsing, cloze-form, answer-matching, and review-scheduling
functions that carry the most behavioral risk during refactors. They avoid the
database and network so they run fast and offline:

    python -m pytest
"""

from __future__ import annotations

import os
import sys
import tempfile

# Keep app data (secret key, db) inside a throwaway folder during import so the
# test run never touches a real user's data/ directory.
os.environ.setdefault("TYPENG_HOME", tempfile.mkdtemp(prefix="typeng-test-"))

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app  # noqa: E402


# --- cloze_forms -----------------------------------------------------------

def test_cloze_forms_regular_verb():
    forms = app.cloze_forms("walk")
    assert {"walk", "walks", "walked", "walking"} <= forms


def test_cloze_forms_y_ending():
    forms = app.cloze_forms("carry")
    assert {"carry", "carries", "carried", "carrying"} <= forms


def test_cloze_forms_e_ending():
    forms = app.cloze_forms("make")
    assert "makes" in forms
    assert "making" in forms
    assert "maked" in forms  # naive form generation; matcher only needs a superset


def test_cloze_forms_doubling_consonant():
    forms = app.cloze_forms("stop")
    assert "stopped" in forms
    assert "stopping" in forms


def test_cloze_forms_non_alpha_returns_word_only():
    assert app.cloze_forms("New York") == {"new york"}
    assert app.cloze_forms("") == set()


def test_cloze_forms_irregular_lookup_used():
    # Whatever irregulars are configured must be included for their base word.
    for base, extra in app.CLOZE_IRREGULAR_FORMS.items():
        assert extra <= app.cloze_forms(base)
        break


# --- cloze_answer / cloze_prompt -------------------------------------------

def test_cloze_answer_matches_inflected_form():
    assert app.cloze_answer("She walked home slowly.", "walk") == "walked"


def test_cloze_answer_no_match_returns_empty():
    assert app.cloze_answer("Nothing relevant here.", "walk") == ""
    assert app.cloze_answer(None, "walk") == ""
    assert app.cloze_answer("", "walk") == ""


def test_cloze_prompt_blanks_target():
    prompt = app.cloze_prompt("She walked home.", "walk")
    assert "____" in prompt
    assert "walked" not in prompt


def test_cloze_prompt_no_match_returns_empty():
    assert app.cloze_prompt("Nothing here.", "walk") == ""


def test_cloze_prompt_only_replaces_first_occurrence():
    prompt = app.cloze_prompt("Walk and walk again.", "walk")
    assert prompt.count("____") == 1


# --- normalize_user_pos ----------------------------------------------------

def test_normalize_user_pos_collapses_verb_variants():
    assert app.normalize_user_pos("vt") == "v"
    assert app.normalize_user_pos("vi") == "v"
    assert app.normalize_user_pos("verb") == "v"


def test_normalize_user_pos_known_parts():
    assert app.normalize_user_pos("noun") == "n"
    assert app.normalize_user_pos("adjective") == "adj"
    assert app.normalize_user_pos("adverb") == "adv"


def test_normalize_user_pos_unknown_is_phrase():
    assert app.normalize_user_pos("gibberish") == "phrase"


# --- normalize_entry -------------------------------------------------------

def test_normalize_entry_basic():
    entry, error = app.normalize_entry(["abandon", "verb", "放弃"], 1)
    assert error is None
    assert entry == {"word": "abandon", "part_of_speech": "v", "meaning": "放弃"}


def test_normalize_entry_too_few_columns():
    entry, error = app.normalize_entry(["abandon", "verb"], 2)
    assert entry is None
    assert error is not None


def test_normalize_entry_missing_required_field():
    # Empty word is rejected. (An empty POS normalizes to "phrase", so the
    # word and meaning fields are the ones that can actually be missing.)
    entry, error = app.normalize_entry(["", "verb", "放弃"], 3)
    assert entry is None
    assert error is not None


def test_normalize_entry_example_kept_when_contains_word():
    entry, error = app.normalize_entry(
        ["abandon", "verb", "放弃", "They abandon the plan."], 4
    )
    assert entry is not None
    assert entry.get("example_sentence") == "They abandon the plan."
    assert error is None


def test_normalize_entry_example_dropped_when_missing_word():
    entry, error = app.normalize_entry(
        ["abandon", "verb", "放弃", "Totally unrelated sentence."], 5
    )
    assert entry is not None
    assert "example_sentence" not in entry
    assert error is not None  # user is told the example was ignored


# --- parse_csv -------------------------------------------------------------

def test_parse_csv_with_header():
    text = "word,part_of_speech,meaning\nabandon,verb,放弃\nability,noun,能力\n"
    entries, errors = app.parse_csv(text)
    assert errors == []
    assert len(entries) == 2
    assert entries[0]["word"] == "abandon"
    assert entries[0]["part_of_speech"] == "v"


def test_parse_csv_without_header():
    text = "abandon,verb,放弃\nability,noun,能力\n"
    entries, errors = app.parse_csv(text)
    assert len(entries) == 2


def test_parse_csv_empty():
    entries, errors = app.parse_csv("")
    assert entries == []
    assert errors


def test_parse_csv_skips_blank_rows():
    text = "abandon,verb,放弃\n\n,,\nability,noun,能力\n"
    entries, _ = app.parse_csv(text)
    assert len(entries) == 2


# --- parse_text_lines ------------------------------------------------------

def test_parse_text_lines_tab_separated():
    text = "abandon\tverb\t放弃\nability\tnoun\t能力\n"
    entries, errors = app.parse_text_lines(text)
    assert len(entries) == 2
    assert entries[0]["word"] == "abandon"


def test_parse_text_lines_pipe_separated():
    text = "abandon|verb|放弃\n"
    entries, _ = app.parse_text_lines(text)
    assert len(entries) == 1


def test_parse_text_lines_skips_comments_and_blanks():
    text = "# a comment\n\nabandon\tverb\t放弃\n"
    entries, _ = app.parse_text_lines(text)
    assert len(entries) == 1


# --- next_review_date ------------------------------------------------------

def test_next_review_date_clamps_stage():
    # Out-of-range stages must not raise; they clamp to the interval table.
    assert isinstance(app.next_review_date(-5), str)
    assert isinstance(app.next_review_date(9999), str)


def test_next_review_date_monotonic():
    dates = [app.next_review_date(stage) for stage in range(len(app.REVIEW_INTERVAL_DAYS))]
    assert dates == sorted(dates)


# --- parse_word_range (regression: integer overflow) -----------------------

def test_parse_word_range_clamps_giant_values(monkeypatch):
    class FakeForm:
        def __init__(self, data):
            self._data = data

        def get(self, key, default=None):
            return self._data.get(key, default)

    class FakeRequest:
        form = FakeForm({"x_start": "99999999999999999999", "x_end": "99999999999999999999"})

    monkeypatch.setattr(app, "request", FakeRequest())
    start, end = app.parse_word_range("x")
    # Must stay well within SQLite's 64-bit integer range.
    assert 1 <= start <= 100_000_000
    assert start <= end <= 100_000_000


# --- import without ECDICT (regression: missing ecdict_lookup table) --------

def test_import_without_ecdict_resource_does_not_crash(monkeypatch, tmp_path):
    """Released packages ship without ecdict.csv, so the ecdict_lookup table is
    never built. Importing a word list must still succeed instead of raising
    'no such table: ecdict_lookup' (which surfaced as a 500 on /import)."""
    # Point every ECDICT source at a nonexistent path so no index is built.
    missing = tmp_path / "nope.csv"
    monkeypatch.setattr(app, "BUNDLED_ECDICT_PATH", missing)
    monkeypatch.setattr(app, "ECDICT_CACHE_PATH", missing)
    # Block any network fallback so the test stays offline and deterministic.
    monkeypatch.setattr(
        app, "load_ecdict_data", lambda: (_ for _ in ()).throw(OSError("offline"))
    )

    # Route the app's per-request connection to a throwaway in-memory DB that
    # has libraries/words but deliberately NO ecdict_lookup table.
    monkeypatch.setattr(app, "DB_PATH", tmp_path / "typeng.db")

    with app.app.app_context():
        app.get_db().executescript(
            """
            CREATE TABLE IF NOT EXISTS libraries (id INTEGER PRIMARY KEY, name TEXT);
            INSERT INTO libraries (id, name) VALUES (1, 'Default Library');
            CREATE TABLE IF NOT EXISTS words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                library_id INTEGER NOT NULL DEFAULT 1,
                word TEXT, part_of_speech TEXT, meaning TEXT,
                example_sentence TEXT, example_translation TEXT,
                phonetic TEXT, definition TEXT, frequency INTEGER,
                source TEXT, source_tags TEXT,
                UNIQUE(library_id, word, part_of_speech)
            );
            """
        )
        # No ecdict_lookup table exists — this is exactly the packaged state.
        assert app.lookup_ecdict_word("abandon") is None  # must not raise
        entries = [{"word": "abandon", "part_of_speech": "v", "meaning": "放弃"}]
        # enrichment + insert should both survive the missing table
        app.enrich_entries_from_ecdict(entries)
        inserted, updated, _ = app.import_entries(entries, library_id=1)
        assert inserted == 1
