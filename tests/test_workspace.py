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
            example_sentence TEXT,
            frequency INTEGER,
            status TEXT NOT NULL,
            unit_number INTEGER,
            unit_position INTEGER
        )
        """
    )
    db.executemany(
        "INSERT INTO words VALUES (?, 1, ?, 'n', ?, NULL, ?, 'new', NULL, NULL)",
        [(number, f"word{number:03d}", f"释义{number}", number) for number in range(1, 206)],
    )
    units.assign_unassigned(db, 1)
    return db


def test_units_keep_boundaries_after_partial_delete():
    db = _unit_db()
    assert [item["count"] for item in units.summaries(db, 1, "new")] == [100, 100, 5]
    assert [row["id"] for row in units.fetch(db, 1, 2, "new")][:2] == [101, 102]

    db.execute("DELETE FROM words WHERE id = 50")

    assert [item["count"] for item in units.summaries(db, 1, "new")] == [99, 100, 5]
    assert [row["id"] for row in units.fetch(db, 1, 2, "new")][:2] == [101, 102]
    db.close()


def test_only_completely_empty_units_collapse():
    db = _unit_db()
    db.execute("DELETE FROM words WHERE id BETWEEN 1 AND 100")
    units.compact_empty_units(db, 1)

    assert [item["count"] for item in units.summaries(db, 1, "new")] == [100, 5]
    assert [row["id"] for row in units.fetch(db, 1, 1, "new")][:2] == [101, 102]
    db.close()


def test_learning_batch_crosses_stable_unit_boundaries():
    db = _unit_db()
    db.execute("DELETE FROM words WHERE id BETWEEN 6 AND 100")

    rows = units.fetch_batch(db, 1, "new", 10)

    assert [int(row["id"]) for row in rows] == [1, 2, 3, 4, 5, 101, 102, 103, 104, 105]
    assert [item["count"] for item in units.summaries(db, 1, "new")][:2] == [5, 100]
    db.close()


def test_units_remain_visible_when_their_words_change_status():
    db = _unit_db()
    db.execute("UPDATE words SET status = 'learned' WHERE id BETWEEN 1 AND 100")

    new_units = units.summaries(db, 1, "new")

    assert [item["number"] for item in new_units] == [1, 2, 3]
    assert [item["count"] for item in new_units] == [0, 100, 5]
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


def test_unit_strip_has_desktop_overflow_controls(monkeypatch):
    monkeypatch.setattr(app, "init_db", lambda: None)
    with app.app.test_client() as client:
        html = client.get("/libraries").get_data(as_text=True)

    assert 'data-unit-scroll="previous"' in html
    assert 'data-unit-scroll="next"' in html
    assert 'data-unit-strip tabindex="0"' in html


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
        export_html = client.get("/libraries?edit=1&unit=1&panel=export").get_data(as_text=True)
        home_html = client.get("/").get_data(as_text=True)

    assert "格式说明" in format_html
    assert "abandon,v,放弃" in format_html
    assert "排除重复词条" in dedupe_html
    assert "CET4" in presets_html and "CET6" in presets_html and "IELTS" in presets_html
    assert "整个词库" in export_html and "当前单元 · 1" in export_html
    assert "待学" in home_html


def test_library_export_supports_csv_and_single_unit_txt(monkeypatch, tmp_path):
    _database_path, library_id = _initialize_workspace_database(
        monkeypatch, tmp_path, "export-library.db"
    )
    with app.app.app_context():
        db = app.get_db()
        db.execute(
            """INSERT INTO words(
                library_id, word, part_of_speech, meaning, phonetic, definition,
                status, unit_number, unit_position
            ) VALUES (?, 'lucid', 'adj', '清晰的', '/luːsɪd/', 'Clear.', 'new', 1, 1)""",
            (library_id,),
        )
        db.execute(
            """INSERT INTO words(
                library_id, word, part_of_speech, meaning, status,
                unit_number, unit_position
            ) VALUES (?, 'recondite', 'adj', '深奥的', 'learned', 2, 1)""",
            (library_id,),
        )
        db.commit()

    with app.app.test_client() as client:
        with client.session_transaction() as session:
            session["active_library_id"] = library_id
        csv_response = client.get(
            "/libraries/export?scope=library&format=csv&unit=1"
        )
        txt_response = client.get(
            "/libraries/export?scope=unit&format=txt&unit=2"
        )

    csv_text = csv_response.data.decode("utf-8-sig")
    txt_text = txt_response.data.decode("utf-8-sig")
    assert csv_response.status_code == 200
    assert "filename=Default-Library-all.csv" in csv_response.headers["Content-Disposition"]
    assert "unit,word,part_of_speech,meaning" in csv_text
    assert "lucid" in csv_text and "recondite" in csv_text
    assert txt_response.status_code == 200
    assert "# Unit 2" in txt_text and "recondite\tadj\t深奥的" in txt_text
    assert "lucid" not in txt_text


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


def test_workspace_can_create_an_empty_unit(monkeypatch, tmp_path):
    _database_path, library_id = _initialize_workspace_database(
        monkeypatch, tmp_path, "new-unit.db"
    )

    with app.app.test_client() as client:
        with client.session_transaction() as session:
            session["active_library_id"] = library_id
        response = client.post("/libraries/units/add")
        page = client.get("/libraries?edit=1&unit=1")

    assert response.status_code == 302
    assert "unit=1" in response.headers["Location"] and "panel=add" in response.headers["Location"]
    assert 'title="0 个词"' in page.get_data(as_text=True)


def test_workspace_can_rename_and_delete_a_library(monkeypatch, tmp_path):
    _database_path, first_id = _initialize_workspace_database(
        monkeypatch, tmp_path, "manage-library.db"
    )
    with app.app.app_context():
        db = app.get_db()
        second_id = int(db.execute("INSERT INTO libraries(name) VALUES ('Second')").lastrowid)
        db.execute(
            "INSERT INTO words(library_id, word, part_of_speech, meaning) VALUES (?, 'private', 'adj', '私有的')",
            (first_id,),
        )
        db.commit()

    with app.app.test_client() as client:
        with client.session_transaction() as session:
            session["active_library_id"] = first_id
        renamed = client.post("/libraries/rename", data={"library_name": "Renamed"})
        deleted = client.post("/libraries/delete")
        with client.session_transaction() as session:
            active_after_delete = session["active_library_id"]

    assert renamed.status_code == 302 and deleted.status_code == 302
    assert active_after_delete == second_id
    with app.app.app_context():
        db = app.get_db()
        assert db.execute("SELECT 1 FROM libraries WHERE id = ?", (first_id,)).fetchone() is None
        assert db.execute("SELECT 1 FROM words WHERE word = 'private'").fetchone() is None


def test_user_pattern_can_be_added_linked_and_used_for_cloze(monkeypatch, tmp_path):
    _database_path, library_id = _initialize_workspace_database(
        monkeypatch, tmp_path, "word-pattern.db"
    )
    with app.app.app_context():
        db = app.get_db()
        word_id = int(db.execute(
            "INSERT INTO words(library_id, word, part_of_speech, meaning) VALUES (?, 'ken', 'n', '认知范围')",
            (library_id,),
        ).lastrowid)
        db.execute(
            "CREATE TABLE wiktionary_definitions (word_key TEXT, part_group TEXT, definition TEXT, sense_tags TEXT, sense_rank INTEGER)"
        )
        db.execute(
            "INSERT INTO wiktionary_definitions VALUES ('ken', 'n', 'Range of perception.', NULL, 3)"
        )
        db.commit()

    monkeypatch.setattr(app, "wiktionary_lookup_available", lambda: True)
    monkeypatch.setattr(app, "ranked_wiktionary_example_candidates", lambda *args, **kwargs: [])
    with app.app.test_client() as client:
        with client.session_transaction() as session:
            session["active_library_id"] = library_id
        response = client.post(
            f"/words/{word_id}/patterns/add",
            data={
                "expression": "beyond one’s ken",
                "definition_number": "1",
                "usage_label": "fossil word",
                "enabled_for_cloze": "on",
            },
            headers={"Referer": f"http://localhost/libraries?edit=1&word={word_id}"},
        )
        detail = client.get(f"/libraries?word={word_id}").get_data(as_text=True)
        edit = client.get(f"/libraries?edit=1&word={word_id}").get_data(as_text=True)

    assert response.status_code == 302
    assert "beyond one’s ken" in detail and "搭配与用法" in detail
    assert "对应英文释义 1" in detail
    assert "beyond one’s ken" in edit and "Cloze" in edit
    with app.app.app_context():
        word = app.get_db().execute("SELECT * FROM words WHERE id = ?", (word_id,)).fetchone()
        candidates = app.cloze_material_candidates(word)
    assert candidates[0]["sentence"] == "beyond one’s ken"
    assert candidates[0]["material_type"] == "pattern"


def test_invalid_user_pattern_without_target_word_is_rejected(monkeypatch, tmp_path):
    _database_path, library_id = _initialize_workspace_database(
        monkeypatch, tmp_path, "invalid-pattern.db"
    )
    with app.app.app_context():
        db = app.get_db()
        word_id = int(db.execute(
            "INSERT INTO words(library_id, word, part_of_speech, meaning) VALUES (?, 'ken', 'n', '认知范围')",
            (library_id,),
        ).lastrowid)
        db.commit()

    with app.app.test_client() as client:
        with client.session_transaction() as session:
            session["active_library_id"] = library_id
        client.post(
            f"/words/{word_id}/patterns/add",
            data={"expression": "outside human knowledge", "enabled_for_cloze": "on"},
        )

    with app.app.app_context():
        count = app.get_db().execute(
            "SELECT COUNT(*) FROM word_patterns WHERE word_id = ?", (word_id,)
        ).fetchone()[0]
    assert count == 0


def test_cloze_result_accepts_optional_material_feedback(monkeypatch, tmp_path):
    _database_path, library_id = _initialize_workspace_database(
        monkeypatch, tmp_path, "cloze-feedback.db"
    )
    with app.app.app_context():
        db = app.get_db()
        word_id = int(db.execute(
            "INSERT INTO words(library_id, word, part_of_speech, meaning) VALUES (?, 'lucid', 'adj', '清晰的')",
            (library_id,),
        ).lastrowid)
        db.execute(
            "INSERT INTO word_examples(word_id, sentence, source) VALUES (?, ?, 'user')",
            (word_id, "Her lucid explanation helped everyone."),
        )
        db.commit()

    monkeypatch.setattr(app, "wiktionary_lookup_available", lambda: False)
    with app.app.test_client() as client:
        with client.session_transaction() as session:
            session.update({
                "active_library_id": library_id,
                "practice_ids": [word_id],
                "practice_index": 0,
                "practice_mode": "normal",
                "prompt_mode": "cloze",
                "fallback_prompt_mode": "chinese",
                "practice_round": 1,
                "awaiting_next": False,
            })
        answered = client.post("/practice/submit", data={"answer": "lucid"})
        result_page = client.get("/practice").get_data(as_text=True)
        with client.session_transaction() as session:
            feedback_token = session["cloze_feedback_context"]["token"]
            assert session["awaiting_next"] is True
        saved = client.post(
            "/practice/feedback",
            data={"feedback_token": feedback_token, "rating": "too_hard"},
            headers={"X-Requested-With": "fetch"},
        )

    assert answered.status_code == 302
    assert "这个例句怎么样？" in result_page
    assert "太难" in result_page and "例句有误" in result_page
    assert saved.status_code == 200 and saved.get_json()["saved"] is True
    with app.app.app_context():
        row = app.get_db().execute(
            "SELECT word, sentence, rating, answer_correct FROM cloze_feedback"
        ).fetchone()
    assert tuple(row) == (
        "lucid", "Her lucid explanation helped everyone.", "too_hard", 1
    )


def test_web_mode_supports_registration_login_and_user_isolation(monkeypatch, tmp_path):
    _initialize_workspace_database(monkeypatch, tmp_path, "web-accounts.db")
    monkeypatch.setattr(app, "WEB_MODE", True)
    monkeypatch.setattr(app, "WEB_ALLOWED_HOSTS", {"localhost"})
    monkeypatch.setitem(app.app.config, "SESSION_COOKIE_SECURE", False)

    with app.app.test_client() as client:
        blocked = client.get("/")
        health = client.get("/health")
        short_password = client.post(
            "/register", data={"username": "学习者", "password": "12345"}
        )
        registered = client.post(
            "/register", data={"username": "学习者", "password": "123456"}
        )
        home = client.get("/")
        client.post("/libraries/add", data={"library_name": "我的词库"})
        logged_out = client.post("/logout")
        wrong_password = client.post(
            "/login", data={"username": "学习者", "password": "bad-password"}
        )
        logged_in = client.post(
            "/login", data={"username": "学习者", "password": "123456"}
        )

    assert blocked.status_code == 302 and "/login" in blocked.headers["Location"]
    assert health.status_code == 200 and health.get_json()["status"] == "ok"
    assert "密码至少需要 6 位" in short_password.get_data(as_text=True)
    assert registered.status_code == 302
    assert home.status_code == 200 and "TypEng" in home.get_data(as_text=True)
    assert logged_out.status_code == 302 and logged_out.headers["Location"].endswith("/login")
    assert "用户名或密码不正确" in wrong_password.get_data(as_text=True)
    assert logged_in.status_code == 302

    with app.app.app_context():
        db = app.get_db()
        user = db.execute("SELECT id, username_key FROM users WHERE username = '学习者'").fetchone()
        libraries = db.execute(
            "SELECT name FROM libraries WHERE user_id = ? ORDER BY id", (user["id"],)
        ).fetchall()
    assert user["username_key"] == "学习者"
    assert [row["name"] for row in libraries] == ["Default Library", "我的词库"]


def test_web_user_cannot_select_another_users_library(monkeypatch, tmp_path):
    _initialize_workspace_database(monkeypatch, tmp_path, "web-isolation.db")
    monkeypatch.setattr(app, "WEB_MODE", True)
    monkeypatch.setattr(app, "WEB_ALLOWED_HOSTS", {"localhost"})
    monkeypatch.setitem(app.app.config, "SESSION_COOKIE_SECURE", False)

    with app.app.test_client() as first:
        first.post("/register", data={"username": "Alice", "password": "123456"})
        first_library = first.get("/")
        assert first_library.status_code == 200
        with first.session_transaction() as state:
            first_library_id = state["active_library_id"]

    with app.app.test_client() as second:
        second.post("/register", data={"username": "第二位", "password": "123456"})
        response = second.post("/libraries/select", data={"library_id": first_library_id})
        html = second.get("/").get_data(as_text=True)

    assert response.status_code == 302
    assert "该词库不存在" in html


def test_web_registration_limits_each_device_to_100_attempts_per_day(monkeypatch, tmp_path):
    _initialize_workspace_database(monkeypatch, tmp_path, "web-rate-limit.db")
    monkeypatch.setattr(app, "WEB_MODE", True)
    monkeypatch.setattr(app, "WEB_ALLOWED_HOSTS", {"localhost"})
    monkeypatch.setitem(app.app.config, "SESSION_COOKIE_SECURE", False)

    with app.app.test_client() as client:
        client.get("/register")  # establishes the persistent device cookie
        for _ in range(100):
            response = client.post(
                "/register", data={"username": "bad name", "password": "123456"}
            )
            assert response.status_code == 200
        limited = client.post(
            "/register", data={"username": "validname", "password": "123456"}
        )

    assert limited.status_code == 429
    assert "今天的注册尝试次数已达到上限" in limited.get_data(as_text=True)


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
        db.execute(
            "INSERT INTO wiktionary_definitions VALUES ('lucid', 'adj', 'bright or luminous', NULL, 1)"
        )
        for rank in range(2, 6):
            db.execute(
                "INSERT INTO wiktionary_definitions VALUES ('lucid', 'adj', ?, NULL, ?)",
                (f"additional modern meaning {rank + 1}", rank),
            )
        db.executemany(
            "INSERT INTO wiktionary_examples VALUES ('lucid', 'adj', ?, ?, 'example', NULL, ?, 0)",
            [
                (
                    "Her lucid explanation made the difficult idea easy to understand.",
                    "expressed clearly and easy to understand",
                    0,
                ),
                (
                    "A lucid glow filled the quiet room at night.",
                    "bright or luminous",
                    1,
                ),
                (
                    "This lucid example belongs to the fifth listed meaning.",
                    "additional modern meaning 5",
                    4,
                ),
                (
                    "This lucid example belongs to the sixth listed meaning.",
                    "additional modern meaning 6",
                    5,
                ),
            ],
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
    html = response.get_data(as_text=True)
    assert "expressed clearly" in html
    assert "对应英文释义 1" in html
    assert "对应英文释义 2" in html
    assert "对应英文释义 5" in html
    assert "对应英文释义 6" in html


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


def test_library_search_matches_only_english_headwords_and_shows_units(monkeypatch, tmp_path):
    _database_path, library_id = _initialize_workspace_database(
        monkeypatch, tmp_path, "library-search.db"
    )
    with app.app.app_context():
        db = app.get_db()
        db.executemany(
            """
            INSERT INTO words(
                library_id, word, part_of_speech, meaning,
                unit_number, unit_position
            ) VALUES (?, ?, 'n', ?, ?, 1)
            """,
            [
                (library_id, "alpha", "阿尔法", 1),
                (library_id, "alphabet", "字母表", 2),
            ],
        )
        db.commit()

    with app.app.test_client() as client:
        with client.session_transaction() as session:
            session["active_library_id"] = library_id
        english = client.get("/libraries?search=1&q=alpha").get_data(as_text=True)
        chinese = client.get("/libraries?search=1&q=字母表").get_data(as_text=True)

    assert "alpha" in english and "alphabet" in english
    assert "单元 1" in english and "单元 2" in english
    assert "alpha" not in chinese and "alphabet" not in chinese
