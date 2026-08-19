"""Integration tests for the Wiktionary example engine.

These tests create a tiny JSONL fragment with known examples, build the
lookup index in a temporary database, and verify that common words whose
examples were previously missed by filtering bugs now return results.

Run with:
    python -m pytest tests/test_example_engine.py -v
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

# Use a throwaway data directory so the test never touches real user data.
os.environ["TYPENG_HOME"] = tempfile.mkdtemp(prefix="typeng-test-engine-")

import app  # noqa: E402


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _minimal_entry(word: str, pos: str, examples: list[str]) -> dict:
    """Build a minimal Wiktionary-style JSONL entry."""
    return {
        "word": word,
        "lang_code": "en",
        "pos": pos,
        "senses": [
            {
                "glosses": ["test sense"],
                "tags": [],
                "examples": [{"text": ex, "type": "example"} for ex in examples],
            }
        ],
    }


def test_wiktionary_index_builds_and_lookups_work(monkeypatch, tmp_path):
    """Build an index from a known fragment and verify lookups return data."""
    jsonl_path = tmp_path / "test.jsonl"
    _write_jsonl(
        jsonl_path,
        [
            _minimal_entry("net", "noun", [
                "Our net income was fourteen dollars.",
                "The net on that container was only fourteen tons.",
            ]),
            _minimal_entry("ritual", "noun", [
                "The priests carried out the religious ritual carefully.",
            ]),
            _minimal_entry("bacteria", "noun", [
                "Anaerobic bacteria function in the absence of oxygen. Both these bacterias are capable of breaking down organic matter [...]",
            ]),
            _minimal_entry("conservation", "noun", [
                'My father had ideas about conservation long before the United States took it up.[…]You preserve water in times of flood.',
            ]),
            _minimal_entry("rectangle", "noun", [
                "For why should you praise the integrity of a Square who faithfully defends the rectangle.",
            ]),
            _minimal_entry("hallway", "noun", []),  # no examples
        ],
    )

    # Point the Wiktionary path lookup at our test fragment
    monkeypatch.setattr(app, "WIKTIONARY_JSONL_CANDIDATES", [jsonl_path])

    with app.app.app_context():
        app.init_db()
        db = app.get_db()

        # Force fresh index
        db.execute("DROP TABLE IF EXISTS wiktionary_examples")
        db.execute("DROP TABLE IF EXISTS wiktionary_definitions")
        db.execute("DROP TABLE IF EXISTS wiktionary_indexed_words")
        db.execute("DELETE FROM metadata WHERE key = 'wiktionary_lookup_signature'")
        db.commit()

        # Build index for all our test words
        app.ensure_wiktionary_lookup_index({"net", "ritual", "bacteria", "conservation", "rectangle", "hallway"})

        # Verify: words with examples should return candidates
        for word, pos, expect in [
            ("net", "n", True),
            ("ritual", "n", True),
            ("bacteria", "n", True),
            ("conservation", "n", True),
            ("rectangle", "n", True),
            ("hallway", "n", False),  # no examples in source
        ]:
            result = app.lookup_wiktionary_example(word, pos)
            if expect:
                assert result is not None, f"{word}({pos}) should have an example but got None"
                assert result["example_sentence"].strip(), f"{word}({pos}) example is empty"
            else:
                # hallway genuinely has no Wiktionary examples
                assert result is None, f"{word}({pos}) should have NO example but got one"


def test_bracket_stripping_allows_bracketed_examples():
    """Regression: [...] and [...] in example text must not block usability."""
    assert app.usable_wiktionary_example(
        "My father had ideas about conservation long before the United States took it up.",
        "conservation",
    )
    assert app.usable_wiktionary_example(
        "Both these bacterias are capable of breaking down organic matter.",
        "bacteria",
    )


def test_long_example_not_blocked_by_length():
    """Regression: examples between 241–500 chars must be accepted."""
    # A 330-char sentence like basement should be usable
    long_sentence = (
        "Turning back, then, toward the basement staircase, she began to grope "
        + "her way through blinding darkness, but had taken only a few uncertain "
        + "steps when, hearing the footsteps below, she stopped and reached "
        + "toward the wall. That is quite a long sentence indeed for a test."
    )[:330]
    assert 240 < len(long_sentence) <= 500
    assert app.usable_wiktionary_example(long_sentence, "basement")


def test_example_splitter_preserves_personal_name_initials():
    quotation = (
        'It should be noted that there is now no intelligentsia that is not in some sense "Left". '
        'Perhaps the last right-wing intellectual was T. E. Lawrence. '
        'Since about 1930 everyone describable as an intellectual has lived in discontent.'
    )

    selected = app.extract_example_sentence(
        quotation, "intellectual", [[117, 129]]
    )

    assert selected == "… Perhaps the last right-wing intellectual was T. E. Lawrence. …"


def test_cloze_truncation_leaves_marker_centered():
    """Truncation must keep the ____ marker visible and not lose it."""
    long_prompt = "The " + "very " * 50 + "quick brown ____ fox " + "jumps " * 30 + "over the lazy dog."
    result = app.truncate_cloze_prompt(long_prompt, max_chars=200)
    assert "____" in result
    assert len(result) <= 220  # allow small overshoot from word-boundary rounding
    # The marker position should be roughly in the middle third
    pos = result.index("____")
    ratio = pos / len(result)
    assert 0.15 < ratio < 0.85, f"marker at {pos}/{len(result)} = {ratio:.2f}, expected 0.15–0.85"


def test_spelling_variant_lookup_finds_examples(monkeypatch, tmp_path):
    """British spelling 'judgement' must find examples under 'judgment'."""
    jsonl_path = tmp_path / "test2.jsonl"
    _write_jsonl(jsonl_path, [
        _minimal_entry("judgment", "noun", [
            "a politician without judgment",
        ]),
    ])
    monkeypatch.setattr(app, "WIKTIONARY_JSONL_CANDIDATES", [jsonl_path])

    with app.app.app_context():
        app.init_db()
        db = app.get_db()
        db.execute("DROP TABLE IF EXISTS wiktionary_examples")
        db.execute("DROP TABLE IF EXISTS wiktionary_definitions")
        db.execute("DROP TABLE IF EXISTS wiktionary_indexed_words")
        db.execute("DELETE FROM metadata WHERE key = 'wiktionary_lookup_signature'")
        db.commit()

        app.ensure_wiktionary_lookup_index({"judgment"})
        result = app.lookup_wiktionary_example("judgement", "n")
        assert result is not None, "judgement should find example via judgment variant"
        assert "judgment" in result["example_sentence"]


def test_wiktionary_definition_is_scoped_to_requested_pos(monkeypatch, tmp_path):
    jsonl_path = tmp_path / "way.jsonl"
    noun = _minimal_entry("way", "noun", ["This is the safest way home."])
    noun["senses"][0]["glosses"] = ["a route or path"]
    adverb = _minimal_entry("way", "adv", ["The station is way over there."])
    adverb["senses"][0]["glosses"] = ["at a great distance"]
    _write_jsonl(jsonl_path, [noun, adverb])
    monkeypatch.setattr(app, "WIKTIONARY_JSONL_CANDIDATES", [jsonl_path])

    with app.app.app_context():
        app.init_db()
        db = app.get_db()
        db.execute("DROP TABLE IF EXISTS wiktionary_examples")
        db.execute("DROP TABLE IF EXISTS wiktionary_definitions")
        db.execute("DROP TABLE IF EXISTS wiktionary_indexed_words")
        db.execute("DELETE FROM metadata WHERE key = 'wiktionary_lookup_signature'")
        db.commit()
        app.ensure_wiktionary_lookup_index({"way"})

        definition = app.lookup_wiktionary_definition("way", "adv")
        assert definition == "at a great distance"
        assert "route" not in definition


def test_wiktionary_omits_pronunciation_spelling_senses(monkeypatch, tmp_path):
    jsonl_path = tmp_path / "air.jsonl"
    lexical = _minimal_entry("air", "verb", ["We aired the room before lunch."])
    lexical["senses"][0]["glosses"] = ["To expose something to the air."]
    spelling = _minimal_entry("air", "verb", ["Where air you going?"])
    spelling["senses"][0]["glosses"] = ["Pronunciation spelling of are."]
    spelling["senses"][0]["tags"] = ["alt-of", "pronunciation-spelling"]
    _write_jsonl(jsonl_path, [lexical, spelling])
    monkeypatch.setattr(app, "WIKTIONARY_JSONL_CANDIDATES", [jsonl_path])

    with app.app.app_context():
        app.init_db()
        db = app.get_db()
        db.execute("DROP TABLE IF EXISTS wiktionary_examples")
        db.execute("DROP TABLE IF EXISTS wiktionary_definitions")
        db.execute("DROP TABLE IF EXISTS wiktionary_indexed_words")
        db.execute("DELETE FROM metadata WHERE key = 'wiktionary_lookup_signature'")
        db.commit()
        app.ensure_wiktionary_lookup_index({"air"})

        definitions = app.lookup_wiktionary_definition_records("air", "v", limit=None)
        examples = app.ranked_wiktionary_example_candidates("air", "v", limit=None)

    assert [item["raw_definition"] for item in definitions] == [
        "To expose something to the air."
    ]
    assert [row["example_sentence"] for row in examples] == [
        "We aired the room before lunch."
    ]


def test_wiktionary_uses_leaf_gloss_and_prefers_complete_example(monkeypatch, tmp_path):
    jsonl_path = tmp_path / "account.jsonl"
    entry = _minimal_entry("account", "verb", [])
    entry["senses"] = [
        {
            "glosses": ["To provide explanation.", "To give a satisfactory reason for; to explain."],
            "tags": ["intransitive"],
            "examples": [
                {"text": "Idleness accounts for poverty.", "type": "example"},
                {
                    "text": "Earlier discussion. " + "context " * 35 + "This may account for the result. " + "later " * 35,
                    "type": "quotation",
                },
            ],
        }
    ]
    _write_jsonl(jsonl_path, [entry])
    monkeypatch.setattr(app, "WIKTIONARY_JSONL_CANDIDATES", [jsonl_path])

    with app.app.app_context():
        app.init_db()
        db = app.get_db()
        db.execute("DROP TABLE IF EXISTS wiktionary_examples")
        db.execute("DROP TABLE IF EXISTS wiktionary_definitions")
        db.execute("DROP TABLE IF EXISTS wiktionary_indexed_words")
        db.execute("DELETE FROM metadata WHERE key = 'wiktionary_lookup_signature'")
        db.commit()
        app.ensure_wiktionary_lookup_index({"account"})

        definitions = app.lookup_wiktionary_definition_records("account", "v", limit=None)
        examples = app.ranked_wiktionary_example_candidates("account", "v", limit=None)

    assert [item["raw_definition"] for item in definitions] == [
        "To give a satisfactory reason for; to explain."
    ]
    assert [row["example_sentence"] for row in examples] == [
        "Idleness accounts for poverty."
    ]


def test_wiktionary_recovers_usage_labels_from_raw_gloss(monkeypatch, tmp_path):
    jsonl_path = tmp_path / "jury.jsonl"
    entry = _minimal_entry("jury", "adj", ["They raised a jury mast after the storm."])
    entry["senses"][0]["glosses"] = [
        "For temporary use; applied to a temporary contrivance."
    ]
    entry["senses"][0]["tags"] = ["not-comparable"]
    entry["senses"][0]["raw_glosses"] = [
        "(nautical, in compounds) For temporary use; applied to a temporary contrivance."
    ]
    _write_jsonl(jsonl_path, [entry])
    monkeypatch.setattr(app, "WIKTIONARY_JSONL_CANDIDATES", [jsonl_path])

    with app.app.app_context():
        app.init_db()
        db = app.get_db()
        db.execute("DROP TABLE IF EXISTS wiktionary_examples")
        db.execute("DROP TABLE IF EXISTS wiktionary_definitions")
        db.execute("DROP TABLE IF EXISTS wiktionary_indexed_words")
        db.execute("DELETE FROM metadata WHERE key = 'wiktionary_lookup_signature'")
        db.commit()
        app.ensure_wiktionary_lookup_index({"jury"})
        definitions = app.lookup_wiktionary_definition_records("jury", "adj")

    assert definitions[0]["definition"].startswith("[in compounds · nautical]")


def test_fossil_word_short_examples_become_fixed_patterns(monkeypatch, tmp_path):
    jsonl_path = tmp_path / "fossil.jsonl"
    entry = _minimal_entry(
        "come", "verb",
        ["come true", "come clean", "This complete sentence should not become a pattern."],
    )
    entry["senses"][0]["raw_glosses"] = [
        "(copulative, fossil word) To become, often in set phrases."
    ]
    entry["senses"][0]["tags"] = ["copulative"]
    _write_jsonl(jsonl_path, [entry])
    monkeypatch.setattr(app, "WIKTIONARY_JSONL_CANDIDATES", [jsonl_path])
    monkeypatch.setattr(app, "WIKTIONARY_USAGE_PATTERNS_PATH", tmp_path / "missing.tsv")

    with app.app.app_context():
        app.init_db()
        db = app.get_db()
        for table in (
            "wiktionary_examples", "wiktionary_definitions",
            "wiktionary_indexed_words", "wiktionary_headwords", "wiktionary_patterns",
        ):
            db.execute(f"DROP TABLE IF EXISTS {table}")
        db.execute("DELETE FROM metadata WHERE key = 'wiktionary_lookup_signature'")
        db.commit()
        app.ensure_wiktionary_lookup_index({"come"})
        patterns = app.lookup_wiktionary_patterns("come", "v")

    assert [item["expression"] for item in patterns] == ["come true", "come clean"]
    assert all(item["usage_label"] == "fossil word" for item in patterns)


def test_rare_definition_and_its_example_are_filtered_together(monkeypatch, tmp_path):
    jsonl_path = tmp_path / "passage.jsonl"
    entry = _minimal_entry("passage", "verb", ["They passaged to America in 1902."])
    entry["senses"][0]["glosses"] = ["To make a passage, especially by sea; to cross."]
    entry["senses"][0]["tags"] = ["rare"]
    _write_jsonl(jsonl_path, [entry])
    monkeypatch.setattr(app, "WIKTIONARY_JSONL_CANDIDATES", [jsonl_path])

    with app.app.app_context():
        app.init_db()
        db = app.get_db()
        db.execute("DROP TABLE IF EXISTS wiktionary_examples")
        db.execute("DROP TABLE IF EXISTS wiktionary_definitions")
        db.execute("DROP TABLE IF EXISTS wiktionary_indexed_words")
        db.execute("DROP TABLE IF EXISTS wiktionary_headwords")
        db.execute("DELETE FROM metadata WHERE key = 'wiktionary_lookup_signature'")
        db.commit()
        app.ensure_wiktionary_lookup_index({"passage"})

        assert app.lookup_wiktionary_definition_records("passage", "v") == []
        assert app.ranked_wiktionary_example_candidates("passage", "v") == []
