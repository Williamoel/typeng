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
