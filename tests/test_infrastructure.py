from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import Flask

from typeng.lexicon_cache import export_cache, install_prebuilt_cache
from typeng.performance import register_request_timing
from typeng.preset_policy import apply_exam_policy
from typeng import paths


def _make_source_db(path: Path) -> None:
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO metadata VALUES ('wiktionary_lookup_signature', 'fixture-v1');
        CREATE TABLE ecdict_lookup (
            word_key TEXT PRIMARY KEY, word TEXT NOT NULL, translation TEXT,
            raw_pos TEXT, exchange TEXT, phonetic TEXT, definition TEXT,
            frequency INTEGER, source_tags TEXT
        );
        INSERT INTO ecdict_lookup VALUES
            ('abandon', 'abandon', 'v. 放弃', 'v', 'd:abandoned',
             'əˈbændən', 'leave behind', 100, 'cet4 toefl');
        CREATE TABLE wiktionary_examples (
            word_key TEXT, part_group TEXT, example_sentence TEXT,
            definition TEXT, example_type TEXT, sense_tags TEXT,
            sense_rank INTEGER, example_rank INTEGER
        );
        CREATE INDEX idx_wiktionary_examples_word_part
            ON wiktionary_examples(word_key, part_group, sense_rank, example_rank);
        INSERT INTO wiktionary_examples VALUES
            ('abandon', 'v', 'They had to abandon the plan.', 'leave behind',
             'example', NULL, 0, 0);
        CREATE TABLE wiktionary_definitions (
            word_key TEXT, part_group TEXT, definition TEXT,
            sense_tags TEXT, sense_rank INTEGER
        );
        INSERT INTO wiktionary_definitions VALUES
            ('abandon', 'v', 'leave behind', NULL, 0);
        CREATE TABLE wiktionary_indexed_words (word_key TEXT PRIMARY KEY);
        INSERT INTO wiktionary_indexed_words VALUES ('abandon');
        CREATE TABLE ecdict_preset_entries (
            word TEXT, part_of_speech TEXT, meaning TEXT, phonetic TEXT,
            definition TEXT, frequency INTEGER, source_tags TEXT
        );
        INSERT INTO ecdict_preset_entries VALUES
            ('abandon', 'v', '放弃', 'əˈbændən', 'leave behind', 100, 'cet4 toefl');
        """
    )
    db.commit()
    db.close()


def test_lexicon_cache_round_trip(tmp_path):
    source_path = tmp_path / "source.db"
    cache_path = tmp_path / "typeng-lexicon.sqlite3"
    _make_source_db(source_path)

    counts = export_cache(source_path, cache_path)
    assert counts["wiktionary_examples"] == 1
    assert counts["ecdict_preset_entries"] == 1
    assert "words" not in counts

    target = sqlite3.connect(tmp_path / "target.db")
    target.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    assert install_prebuilt_cache(target, cache_path)
    sentence = target.execute(
        "SELECT example_sentence FROM wiktionary_examples WHERE word_key = 'abandon'"
    ).fetchone()[0]
    assert sentence == "They had to abandon the plan."
    meaning = target.execute(
        "SELECT meaning FROM ecdict_preset_entries WHERE word = 'abandon'"
    ).fetchone()[0]
    assert meaning == "放弃"
    assert not install_prebuilt_cache(target, cache_path)
    target.close()


def test_request_timing_header_is_exposed():
    test_app = Flask(__name__)
    register_request_timing(test_app)

    @test_app.get("/")
    def index():
        return "ok"

    response = test_app.test_client().get("/")
    assert response.status_code == 200
    assert response.headers["Server-Timing"].startswith("app;dur=")


def test_exam_policy_validates_pos_and_only_removes_confirmed_basic_words(tmp_path):
    db = sqlite3.connect(tmp_path / "policy.db")
    db.executescript(
        """
        CREATE TABLE wiktionary_exam_parts (
            word_key TEXT, part_group TEXT,
            PRIMARY KEY(word_key, part_group)
        );
        INSERT INTO wiktionary_exam_parts VALUES ('can', 'v');
        INSERT INTO wiktionary_exam_parts VALUES ('recondite', 'adj');
        INSERT INTO wiktionary_exam_parts VALUES ('mismatch', 'adj');
        INSERT INTO wiktionary_exam_parts VALUES ('nodef', 'n');
        CREATE TABLE wiktionary_definitions (
            word_key TEXT, part_group TEXT, definition TEXT,
            sense_tags TEXT, sense_rank INTEGER
        );
        INSERT INTO wiktionary_definitions VALUES
            ('can', 'v', 'be able to', NULL, 0);
        INSERT INTO wiktionary_definitions VALUES
            ('recondite', 'adj', 'little known; abstruse', 'US,slang', 0);
        CREATE TABLE efllex_profiles (
            word_key TEXT, part_group TEXT, provisional_level TEXT
        );
        INSERT INTO efllex_profiles VALUES ('can', 'aux', 'A1');
        """
    )
    entries = [
        {"word": "can", "part_of_speech": "aux", "meaning": "能够"},
        {"word": "recondite", "part_of_speech": "adj", "meaning": "深奥的"},
        {"word": "mismatch", "part_of_speech": "adv", "meaning": "不匹配"},
        {"word": "nodef", "part_of_speech": "n", "meaning": "无释义"},
    ]
    kept, stats = apply_exam_policy(db, "cet4", entries)
    assert [(entry["word"], entry["part_of_speech"]) for entry in kept] == [
        ("recondite", "adj")
    ]
    assert stats["removed_basic"] == 1
    assert stats["removed_wiktionary_pos"] == 1
    assert stats["removed_missing_definition"] == 1
    assert stats["kept_unclassified"] == 1
    assert kept[0]["definition"] == "[US · slang] little known; abstruse"
    db.close()


def test_exam_policy_refuses_to_build_without_english_definitions(tmp_path):
    db = sqlite3.connect(tmp_path / "policy.db")
    kept, stats = apply_exam_policy(
        db, "gre", [{"word": "unverified", "part_of_speech": "n"}]
    )
    assert kept == []
    assert stats["wiktionary_definitions_unavailable"] == 1


def test_every_exam_preset_uses_the_same_definition_gate(tmp_path):
    db = sqlite3.connect(tmp_path / "all-policy.db")
    db.executescript(
        """
        CREATE TABLE wiktionary_definitions (
            word_key TEXT, part_group TEXT, definition TEXT,
            sense_tags TEXT, sense_rank INTEGER
        );
        INSERT INTO wiktionary_definitions VALUES
            ('recondite', 'adj', 'little known; abstruse', NULL, 0);
        """
    )
    for preset_key in ("zk", "gk", "cet4", "cet6", "kaoyan", "ielts", "toefl", "gre"):
        kept, _stats = apply_exam_policy(
            db,
            preset_key,
            [{"word": "recondite", "part_of_speech": "adj", "meaning": "深奥的"}],
        )
        assert kept[0]["definition"] == "little known; abstruse"
    db.close()


def test_lexicon_cache_upgrades_old_ecdict_without_replacing_other_tables(tmp_path):
    source_path = tmp_path / "source.db"
    cache_path = tmp_path / "cache.db"
    _make_source_db(source_path)
    export_cache(source_path, cache_path)

    target = sqlite3.connect(tmp_path / "old-target.db")
    target.executescript(
        """
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE ecdict_lookup (
            word_key TEXT PRIMARY KEY, word TEXT, phonetic TEXT,
            definition TEXT, frequency INTEGER, source_tags TEXT
        );
        INSERT INTO ecdict_lookup VALUES ('legacy', 'legacy', NULL, NULL, NULL, NULL);
        CREATE TABLE wiktionary_examples (marker TEXT);
        INSERT INTO wiktionary_examples VALUES ('keep-me');
        """
    )
    assert install_prebuilt_cache(target, cache_path)
    columns = {row[1] for row in target.execute("PRAGMA table_info(ecdict_lookup)")}
    assert {"translation", "raw_pos", "exchange"} <= columns
    assert target.execute("SELECT COUNT(*) FROM ecdict_preset_entries").fetchone()[0] == 1
    assert target.execute("SELECT marker FROM wiktionary_examples").fetchone()[0] == "keep-me"
    target.close()


def test_packaged_empty_external_resources_do_not_hide_bundled_cache(monkeypatch, tmp_path):
    executable_dir = tmp_path / "dist"
    app_home = tmp_path / "home"
    bundle_root = tmp_path / "bundle"
    (executable_dir / "resources").mkdir(parents=True)
    (app_home / "resources").mkdir(parents=True)
    bundled_lexicon = bundle_root / "resources" / "lexicon" / "typeng-lexicon.sqlite3"
    bundled_lexicon.parent.mkdir(parents=True)
    bundled_lexicon.touch()

    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "executable", str(executable_dir / "typeng"))
    assert paths.resolve_resource_dir(app_home, bundle_root) == bundle_root / "resources"

    external_ecdict = executable_dir / "resources" / "ecdict.csv"
    external_ecdict.touch()
    assert paths.resolve_resource_dir(app_home, bundle_root) == executable_dir / "resources"
