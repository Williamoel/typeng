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
    assert app.normalize_user_pos("aux") == "v"


def test_normalize_user_pos_known_parts():
    assert app.normalize_user_pos("noun") == "n"
    assert app.normalize_user_pos("adjective") == "adj"
    assert app.normalize_user_pos("adverb") == "adv"


def test_normalize_user_pos_unknown_is_phrase():
    assert app.normalize_user_pos("gibberish") == "phrase"


def test_cross_dictionary_pos_normalization():
    assert app.normalize_part_group("auxiliary") == "v"
    assert app.normalize_wiktionary_pos("proper noun") == "n"
    assert app.normalize_wiktionary_pos("article") == "det"
    assert app.normalize_wiktionary_pos("initialism") == "abbr"
    assert app.wiktionary_lookup_groups("phrase", "account for") == [
        "adj", "adv", "conj", "interj", "n", "phrase", "prep", "v"
    ]


def test_definition_items_keep_only_the_requested_part_of_speech():
    value = "n. a route or path\nadv. at a great distance\nadv. by far"
    assert app.definition_items(value, "adv") == ["at a great distance", "by far"]
    assert app.definition_items(value, "n") == ["a route or path"]
    assert app.definition_items(value, "v") == []


def test_unlabeled_wiktionary_definitions_are_kept():
    assert app.definition_items("at a great distance\nby a large amount", "adv") == [
        "at a great distance", "by a large amount"
    ]


def test_wiktionary_usage_labels_are_concise_and_deduplicated():
    assert app.wiktionary_usage_label("US,slang") == "US · slang"
    assert app.wiktionary_usage_label("British,colloquial,informal") == "british · colloquial · informal"
    assert app.wiktionary_usage_label("nautical,in-compounds") == "nautical · in compounds"
    assert app.wiktionary_usage_label("often,often-with-down,with-down") == "often with down"
    assert app.wiktionary_usage_label("proscribed,sometimes,sometimes-proscribed") == "sometimes proscribed"


def test_wiktionary_math_definition_is_readable_plain_text():
    raw = "Given an n×n matrix a_ij,, the sum over all permutations π, of ∏ᵢ₌₁ⁿa_iπ(i)."
    assert app.wiktionary_definition_display(raw) == (
        "Given an n × n matrix A = (a(i, j)), the sum over all permutations π "
        "of the product from i = 1 to n of a(i, π(i))."
    )


def test_ecdict_translation_does_not_attach_inflection_notes_to_adjectives():
    shot = "a. 杂色的, 交织着的, 破旧的\nshoot的过去式和过去分词"
    beat = "a. 疲乏的, 颓废的\nbeat的过去式\n[计] 拍; 节拍"
    assert app.split_ecdict_translation(shot, "adj") == [
        ("adj", "杂色的, 交织着的, 破旧的")
    ]
    assert app.split_ecdict_translation(beat, "adj") == [
        ("adj", "疲乏的, 颓废的")
    ]


def test_ecdict_preset_merges_transitive_and_intransitive_meanings(monkeypatch):
    raw = (
        "word,phonetic,definition,translation,pos,collins,oxford,tag,bnc,frq,exchange,detail,audio\n"
        "obtain,əb'tein,v. come into possession of,\"vt. 获得, 达到\\nvi. 流行, 得到公认\",v,3,1,cet6,793,1595,,,\n"
        "shock,ʃɒk,a. unexpected,\"a. 蓬乱浓密的\",adj,4,1,cet6,100,200,,,\n"
    ).encode()
    monkeypatch.setattr(app, "load_ecdict_data", lambda: raw)
    monkeypatch.setattr(app, "ecdict_source_signature", lambda: "test-ecdict-v1")

    with app.app.app_context():
        app.init_db()
        db = app.get_db()
        db.execute("DROP TABLE IF EXISTS ecdict_lookup")
        db.execute("DROP TABLE IF EXISTS ecdict_preset_entries")
        db.execute("DELETE FROM metadata WHERE key = 'ecdict_lookup_signature'")
        db.commit()
        app.ensure_ecdict_lookup_index()
        rows = db.execute(
            "SELECT word, part_of_speech, meaning FROM ecdict_preset_entries "
            "WHERE word IN ('obtain', 'shock') ORDER BY word"
        ).fetchall()

    assert [dict(row) for row in rows] == [
        {
            "word": "obtain",
            "part_of_speech": "v",
            "meaning": "获得, 达到；流行, 得到公认",
        },
        {
            "word": "shock",
            "part_of_speech": "adj",
            "meaning": "令人震惊的, 突如其来的",
        },
    ]


def test_editor_parts_are_concise_wiktionary_groups():
    values = dict(app.PART_OF_SPEECH_OPTIONS)
    assert "aux" not in values
    assert values["v"] == "v."
    assert values["adv"] == "adv."
    assert values["det"] == "det."


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


def test_parse_text_lines_dictionary_block_splits_multiple_parts_of_speech():
    text = "accessory\n\tn. 同谋，帮凶 adj. 附属的\n"
    entries, errors = app.parse_text_lines(text)
    assert errors == []
    assert entries == [
        {"word": "accessory", "part_of_speech": "n", "meaning": "同谋，帮凶"},
        {"word": "accessory", "part_of_speech": "adj", "meaning": "附属的"},
    ]


def test_parse_text_lines_dictionary_block_accepts_one_sense_per_line():
    text = "account for\n  v. 解释；占据\n  phrase. 是……的原因\n"
    entries, errors = app.parse_text_lines(text)
    assert errors == []
    assert [(entry["part_of_speech"], entry["meaning"]) for entry in entries] == [
        ("v", "解释；占据"),
        ("phrase", "是……的原因"),
    ]


def test_parse_text_lines_accepts_two_column_dictionary_export():
    text = "accessory\tn. 同谋，帮凶 adj. 附属的\n"
    entries, errors = app.parse_text_lines(text)
    assert len(entries) == 2
    assert errors == []


def test_parse_text_lines_accepts_inline_dictionary_entry():
    entries, errors = app.parse_text_lines("accessory n. 同谋，帮凶 adj. 附属的")
    assert len(entries) == 2
    assert errors == []


def test_parse_text_lines_reports_orphan_headword_and_orphan_sense():
    entries, errors = app.parse_text_lines("orphan\nabandon|v|放弃\nn. 孤儿\n")
    assert entries == [{"word": "abandon", "part_of_speech": "v", "meaning": "放弃"}]
    assert any("orphan" in error for error in errors)
    assert any("缺少对应的英文单词" in error for error in errors)


def test_parse_text_lines_merges_repeated_parts_in_one_dictionary_block():
    text = "set\n n. 一套；一组\n n. 集合\n v. 放置\n"
    entries, errors = app.parse_text_lines(text)
    assert errors == []
    assert entries == [
        {"word": "set", "part_of_speech": "n", "meaning": "一套；一组；集合"},
        {"word": "set", "part_of_speech": "v", "meaning": "放置"},
    ]


def test_parse_text_lines_can_mix_legacy_rows_and_dictionary_blocks():
    text = "abandon|v|放弃\naccessory\n n. 同谋 adj. 附属的\nability,n,能力\n"
    entries, errors = app.parse_text_lines(text)
    assert errors == []
    assert len(entries) == 4


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


def test_data_migrations_run_once_per_schema_version(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "DB_PATH", tmp_path / "versioned.db")
    monkeypatch.setattr(app, "PREBUILT_LEXICON_PATH", tmp_path / "missing-cache.db")
    calls = {name: 0 for name in (
        "clear_invalid_example_sentences",
        "simplify_existing_example_translations",
        "merge_verb_part_duplicates",
        "migrate_plural_phrase_entries",
        "migrate_inferred_phrase_entries",
    )}

    for name in calls:
        def record(_db, migration_name=name):
            calls[migration_name] += 1
        # Migration implementations now belong to the schema module; app keeps
        # aliases only for backwards compatibility.
        monkeypatch.setattr(app._schema, name, record)

    with app.app.app_context():
        app.init_db()
        app.init_db()
        version = app.get_db().execute(
            "SELECT value FROM metadata WHERE key = 'app_schema_version'"
        ).fetchone()["value"]

    assert version == str(app.APP_SCHEMA_VERSION)
    assert set(calls.values()) == {1}


# --- extract_example_sentence (regression: common words with only long quotes) ---

def test_extract_pulls_sentence_with_target_from_long_quote():
    # A multi-sentence quotation where only one sentence uses the word.
    text = ("The admirable smoothness reflected great credit on the crew. "
            "Fuel was held back so as to create shortages and dissatisfaction.")
    out = app.extract_example_sentence(text, "shortage")
    assert "shortage" in out.lower()
    assert out.count(".") <= 1  # a single sentence, not the whole passage


def test_extract_returns_single_sentence_unchanged():
    text = "She walked home slowly."
    assert app.extract_example_sentence(text, "walk") == text


def test_extract_prefers_shortest_matching_sentence():
    text = ("Reliability matters. Punctuality and reliability remain the bedrock "
            "of a successful national railway network over many decades.")
    out = app.extract_example_sentence(text, "reliability")
    assert out == "Reliability matters. …"


def test_extract_empty_text():
    assert app.extract_example_sentence("", "walk") == ""


def test_extract_uses_wiktionary_highlight_instead_of_bare_headword():
    text = (
        "When I was young and full of grace, I sprited a rattlesnake. "
        "When I was young, a fever fell my spirit; I will not tell. "
        "You're on your honor not to tell."
    )
    start = text.index("sprited")
    extracted = app.extract_example_sentence(
        text, "spirit", [[start, start + len("sprited")]]
    )

    assert extracted == "When I was young and full of grace, I sprited a rattlesnake. …"
    assert not app.usable_wiktionary_example(extracted, "spirit")


def test_extract_does_not_split_common_title_abbreviation():
    text = (
        "God does not appear, but the Devil (Ms. Pinal) emphatically does, "
        "and finally succeeds in spiriting Simon off to Manhattan."
    )
    start = text.index("spiriting")

    extracted = app.extract_example_sentence(
        text, "spirit", [[start, start + len("spiriting")]]
    )

    assert extracted.startswith("God does not appear")
    assert "Ms. Pinal" in extracted


def test_long_excerpt_is_centered_and_marks_both_omissions():
    text = "Opening context " + "before " * 35 + "spiriting Simon off " + "after " * 35
    start = text.index("spiriting")

    extracted = app.extract_example_sentence(
        text, "spirit", [[start, start + len("spiriting")]]
    )

    assert extracted.startswith("… ")
    assert extracted.endswith(" …")
    assert "spiriting" in extracted
    assert len(extracted) <= 225


def test_long_single_sentence_common_word_is_usable():
    # ~220 chars, single sentence, common verb — must pass the 240 cap.
    text = ("In polling by the research center that year, fully half the "
            "respondents thought the two parties would cooperate more in the "
            "coming year, versus those who thought otherwise entirely today.")
    extracted = app.extract_example_sentence(text, "cooperate")
    assert app.usable_wiktionary_example(extracted, "cooperate")


def test_stylized_and_historical_spellings_are_not_learner_examples():
    assert not app.usable_wiktionary_example(
        "And maaaaaaaybe Superman would be a good hang.", "hang"
    )
    assert not app.usable_wiktionary_example(
        "All day to mount the trench, to ſtorm the breach.", "storm"
    )
    assert not app.usable_wiktionary_example(
        "If he don’t get outta my hood, I’m gonna cap his ass.", "cap"
    )


# --- spelling_variants (regression: British/American spelling) -------------

def test_spelling_variants_bidirectional():
    assert app.spelling_variants("judgement") == {"judgement", "judgment"}
    assert app.spelling_variants("judgment") == {"judgement", "judgment"}
    assert app.spelling_variants("colour") == {"colour", "color"}
    assert app.spelling_variants("color") == {"colour", "color"}


def test_spelling_variants_common_rules():
    assert "organize" in app.spelling_variants("organise")
    assert "centre" in app.spelling_variants("center")
    assert "defense" in app.spelling_variants("defence")
    assert "analyze" in app.spelling_variants("analyse")
    assert "catalog" in app.spelling_variants("catalogue")


def test_spelling_variants_no_false_positive():
    # A word with no variant rule applies returns just itself.
    assert app.spelling_variants("apple") == {"apple"}


def test_cloze_accepts_both_spellings():
    # Both spellings (and their inflections) must be matchable for cloze.
    forms = app.cloze_forms("judgement")
    assert "judgement" in forms and "judgment" in forms
    forms2 = app.cloze_forms("colour")
    assert "colour" in forms2 and "color" in forms2
    # inflections still generated on top of variants
    assert "colours" in forms2 or "colors" in forms2


# --- learner-safe archaic filtering ----------------------------------------

def test_ranked_candidates_rejects_archaic_even_when_it_is_the_only_option(monkeypatch):
    """No example is preferable to unsuitable historical English."""
    import sqlite3 as _sqlite

    # Two rows, both archaic — the pre-fix code filtered these out entirely.
    archaic_rows = [
        {"example_sentence": "For why should you praise the integrity of a Square who defends the rectangle.",
         "definition": "a quadrilateral", "example_type": "quotation",
         "sense_tags": "archaic", "part_group": "n"},
    ]

    class FakeConn:
        def execute(self, *a, **k):
            class R:
                def fetchall(self_inner):
                    return [_FakeRow(r) for r in archaic_rows]
            return R()

    class _FakeRow:
        def __init__(self, d): self._d = d
        def __getitem__(self, k): return self._d[k]

    monkeypatch.setattr(app, "get_db", lambda: FakeConn())
    monkeypatch.setattr(app, "wiktionary_jsonl_path", lambda: "dummy")
    monkeypatch.setattr(app, "ensure_wiktionary_lookup_index", lambda *a, **k: None)

    out = app.ranked_wiktionary_example_candidates("rectangle", "noun")
    assert out == []


def test_wiktionary_example_filter_catches_untagged_archaic_quotation():
    sentence = "A man that flattereth his neighbor spreadeth a net for his feet."
    assert app.contains_archaic_english(sentence)
    assert not app.usable_wiktionary_example(sentence, "net")
    assert app.usable_wiktionary_example("She brushed her teeth before bed.", "teeth")
    assert app.usable_wiktionary_example("The twentieth chapter explains the result.", "twentieth")


# --- example_note_from_tags (regression: archaic example warning) ----------

def test_example_note_from_tags_flags_archaic():
    assert app.example_note_from_tags("archaic") == "archaic"
    assert app.example_note_from_tags("obsolete,rare") is not None
    assert "obsolete" in app.example_note_from_tags("obsolete")


def test_example_note_from_tags_ignores_ordinary():
    assert app.example_note_from_tags(None) is None
    assert app.example_note_from_tags("") is None
    assert app.example_note_from_tags("transitive,informal") == "informal"


# --- truncate_cloze_prompt -------------------------------------------------

def test_truncate_cloze_prompt_short_sentence_unchanged():
    short = "The quick brown fox ____ over the lazy dog."
    assert app.truncate_cloze_prompt(short) == short


def test_truncate_cloze_prompt_long_truncated_around_marker():
    long_prompt = "x " * 120 + "____" + " y" * 120
    result = app.truncate_cloze_prompt(long_prompt, max_chars=240)
    assert "____" in result
    assert len(result) <= 250  # allow slight overshoot from word-boundary
    assert result.startswith("…")
    assert result.endswith("…")


def test_truncate_cloze_prompt_no_marker_truncates_tail():
    long_no_marker = "abcdefghij " * 30
    result = app.truncate_cloze_prompt(long_no_marker, max_chars=50)
    assert len(result) <= 53
    assert "…" in result


def test_truncate_cloze_prompt_empty():
    assert app.truncate_cloze_prompt("") == ""
