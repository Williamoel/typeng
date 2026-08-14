from __future__ import annotations

import sqlite3

import app
from typeng.repositories import units


def _unit_db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute(
        """
        CREATE TABLE words (
            id INTEGER PRIMARY KEY,
            library_id INTEGER NOT NULL,
            word TEXT NOT NULL,
            part_of_speech TEXT NOT NULL,
            meaning TEXT NOT NULL,
            frequency INTEGER,
            status TEXT NOT NULL
        )
        """
    )
    db.executemany(
        "INSERT INTO words VALUES (?, 1, ?, 'n', ?, ?, 'new')",
        [(number, f"word{number:03d}", f"释义{number}", number) for number in range(1, 206)],
    )
    return db


def test_units_are_100_words_and_compact_after_delete():
    db = _unit_db()
    assert [item["count"] for item in units.summaries(db, 1, "new")] == [100, 100, 5]
    assert [row["id"] for row in units.fetch(db, 1, 2, "new")][:2] == [101, 102]

    db.execute("DELETE FROM words WHERE id = 50")

    assert [item["count"] for item in units.summaries(db, 1, "new")] == [100, 100, 4]
    assert [row["id"] for row in units.fetch(db, 1, 2, "new")][:2] == [102, 103]
    db.close()


def test_cloze_always_prefers_a_user_example(monkeypatch):
    candidates = [
        {"sentence": "A dictionary sentence uses lucid.", "translation": None, "note": None, "source": "wiktionary", "is_user": False},
        {"sentence": "My lucid example is memorable.", "translation": "我的例句", "note": None, "source": "user", "is_user": True},
    ]
    monkeypatch.setattr(app, "example_candidates_for_word", lambda word: candidates)
    word = {"id": 7, "word": "lucid", "example_sentence": None}

    with app.app.test_request_context("/"):
        selected = app.practice_word_with_example(word)
        repeated = app.practice_word_with_example(word)

    assert selected["example_sentence"] == "My lucid example is memorable."
    assert selected["example_source"] == "user"
    assert repeated["example_sentence"] == selected["example_sentence"]


def test_main_workspace_is_chinese_and_split(monkeypatch):
    monkeypatch.setattr(app, "init_db", lambda: None)
    with app.app.test_client() as client:
        response = client.get("/")
    # The shared test database may have no words, but the main workspace must
    # still render the new structure and localized controls.
    assert response.status_code == 200
    assert b"split-workspace" in response.data
    assert "预览单词" in response.get_data(as_text=True)


def test_library_editing_stays_inside_workspace(monkeypatch, tmp_path):
    database_path = tmp_path / "workspace.db"
    monkeypatch.setattr(app, "DB_PATH", database_path)
    monkeypatch.setattr(app, "PREBUILT_LEXICON_PATH", tmp_path / "missing-cache.db")
    monkeypatch.setattr(app, "wiktionary_lookup_available", lambda: False)
    with app.app.app_context():
        app._schema.initialize(app.get_db(), app.PREBUILT_LEXICON_PATH, app.APP_SCHEMA_VERSION)
        library_id = int(app.get_db().execute("SELECT id FROM libraries ORDER BY id LIMIT 1").fetchone()[0])
        cursor = app.get_db().execute(
            "INSERT INTO words(library_id, word, part_of_speech, meaning, frequency) VALUES (?, ?, ?, ?, ?)",
            (library_id, "lucid", "adj", "清晰的", 1),
        )
        word_id = int(cursor.lastrowid)
        app.get_db().commit()
    monkeypatch.setattr(app, "DB_INITIALIZED", True)

    with app.app.test_client() as client:
        edit_page = client.get(f"/libraries?edit=1&unit=1&word={word_id}")
        add_page = client.get("/libraries?edit=1&unit=1&panel=add")
        delete_response = client.post(
            "/words/bulk-delete",
            data={"workspace": "1", "unit": "1", "word_ids": str(word_id)},
        )

    edit_html = edit_page.get_data(as_text=True)
    assert edit_page.status_code == 200
    assert "返回词表" in edit_html
    assert "保存修改" in edit_html
    assert "全选本单元" in edit_html
    assert "添加到词库" in add_page.get_data(as_text=True)
    assert delete_response.status_code == 302
    assert "/libraries?edit=1&unit=1" in delete_response.headers["Location"]


def _initialize_workspace_database(monkeypatch, tmp_path, filename="workspace-feature.db"):
    database_path = tmp_path / filename
    monkeypatch.setattr(app, "DB_PATH", database_path)
    monkeypatch.setattr(app, "PREBUILT_LEXICON_PATH", tmp_path / "missing-cache.db")
    with app.app.app_context():
        app._schema.initialize(app.get_db(), app.PREBUILT_LEXICON_PATH, app.APP_SCHEMA_VERSION)
        library_id = int(app.get_db().execute("SELECT id FROM libraries ORDER BY id LIMIT 1").fetchone()[0])
    monkeypatch.setattr(app, "DB_INITIALIZED", True)
    return database_path, library_id


def test_workspace_exposes_inline_format_dedupe_and_presets(monkeypatch, tmp_path):
    _database_path, _library_id = _initialize_workspace_database(monkeypatch, tmp_path)

    with app.app.test_client() as client:
        format_html = client.get("/libraries?edit=1&panel=format").get_data(as_text=True)
        dedupe_html = client.get("/libraries?edit=1&panel=dedupe").get_data(as_text=True)
        presets_html = client.get("/libraries?edit=1&panel=presets").get_data(as_text=True)
        home_html = client.get("/").get_data(as_text=True)

    assert "格式说明" in format_html
    assert "abandon,v,放弃" in format_html
    assert "排除重复词条" in dedupe_html
    assert "CET4" in presets_html and "CET6" in presets_html and "IELTS" in presets_html
    assert "待学" in home_html


def test_workspace_can_create_an_empty_library(monkeypatch, tmp_path):
    _database_path, _library_id = _initialize_workspace_database(monkeypatch, tmp_path, "new-library.db")

    with app.app.test_client() as client:
        panel_html = client.get("/libraries?edit=1&panel=new").get_data(as_text=True)
        response = client.post(
            "/libraries/add",
            data={"workspace": "1", "library_name": "本周生词"},
        )

    assert "新建词库" in panel_html
    assert response.status_code == 302
    assert "/libraries?edit=1" in response.headers["Location"]
    with app.app.app_context():
        row = app.get_db().execute(
            "SELECT id FROM libraries WHERE name = ?", ("本周生词",)
        ).fetchone()
    assert row is not None


def test_workspace_dedupe_only_removes_entries_from_active_library(monkeypatch, tmp_path):
    _database_path, target_library_id = _initialize_workspace_database(monkeypatch, tmp_path, "dedupe.db")
    with app.app.app_context():
        db = app.get_db()
        source_library_id = int(db.execute("INSERT INTO libraries(name) VALUES ('已学词库')").lastrowid)
        db.executemany(
            "INSERT INTO words(library_id, word, part_of_speech, meaning) VALUES (?, ?, ?, ?)",
            [
                (target_library_id, "lucid", "adj", "清晰的"),
                (target_library_id, "run", "n", "跑步"),
                (source_library_id, "LUCID", "adj", "清晰的"),
                (source_library_id, "run", "v", "跑"),
            ],
        )
        db.commit()

    with app.app.test_client() as client:
        with client.session_transaction() as session:
            session["active_library_id"] = target_library_id
        response = client.post(
            "/libraries/exclude",
            data={
                "workspace": "1",
                "source_library_id": str(source_library_id),
                "match_scope": "word_part",
            },
        )

    assert response.status_code == 302
    assert "panel=dedupe" in response.headers["Location"]
    with app.app.app_context():
        target_words = {
            row["word"] for row in app.get_db().execute(
                "SELECT word FROM words WHERE library_id = ?", (target_library_id,)
            )
        }
        source_words = {
            row["word"] for row in app.get_db().execute(
                "SELECT word FROM words WHERE library_id = ?", (source_library_id,)
            )
        }
    assert target_words == {"run"}
    assert source_words == {"LUCID", "run"}


def test_workspace_add_autofills_chinese_for_matching_word_and_pos(monkeypatch, tmp_path):
    _database_path, library_id = _initialize_workspace_database(monkeypatch, tmp_path, "autofill.db")
    monkeypatch.setattr(app, "wiktionary_part_lookup_available", lambda: True)
    monkeypatch.setattr(app, "wiktionary_part_exists", lambda word, part: (word, part) == ("lucid", "adj"))
    monkeypatch.setattr(
        app,
        "ecdict_entries_for_word",
        lambda word, part, meaning, raw=None: [
            {"word": word, "part_of_speech": part, "meaning": "清晰的；明晰的"}
        ],
    )
    monkeypatch.setattr(app, "enrich_entries_from_ecdict", lambda entries: 0)

    with app.app.test_client() as client:
        with client.session_transaction() as session:
            session["active_library_id"] = library_id
        response = client.post(
            "/words/add",
            data={
                "workspace": "1",
                "word[]": "lucid",
                "part_of_speech[]": "adj",
                "meaning[]": "",
                "example_sentence[]": "",
            },
        )

    assert response.status_code == 302
    with app.app.app_context():
        row = app.get_db().execute(
            "SELECT word, part_of_speech, meaning FROM words WHERE library_id = ?",
            (library_id,),
        ).fetchone()
    assert dict(row) == {"word": "lucid", "part_of_speech": "adj", "meaning": "清晰的；明晰的"}


def test_compact_wiktionary_pos_index_can_validate_without_example_tables(monkeypatch, tmp_path):
    _initialize_workspace_database(monkeypatch, tmp_path, "compact-pos.db")
    monkeypatch.setattr(app, "wiktionary_jsonl_path", lambda: None)

    with app.app.app_context():
        assert app.wiktionary_part_lookup_available()
        assert app.wiktionary_part_exists("lucid", "adj")
        assert not app.wiktionary_part_exists("lucid", "adv")


def test_word_detail_never_scans_raw_wiktionary_during_request(monkeypatch, tmp_path):
    _database_path, library_id = _initialize_workspace_database(monkeypatch, tmp_path, "request-lookup.db")
    with app.app.app_context():
        db = app.get_db()
        cursor = db.execute(
            "INSERT INTO words(library_id, word, part_of_speech, meaning) VALUES (?, 'lucid', 'adj', '清晰的')",
            (library_id,),
        )
        word_id = int(cursor.lastrowid)
        db.execute(
            "CREATE TABLE wiktionary_examples (word_key TEXT, part_group TEXT, example_sentence TEXT, definition TEXT, example_type TEXT, sense_tags TEXT, sense_rank INTEGER, example_rank INTEGER)"
        )
        db.execute(
            "CREATE TABLE wiktionary_definitions (word_key TEXT, part_group TEXT, definition TEXT, sense_tags TEXT, sense_rank INTEGER)"
        )
        db.execute("CREATE TABLE wiktionary_indexed_words (word_key TEXT PRIMARY KEY)")
        db.execute(
            "INSERT INTO wiktionary_definitions VALUES ('lucid', 'adj', 'expressed clearly and easy to understand', NULL, 0)"
        )
        db.commit()

    from typeng.dictionaries import wiktionary

    def fail_if_scanned(*_args, **_kwargs):
        raise AssertionError("raw Wiktionary must not be scanned by a detail request")

    monkeypatch.setattr(app, "wiktionary_lookup_available", lambda: True)
    monkeypatch.setattr(wiktionary, "ensure_wiktionary_lookup_index", fail_if_scanned)
    with app.app.test_client() as client:
        with client.session_transaction() as session:
            session["active_library_id"] = library_id
        response = client.get(f"/libraries?unit=1&word={word_id}")

    assert response.status_code == 200
    assert "expressed clearly" in response.get_data(as_text=True)


def test_review_and_wrong_lists_are_scoped_to_active_library(monkeypatch, tmp_path):
    _database_path, first_library_id = _initialize_workspace_database(monkeypatch, tmp_path, "library-scope.db")
    with app.app.app_context():
        db = app.get_db()
        second_library_id = int(db.execute("INSERT INTO libraries(name) VALUES ('第二词库')").lastrowid)
        db.executemany(
            "INSERT INTO words(library_id, word, part_of_speech, meaning, status) VALUES (?, ?, ?, ?, ?)",
            [
                (first_library_id, "alphaonly", "n", "甲", "learned"),
                (first_library_id, "wrongonly", "adj", "错误的", "wrong"),
                (second_library_id, "gammaonly", "n", "丙", "learned"),
            ],
        )
        db.commit()

    with app.app.test_client() as client:
        with client.session_transaction() as session:
            session["active_library_id"] = first_library_id
        learned_html = client.get("/learned").get_data(as_text=True)
        wrong_html = client.get("/wrong").get_data(as_text=True)
        with client.session_transaction() as session:
            session["active_library_id"] = second_library_id
        second_html = client.get("/learned").get_data(as_text=True)

    assert "alphaonly" in learned_html and "gammaonly" not in learned_html
    assert "wrongonly" in wrong_html
    assert "gammaonly" in second_html and "alphaonly" not in second_html
