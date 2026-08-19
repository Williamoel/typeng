from __future__ import annotations

import csv
import hashlib
import io
import os
import random
import re
import secrets
import sqlite3
import sys
import threading
from datetime import datetime, timedelta, timezone
from math import ceil
from pathlib import Path

from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, send_file, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

from typeng.constants import (
    BLOCKED_EXAMPLE_WORDS,
    CLOZE_IRREGULAR_FORMS,
    CLOZE_SCOPES,
    CLOZE_SCOPE_ONLY,
    CLOZE_SCOPE_WITH,
    DEFAULT_REVIEW_TARGET_COUNT,
    DEFAULT_WRONG_REVIEW_TARGET_COUNT,
    ECDICT_DEFINITION_POS_RE,
    ECDICT_DEFINITION_SPLIT_RE,
    ECDICT_POS_PREFIX_RE,
    ECDICT_PRESET_LIBRARIES,
    LIBRARY_PAGE_SIZE,
    LIBRARY_SORT_MODES,
    MAX_REVIEW_TARGET_COUNT,
    MAX_WRONG_REVIEW_TARGET_COUNT,
    MIN_REVIEW_TARGET_COUNT,
    MIN_WRONG_REVIEW_TARGET_COUNT,
    PART_OF_SPEECH_OPTIONS,
    PROMPT_AUDIO,
    PROMPT_CHINESE,
    PROMPT_CLOZE,
    PROMPT_MIXED,
    PROMPT_MODES,
    REVIEW_INTERVAL_DAYS,
    SORT_ALPHA,
    SORT_FREQUENCY,
    STATUS_LEARNED,
    STATUS_NEW,
    STATUS_WRONG,
)
from typeng.domain import *  # compatibility exports while routes are split incrementally
from typeng.dictionaries import wiktionary as _wiktionary
from typeng.dictionaries import ecdict as _ecdict
from typeng.db import connect as connect_db
from typeng.cefr import ensure_efllex_index
from typeng.preset_policy import apply_exam_policy, ensure_wiktionary_exam_pos_index
from typeng.lexicon_cache import lookup_available
from typeng.paths import resolve_app_home, resolve_bundle_dir, resolve_resource_dir
from typeng.performance import register_request_timing
from typeng.security import host_name, is_local_host, is_local_origin, is_same_origin, load_or_create_secret, normalize_username
from typeng import schema as _schema
from typeng.repositories import libraries as library_repository
from typeng.repositories import examples as example_repository
from typeng.repositories import feedback as feedback_repository
from typeng.repositories import patterns as pattern_repository
from typeng.repositories import lexicon as lexicon_repository
from typeng.repositories import units as unit_repository
from typeng.repositories import words as word_repository
from typeng.repositories import users as user_repository
from typeng.services import review as review_service

SOURCE_ROOT = Path(__file__).resolve().parent
APP_ROOT = resolve_bundle_dir(SOURCE_ROOT)
APP_HOME = resolve_app_home(SOURCE_ROOT)
BASE_DIR = APP_ROOT
DATA_DIR = APP_HOME / "data"
RESOURCE_DIR = resolve_resource_dir(APP_HOME, APP_ROOT)
DB_PATH = DATA_DIR / "typeng.db"
BUNDLED_ECDICT_PATH = RESOURCE_DIR / "ecdict.csv"
ECDICT_CACHE_PATH = DATA_DIR / "ecdict.csv"
ECDICT_SOURCE_URL = "https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv"
ECDICT_LOOKUP_SCHEMA_VERSION = 6
EFLLEx_PATH = RESOURCE_DIR / "efllex" / "EFLLex.tsv"
WIKTIONARY_EXAM_POS_PATH = RESOURCE_DIR / "wiktionary" / "exam-pos-index.tsv"
WIKTIONARY_DIR = RESOURCE_DIR / "wiktionary"
WIKTIONARY_USAGE_PATTERNS_PATH = WIKTIONARY_DIR / "usage-patterns.tsv"
WIKTIONARY_JSONL_CANDIDATES = [
    APP_HOME / "kaikki.org-dictionary-English.jsonl",
    BASE_DIR / "kaikki.org-dictionary-English.jsonl",
    WIKTIONARY_DIR / "kaikki.org-dictionary-English.jsonl",
]
WIKTIONARY_SCHEMA_VERSION = 15
APP_SCHEMA_VERSION = 10
PREBUILT_LEXICON_PATH = Path(
    os.environ.get(
        "TYPENG_LEXICON_PATH",
        str(RESOURCE_DIR / "lexicon" / "typeng-lexicon.sqlite3"),
    )
).expanduser().resolve()
WEB_MODE = os.environ.get("TYPENG_WEB_MODE") == "1"
WEB_ALLOWED_HOSTS = {
    host.strip().casefold()
    for host in os.environ.get("TYPENG_ALLOWED_HOSTS", "").split(",")
    if host.strip()
}
app = Flask(
    __name__,
    template_folder=str(APP_ROOT / "templates"),
    static_folder=str(APP_ROOT / "static"),
)
if WEB_MODE:
    # Hosted deployments terminate TLS at a trusted reverse proxy. Only the
    # nearest proxy hop is accepted so origin checks see the public URL.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
if not getattr(sys, "frozen", False):
    # Source development is collaborative and templates/styles change often.
    # Avoid serving a cached template together with newer CSS from disk.
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
DB_INITIALIZED = False
DB_INIT_LOCK = threading.Lock()
register_request_timing(app)
app.add_template_filter(definition_lines, "definition_lines")
app.add_template_filter(definition_items, "definition_items")
app.add_template_filter(display_pos_label, "display_pos_label")


app.config["SECRET_KEY"] = os.environ.get("TYPENG_SECRET_KEY") or load_or_create_secret(DATA_DIR)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=(
        WEB_MODE and os.environ.get("TYPENG_COOKIE_SECURE", "1") != "0"
    ),
)

if WEB_MODE and not os.environ.get("TYPENG_SECRET_KEY"):
    raise RuntimeError("TYPENG_SECRET_KEY is required in web mode")
@app.before_request
def protect_local_app() -> None:
    if WEB_MODE:
        if WEB_ALLOWED_HOSTS and host_name(request.host) not in WEB_ALLOWED_HOSTS:
            abort(403)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("Origin")
            if origin and not is_same_origin(origin, request.host_url):
                abort(403)
        ensure_db()
        public_endpoints = {"static", "access_web", "login", "register", "health"}
        g.current_user = None
        user_id = session.get("user_id")
        if user_id is not None:
            try:
                g.current_user = user_repository.fetch_by_id(get_db(), int(user_id))
            except (TypeError, ValueError):
                g.current_user = None
        if g.current_user is None:
            session.pop("user_id", None)
            session.pop("active_library_id", None)
            if request.endpoint not in public_endpoints:
                return redirect(url_for("login", next=request.full_path.rstrip("?")))
        return

    if not is_local_host(request.host):
        abort(403)
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("Origin")
        if origin and not is_local_origin(origin):
            abort(403)


@app.get("/access")
def access_web():
    return redirect(url_for("login" if WEB_MODE else "index"))


def auth_redirect_target() -> str:
    target = request.form.get("next", request.args.get("next", "")).strip()
    if target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("index")


def registration_device() -> tuple[str, str | None]:
    token = request.cookies.get("typeng_device", "").strip()
    new_token = None
    if token:
        identity = f"device:{token}"
    else:
        new_token = secrets.token_urlsafe(24)
        identity = f"ip:{request.remote_addr or 'unknown'}"
    digest = hashlib.sha256(
        f"{app.config['SECRET_KEY']}:{identity}".encode("utf-8")
    ).hexdigest()
    return digest, new_token


def no_store_auth_response(template: str, **context):
    response = app.make_response(render_template(template, **context))
    response.headers["Cache-Control"] = "no-store"
    _fingerprint, new_token = registration_device()
    if new_token:
        response.set_cookie(
            "typeng_device", new_token, max_age=365 * 24 * 60 * 60,
            httponly=True, secure=app.config["SESSION_COOKIE_SECURE"], samesite="Lax",
        )
    return response


@app.route("/login", methods=["GET", "POST"])
def login():
    if not WEB_MODE:
        return redirect(url_for("index"))
    if getattr(g, "current_user", None) is not None:
        return redirect(url_for("index"))
    error = ""
    username = ""
    if request.method == "POST":
        username, username_key = normalize_username(request.form.get("username", ""))
        user = user_repository.fetch_by_key(get_db(), username_key)
        password = request.form.get("password", "")
        if user is not None and check_password_hash(str(user["password_hash"]), password):
            session.clear()
            session["user_id"] = int(user["id"])
            user_repository.mark_login(get_db(), int(user["id"]))
            return redirect(auth_redirect_target())
        error = "用户名或密码不正确。"
    return no_store_auth_response(
        "auth.html", auth_mode="login", error=error, username=username,
        next_url=request.form.get("next", request.args.get("next", "")),
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if not WEB_MODE:
        return redirect(url_for("index"))
    if getattr(g, "current_user", None) is not None:
        return redirect(url_for("index"))
    error = ""
    username = ""
    if request.method == "POST":
        device_hash, _new_token = registration_device()
        today = today_iso()
        if user_repository.registration_attempt_count(get_db(), device_hash, today) >= 100:
            return no_store_auth_response(
                "auth.html", auth_mode="register",
                error="这台设备今天的注册尝试次数已达到上限，请明天再试。",
                username="", next_url="",
            ), 429

        username, username_key = normalize_username(request.form.get("username", ""))
        password = request.form.get("password", "")
        success = False
        if not re.fullmatch(r"[A-Za-z0-9_\u3400-\u9FFF]{1,32}", username):
            error = "用户名限 1–32 个中文、英文字母、数字或下划线。"
        elif len(password) < 6:
            error = "密码至少需要 6 位。"
        elif len(password) > 256:
            error = "密码不能超过 256 位。"
        elif user_repository.fetch_by_key(get_db(), username_key) is not None:
            error = "该用户名已经被使用。"
        else:
            try:
                user_id = user_repository.create(
                    get_db(), username, username_key, generate_password_hash(password)
                )
                cursor = get_db().execute(
                    "INSERT INTO libraries (user_id, name) VALUES (?, ?)",
                    (user_id, "Default Library"),
                )
                get_db().commit()
                session.clear()
                session["user_id"] = user_id
                session["active_library_id"] = int(cursor.lastrowid)
                success = True
            except sqlite3.IntegrityError:
                get_db().rollback()
                error = "该用户名已经被使用。"
        user_repository.record_registration_attempt(get_db(), device_hash, today, success)
        if success:
            return redirect(url_for("index"))
    return no_store_auth_response(
        "auth.html", auth_mode="register", error=error, username=username, next_url="",
    )


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login" if WEB_MODE else "index"))


@app.get("/health")
def health():
    get_db().execute("SELECT 1").fetchone()
    return jsonify({"status": "ok", "mode": "web" if WEB_MODE else "local"})


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = connect_db(DB_PATH)
    return g.db


# Compatibility names keep extensions and the existing test suite stable while
# schema ownership lives in typeng.schema.
table_columns = _schema.table_columns
merge_verb_part_duplicates = _schema.merge_verb_part_duplicates
migrate_plural_phrase_entries = _schema.migrate_plural_phrase_entries
update_word_part_preserving_duplicate = _schema.update_word_part_preserving_duplicate
migrate_inferred_phrase_entries = _schema.migrate_inferred_phrase_entries
ensure_metadata_table = _schema.ensure_metadata_table
clear_invalid_example_sentences = _schema.clear_invalid_example_sentences
simplify_existing_example_translations = _schema.simplify_existing_example_translations


def migrate_db(db: sqlite3.Connection) -> None:
    _schema.migrate_db(db, APP_SCHEMA_VERSION)


def init_db() -> None:
    _schema.initialize(get_db(), PREBUILT_LEXICON_PATH, APP_SCHEMA_VERSION)
    ensure_efllex_index(get_db(), EFLLEx_PATH)
    ensure_wiktionary_exam_pos_index(get_db(), WIKTIONARY_EXAM_POS_PATH)


_wiktionary.configure(
    db_provider=lambda: get_db(),
    path_provider=lambda: wiktionary_jsonl_path(),
    signature_provider=lambda: wiktionary_source_signature(),
    available_provider=lambda: wiktionary_lookup_available(),
    usage_patterns_provider=lambda: WIKTIONARY_USAGE_PATTERNS_PATH,
)
ensure_wiktionary_lookup_index = _wiktionary.ensure_wiktionary_lookup_index
ranked_wiktionary_example_candidates = _wiktionary.ranked_wiktionary_example_candidates
lookup_wiktionary_example = _wiktionary.lookup_wiktionary_example
lookup_wiktionary_definition = _wiktionary.lookup_wiktionary_definition
lookup_wiktionary_definition_records = _wiktionary.lookup_wiktionary_definition_records
lookup_wiktionary_patterns = _wiktionary.lookup_wiktionary_patterns
load_ecdict_data = _ecdict.load_ecdict_data
_ecdict.configure(
    db_provider=lambda: get_db(),
    bundled_path_provider=lambda: BUNDLED_ECDICT_PATH,
    cache_path_provider=lambda: ECDICT_CACHE_PATH,
    data_dir_provider=lambda: DATA_DIR,
    source_url_provider=lambda: ECDICT_SOURCE_URL,
    schema_provider=lambda: ECDICT_LOOKUP_SCHEMA_VERSION,
    loader_provider=lambda: load_ecdict_data(),
)
ecdict_entries_for_word = _ecdict.ecdict_entries_for_word
ecdict_source_signature = _ecdict.ecdict_source_signature
ensure_ecdict_lookup_index = _ecdict.ensure_ecdict_lookup_index
lookup_ecdict_word = _ecdict.lookup_ecdict_word


@app.teardown_appcontext
def close_db(_: object) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()




























@app.before_request
def ensure_db() -> None:
    # Schema checks run once per process. Versioned data migrations themselves
    # run once per database version, not once per application launch.
    global DB_INITIALIZED
    if DB_INITIALIZED:
        return
    with DB_INIT_LOCK:
        if not DB_INITIALIZED:
            init_db()
            DB_INITIALIZED = True


def count_words(status: str | None = None) -> int:
    return word_repository.count(get_db(), get_active_library_id(), status)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0).isoformat(sep=" ")


def today_iso() -> str:
    return datetime.now().date().isoformat()


def review_due_count() -> int:
    return review_service.due_count(
        get_db(), get_active_library_id(), STATUS_LEARNED,
        "next_review_at", today_iso(), require_incomplete_review=True,
    )


def review_scheduled_count() -> int:
    row = get_db().execute(
        """
        SELECT COUNT(*) AS count
        FROM words
        JOIN libraries ON libraries.id = words.library_id
        WHERE words.library_id = ?
          AND words.status = ?
          AND words.review_correct_count < libraries.review_target_count
          AND words.next_review_at IS NOT NULL
        """,
        (get_active_library_id(), STATUS_LEARNED),
    ).fetchone()
    return int(row["count"])


def wrong_due_count() -> int:
    return review_service.due_count(
        get_db(), get_active_library_id(), STATUS_WRONG,
        "wrong_next_review_at", today_iso(),
    )


def wrong_scheduled_count() -> int:
    row = get_db().execute(
        """
        SELECT COUNT(*) AS count
        FROM words
        WHERE library_id = ?
          AND status = ?
          AND wrong_next_review_at IS NOT NULL
        """,
        (get_active_library_id(), STATUS_WRONG),
    ).fetchone()
    return int(row["count"])


def review_target_count() -> int:
    library = get_active_library()
    return max(MIN_REVIEW_TARGET_COUNT, int(library["review_target_count"]))


def wrong_review_target_count() -> int:
    library = get_active_library()
    return max(MIN_WRONG_REVIEW_TARGET_COUNT, int(library["wrong_review_target_count"]))


































def base_prompt_mode_from_form() -> str:
    show_chinese = request.form.get("show_chinese") == "on"
    auto_audio = request.form.get("auto_audio") == "on"
    if show_chinese and auto_audio:
        return PROMPT_MIXED
    if show_chinese:
        return PROMPT_CHINESE
    return PROMPT_AUDIO


def prompt_mode_from_form(allow_cloze: bool = False) -> str:
    if allow_cloze and request.form.get("only_cloze") == "on":
        return PROMPT_CLOZE
    return base_prompt_mode_from_form()


def set_practice_options(prompt_mode: str) -> None:
    session["prompt_mode"] = prompt_mode
    session["fallback_prompt_mode"] = base_prompt_mode_from_form()
    if request.form.get("only_cloze") == "on":
        session["cloze_scope"] = CLOZE_SCOPE_ONLY
    elif request.form.get("use_cloze") == "on":
        session["cloze_scope"] = CLOZE_SCOPE_WITH
    else:
        session.pop("cloze_scope", None)
    session["show_definition"] = request.form.get("show_definition") == "on"
    session["show_phonetic"] = request.form.get("show_phonetic") == "on"


def cloze_scope_from_session() -> str:
    scope = session.get("cloze_scope", "")
    return scope if scope in CLOZE_SCOPES else ""


def only_cloze_from_form(allow_cloze: bool = False) -> bool:
    return allow_cloze and request.form.get("only_cloze") == "on"


def with_cloze_from_form(allow_cloze: bool = False) -> bool:
    return allow_cloze and request.form.get("use_cloze") == "on" and request.form.get("only_cloze") != "on"


def effective_prompt_mode(word: sqlite3.Row) -> str:
    prompt_mode = session.get("prompt_mode", PROMPT_MIXED)
    if prompt_mode == PROMPT_CLOZE and not cloze_prompt(word["example_sentence"], word["word"]):
        return session.get("fallback_prompt_mode", PROMPT_MIXED)
    return prompt_mode


def example_candidates_for_word(
    word: sqlite3.Row | dict[str, object], *, include_tagged: bool = False
) -> list[dict[str, object]]:
    """Return user examples first, followed by every suitable Wiktionary example."""
    word_id = int(word["id"])
    candidates: list[dict[str, object]] = []
    seen: set[str] = set()
    for row in example_repository.fetch_user_examples(get_db(), word_id):
        sentence = str(row["sentence"] or "").strip()
        if sentence and sentence not in seen and valid_example_sentence(sentence, str(word["word"])):
            seen.add(sentence)
            candidates.append({
                "sentence": sentence,
                "translation": row["translation"],
                "note": row["note"],
                "source": "user",
                "is_user": True,
            })

    if wiktionary_lookup_available():
        for row in ranked_wiktionary_example_candidates(
            str(word["word"]),
            str(word["part_of_speech"]),
            limit=None,
            include_tagged=include_tagged,
        ):
            sentence = str(row["example_sentence"] or "").strip()
            if not sentence or sentence in seen:
                continue
            is_excerpt = sentence.startswith("… ") or sentence.endswith(" …")
            if is_excerpt and candidates:
                continue
            seen.add(sentence)
            candidates.append({
                "sentence": sentence,
                "translation": None,
                "note": _lookup_note(row),
                "definition": row["definition"],
                "sense_rank": row["sense_rank"],
                "source": "wiktionary",
                "is_user": False,
            })

    def value(key: str) -> object | None:
        try:
            return word[key]
        except (IndexError, KeyError):
            return None

    legacy = str(value("example_sentence") or "").strip()
    legacy_is_user = value("example_source") == "user"
    legacy_is_deprioritized = (
        len(legacy) > 240 or legacy.startswith("… ") or legacy.endswith(" …")
    )
    if (
        legacy
        and legacy not in seen
        and not (candidates and legacy_is_deprioritized and not legacy_is_user)
        and valid_example_sentence(legacy, str(word["word"]))
        and (legacy_is_user or usable_wiktionary_example(legacy, str(word["word"])))
    ):
        candidates.insert(0, {
            "sentence": legacy,
            "translation": value("example_translation"),
            "note": value("example_note"),
            "source": "user" if legacy_is_user else "legacy",
            "is_user": legacy_is_user,
        })
    return candidates


def pattern_candidates_for_word(
    word: sqlite3.Row | dict[str, object]
) -> list[dict[str, object]]:
    """Return user-authored and dictionary fixed expressions for one word."""
    word_id = int(word["id"])
    try:
        part_of_speech = str(word["part_of_speech"])
    except (KeyError, IndexError):
        part_of_speech = ""
    candidates: list[dict[str, object]] = []
    seen: set[str] = set()
    for row in pattern_repository.fetch_user_patterns(get_db(), word_id):
        expression = str(row["expression"] or "").strip()
        if not expression or expression.casefold() in seen:
            continue
        seen.add(expression.casefold())
        candidates.append(
            {
                "id": int(row["id"]),
                "expression": expression,
                "definition": row["definition"],
                "sense_rank": row["sense_rank"],
                "usage_label": row["usage_label"] or "固定搭配",
                "source": "user",
                "source_ref": None,
                "enabled_for_cloze": bool(row["enabled_for_cloze"]),
                "is_user": True,
            }
        )
    if part_of_speech and wiktionary_lookup_available():
        for item in lookup_wiktionary_patterns(
            str(word["word"]), part_of_speech
        ):
            expression = str(item["expression"] or "").strip()
            if not expression or expression.casefold() in seen:
                continue
            seen.add(expression.casefold())
            candidates.append(dict(item))
    return candidates


def cloze_material_candidates(
    word: sqlite3.Row | dict[str, object]
) -> list[dict[str, object]]:
    """Choose material by type so numerous examples do not bury patterns."""
    patterns = [
        {
            "sentence": item["expression"],
            "translation": None,
            "note": item.get("usage_label"),
            "source": item.get("source"),
            "is_user": bool(item.get("is_user")),
            "material_type": "pattern",
            "definition": item.get("definition"),
            "sense_rank": item.get("sense_rank"),
        }
        for item in pattern_candidates_for_word(word)
        if item.get("enabled_for_cloze")
        and cloze_prompt(str(item.get("expression") or ""), str(word["word"]))
    ]
    examples = [
        {**item, "material_type": "example"}
        for item in example_candidates_for_word(word)
    ]
    user_groups = [
        group for group in (
            [item for item in patterns if item["is_user"]],
            [item for item in examples if item["is_user"]],
        ) if group
    ]
    dictionary_groups = [
        group for group in (
            [item for item in patterns if not item["is_user"]],
            [item for item in examples if not item["is_user"]],
        ) if group
    ]
    groups = user_groups or dictionary_groups
    if not groups:
        return []
    # Return a type-balanced order. The caller picks the first group and then
    # one row inside it, so 10 examples do not outweigh one fixed expression.
    selected_group = random.choice(groups)
    return selected_group


def practice_word_with_example(word: sqlite3.Row) -> dict[str, object]:
    """Choose stable Cloze material, preferring user-authored material."""
    cached = session.get("practice_example") or {}
    if int(cached.get("word_id", -1)) != int(word["id"]):
        candidates = cloze_material_candidates(word)
        selected = random.choice(candidates) if candidates else None
        cached = {"word_id": int(word["id"]), **selected} if selected else {"word_id": int(word["id"])}
        session["practice_example"] = cached
    result = dict(word)
    result["example_sentence"] = cached.get("sentence")
    result["example_translation"] = cached.get("translation")
    result["example_note"] = cached.get("note")
    result["example_source"] = cached.get("source")
    result["cloze_material_type"] = cached.get("material_type")
    return result


def ids_with_cloze(rows: list[sqlite3.Row], limit: int) -> list[int]:
    ids: list[int] = []
    for row in rows:
        full_word = fetch_word(int(row["id"]))
        if full_word is not None and cloze_material_candidates(full_word):
            ids.append(int(row["id"]))
            if len(ids) >= limit:
                break
    return ids


def cloze_ids_from_ids(ids: list[int]) -> list[int]:
    return [int(row["id"]) for row in fetch_words_by_ids(ids) if cloze_material_candidates(row)]


def start_pending_cloze_round() -> bool:
    pending_ids = [int(word_id) for word_id in session.get("pending_cloze_ids", [])]
    if not pending_ids:
        session.pop("pending_cloze_ids", None)
        return False
    session["practice_ids"] = pending_ids
    session["practice_index"] = 0
    session["prompt_mode"] = PROMPT_CLOZE
    session["cloze_scope"] = CLOZE_SCOPE_ONLY
    session["retry_ids"] = []
    session["awaiting_next"] = False
    session["last_result"] = None
    session["practice_round"] = int(session.get("practice_round", 1)) + 1
    session["cloze_followup_active"] = True
    session.pop("pending_cloze_ids", None)
    return True


























def wiktionary_jsonl_path() -> Path | None:
    for path in WIKTIONARY_JSONL_CANDIDATES:
        if path.exists():
            return path
    return None


def wiktionary_source_signature() -> str | None:
    path = wiktionary_jsonl_path()
    if not path:
        return None
    stat = path.stat()
    supplement = ""
    if WIKTIONARY_USAGE_PATTERNS_PATH.is_file():
        extra = WIKTIONARY_USAGE_PATTERNS_PATH.stat()
        supplement = f":{extra.st_size}:{int(extra.st_mtime)}"
    return f"{path.name}:{stat.st_size}:{int(stat.st_mtime)}:{WIKTIONARY_SCHEMA_VERSION}{supplement}"
















# Sense tags worth warning the learner about when they appear on an example.
# Mapped to a short human-readable label shown in cloze practice.






def _lookup_note(lookup: sqlite3.Row) -> str | None:
    """Extract an example note such as ``archaic usage`` from a lookup row."""
    try:
        return example_note_from_tags(lookup["sense_tags"])
    except (IndexError, KeyError):
        return None


def wiktionary_lookup_available() -> bool:
    return bool(wiktionary_jsonl_path()) or lookup_available(get_db(), "wiktionary_examples")


def example_lookup_available() -> bool:
    return wiktionary_lookup_available()


def wiktionary_part_lookup_available() -> bool:
    """Return whether an exact word/POS check can be performed.

    Release builds may ship the compact exam POS index without the much larger
    example/definition tables, so POS validation has its own availability
    check instead of reusing example availability.
    """
    db = get_db()
    if WIKTIONARY_EXAM_POS_PATH.is_file():
        ensure_wiktionary_exam_pos_index(db, WIKTIONARY_EXAM_POS_PATH)
    return bool(wiktionary_jsonl_path()) or any(
        lookup_available(db, table)
        for table in ("wiktionary_definitions", "wiktionary_examples", "wiktionary_exam_parts")
    )


def wiktionary_part_exists(word: str, part_of_speech: str) -> bool:
    """Confirm that Wiktionary contains the requested normalized word/POS."""
    if not wiktionary_part_lookup_available():
        return False
    word_keys = sorted(spelling_variants(word))
    groups = wiktionary_lookup_groups(part_of_speech, word)
    db = get_db()
    key_marks = ",".join("?" for _ in word_keys)
    group_marks = ",".join("?" for _ in groups)
    for table in ("wiktionary_definitions", "wiktionary_examples", "wiktionary_exam_parts"):
        if not db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (table,)
        ).fetchone():
            continue
        if db.execute(
            f"SELECT 1 FROM {table} WHERE word_key IN ({key_marks}) "
            f"AND part_group IN ({group_marks}) LIMIT 1",
            (*word_keys, *groups),
        ).fetchone():
            return True
    return False


def fill_examples_from_dictionaries(
    start: int = 1,
    end: int = 100,
    mode: str = "best",
) -> tuple[int, int]:
    if not example_lookup_available():
        return 0, -1

    rows = fetch_word_range(start, end, "id, word, part_of_speech, example_sentence, example_source")
    if not rows:
        return 0, 0

    matches: dict[int, tuple[str, str | None]] = {}
    definitions: dict[int, str] = {}
    if wiktionary_jsonl_path():
        ensure_wiktionary_lookup_index({str(row["word"]).strip().lower() for row in rows})
    for row in rows:
        word = str(row["word"])
        part_of_speech = str(row["part_of_speech"])
        definition = lookup_wiktionary_definition(word, part_of_speech)
        if definition:
            definitions[int(row["id"])] = definition

        if mode == "refresh":
            # A handwritten example always wins and is never replaced.
            if row["example_source"] == "user":
                continue
            lookup = refresh_example_candidate(word, part_of_speech, row["example_sentence"], top_n=8)
            if lookup:
                matches[int(row["id"])] = (lookup["example_sentence"], lookup["definition"], _lookup_note(lookup))
            continue

        # Fill (best) only fills entries that have no example yet. A word that
        # already has an example — whether the user typed it or a previous fill
        # added it — is left untouched, so hand-written examples are never lost.
        if str(row["example_sentence"] or "").strip():
            continue
        lookup = lookup_wiktionary_example(word, part_of_speech)
        if lookup:
            matches[int(row["id"])] = (lookup["example_sentence"], lookup["definition"], _lookup_note(lookup))

    # Neither mode clears existing content: fill only adds where empty, and
    # refresh only replaces entries that found a new candidate.
    for word_id, (sentence, example_definition, note) in matches.items():
        definition = definitions.get(word_id) or example_definition
        get_db().execute(
            """
            UPDATE words
            SET example_sentence = ?,
                example_translation = NULL,
                example_note = ?,
                example_source = 'wiktionary',
                definition = COALESCE(?, definition),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND library_id = ?
            """,
            (sentence, note, definition, word_id, get_active_library_id()),
        )
    definition_only_ids = sorted(set(definitions) - set(matches))
    for batch_start in range(0, len(definition_only_ids), 500):
        batch = definition_only_ids[batch_start : batch_start + 500]
        placeholders = ",".join("?" for _ in batch)
        params: list[object] = []
        case_parts: list[str] = []
        for word_id in batch:
            case_parts.append("WHEN ? THEN ?")
            params.extend([word_id, definitions[word_id]])
        get_db().execute(
            f"""
            UPDATE words
            SET definition = CASE id {' '.join(case_parts)} ELSE definition END,
                updated_at = CURRENT_TIMESTAMP
            WHERE library_id = ?
              AND id IN ({placeholders})
            """,
            [*params, get_active_library_id(), *batch],
        )
    for word_id in sorted(set(matches) | set(definition_only_ids)):
        lexicon_repository.sync_learning_word(get_db(), word_id)
    get_db().commit()
    return len(matches), len(rows)


def schedule_initial_review(word_id: int) -> None:
    review_service.schedule_initial(
        get_db(), get_active_library_id(), word_id, next_review_date,
    )


def complete_review(word_id: int) -> None:
    review_service.complete(
        get_db(), get_active_library_id(), word_id, review_target_count(),
        STATUS_LEARNED, next_review_date,
    )


def reset_review_schedule(word_id: int) -> None:
    review_service.reset(get_db(), get_active_library_id(), word_id)


def fetch_libraries() -> list[sqlite3.Row]:
    return library_repository.fetch_all(get_db(), current_user_id())


def fetch_library(library_id: int) -> sqlite3.Row | None:
    return library_repository.fetch_one(get_db(), library_id, current_user_id())


def current_user_id() -> int | None:
    user = getattr(g, "current_user", None)
    return int(user["id"]) if WEB_MODE and user is not None else None


def get_active_library_id() -> int:
    db = get_db()
    requested_id = session.get("active_library_id")
    if requested_id is not None:
        row = fetch_library(int(requested_id))
        if row:
            return int(row["id"])

    user_id = current_user_id()
    row = db.execute(
        "SELECT id FROM libraries WHERE user_id IS ? ORDER BY id ASC LIMIT 1",
        (user_id,),
    ).fetchone()
    if row is None:
        db.execute(
            "INSERT INTO libraries (user_id, name) VALUES (?, ?)",
            (user_id, "Default Library"),
        )
        db.commit()
        row = db.execute(
            "SELECT id FROM libraries WHERE user_id IS ? ORDER BY id ASC LIMIT 1",
            (user_id,),
        ).fetchone()
    session["active_library_id"] = int(row["id"])
    return int(row["id"])


def get_active_library() -> sqlite3.Row:
    return fetch_library(get_active_library_id())


def get_or_create_library(name: str) -> int:
    return library_repository.get_or_create(get_db(), name, current_user_id())


def reset_ecdict_library(library_id: int) -> None:
    library_repository.delete_source_words(get_db(), library_id, "ECDICT")
    unit_repository.compact_empty_units(get_db(), library_id)
    get_db().commit()


def prune_word_ids_from_session(word_ids: set[int]) -> None:
    if not word_ids:
        return

    ids = [int(item) for item in session.get("practice_ids", [])]
    if ids:
        session["practice_ids"] = [word_id for word_id in ids if word_id not in word_ids]
        session["practice_index"] = min(int(session.get("practice_index", 0)), len(session["practice_ids"]))

    for key in ("retry_ids", "missed_ids"):
        stored_ids = [int(item) for item in session.get(key, [])]
        if stored_ids:
            session[key] = [word_id for word_id in stored_ids if word_id not in word_ids]


def delete_word_ids(word_ids: set[int], library_id: int) -> int:
    if not word_ids:
        return 0

    deleted = 0
    sorted_ids = sorted(word_ids)
    for start in range(0, len(sorted_ids), 500):
        batch = sorted_ids[start : start + 500]
        placeholders = ",".join("?" for _ in batch)
        cursor = get_db().execute(
            f"DELETE FROM words WHERE library_id = ? AND id IN ({placeholders})",
            [library_id, *batch],
        )
        deleted += int(cursor.rowcount)
    unit_repository.compact_empty_units(get_db(), library_id)
    get_db().commit()
    prune_word_ids_from_session(word_ids)
    return deleted






























































def refresh_example_candidate(
    word: str,
    part_of_speech: str,
    current_sentence: str | None = None,
    top_n: int = 8,
) -> sqlite3.Row | None:
    current = (current_sentence or "").strip()
    seen_sentences = {current} if current else set()
    candidates: list[sqlite3.Row] = []
    for row in ranked_wiktionary_example_candidates(word, part_of_speech, limit=top_n):
        sentence = str(row["example_sentence"] or "").strip()
        if not sentence or sentence in seen_sentences:
            continue
        seen_sentences.add(sentence)
        candidates.append(row)

    return random.choice(candidates[:top_n]) if candidates else None


def library_word_count() -> int:
    return int(get_db().execute(
        "SELECT COUNT(*) AS total FROM words WHERE library_id = ?",
        (get_active_library_id(),),
    ).fetchone()["total"])


def parse_word_range(prefix: str, default_start: int = 1, default_end: int = 100, max_span: int = 2000) -> tuple[int, int]:
    try:
        start = int(request.form.get(f"{prefix}_start", str(default_start)))
    except ValueError:
        start = default_start
    try:
        end = int(request.form.get(f"{prefix}_end", str(default_end)))
    except ValueError:
        end = default_end
    # Clamp to a sane ceiling so an oversized value cannot become a SQLite
    # LIMIT/OFFSET larger than a 64-bit integer, which would raise OverflowError.
    max_index = 100_000_000
    start = min(max(1, start), max_index)
    end = min(max(start, end), max_index)
    if end - start + 1 > max_span:
        end = start + max_span - 1
    return start, end


def fetch_word_range(start: int, end: int, columns: str = "*") -> list[sqlite3.Row]:
    limit = max(0, end - start + 1)
    offset = max(0, start - 1)
    if limit <= 0:
        return []
    return get_db().execute(
        f"""
        SELECT {columns}
        FROM words
        WHERE library_id = ?
        ORDER BY
            CASE WHEN frequency IS NULL THEN 1 ELSE 0 END ASC,
            frequency ASC,
            lower(word) ASC,
            part_of_speech ASC,
            id ASC
        LIMIT ? OFFSET ?
        """,
        (get_active_library_id(), limit, offset),
    ).fetchall()


def enrich_entries_from_ecdict(entries: list[dict[str, str]]) -> int:
    enriched = 0
    cache: dict[str, sqlite3.Row | None] = {}
    for entry in entries:
        word_key = entry["word"].strip().lower()
        if word_key not in cache:
            cache[word_key] = lookup_ecdict_word(entry["word"])
        lookup = cache[word_key]
        if not lookup:
            continue

        changed = False
        for key in ("phonetic", "definition", "frequency"):
            if not entry.get(key) and lookup[key] is not None:
                entry[key] = lookup[key]
                changed = True
        if lookup["source_tags"]:
            entry["source_tags"] = lookup["source_tags"]
            changed = True
        entry["source"] = "ECDICT"
        if changed:
            enriched += 1
    return enriched


def import_entries(
    entries: list[dict[str, str]],
    library_id: int | None = None,
    update_existing: bool = True,
) -> tuple[int, int, int]:
    if library_id is None:
        library_id = get_active_library_id()
    return word_repository.import_entries(
        get_db(), library_id, entries, normalize_user_pos,
        lexicon_repository.sync_learning_word, update_existing,
    )


def fetch_words(status: str | None = None) -> list[sqlite3.Row]:
    return word_repository.fetch_all(get_db(), get_active_library_id(), status)


def build_word_filter(search: str) -> tuple[str, list[str]]:
    search = search.strip()
    if not search:
        return "", []

    pattern = f"%{search.lower()}%"
    return (
        """
        AND (
            lower(word) LIKE ?
            OR lower(part_of_speech) LIKE ?
            OR lower(meaning) LIKE ?
        )
        """,
        [pattern, pattern, pattern],
    )


def fetch_words_page(
    page: int,
    per_page: int,
    search: str = "",
    sort_mode: str = SORT_FREQUENCY,
) -> tuple[list[sqlite3.Row], dict[str, int | str | bool]]:
    db = get_db()
    library_id = get_active_library_id()
    filter_sql, filter_params = build_word_filter(search)
    if sort_mode not in LIBRARY_SORT_MODES:
        sort_mode = SORT_FREQUENCY

    if sort_mode == SORT_ALPHA:
        order_sql = """
            lower(word) ASC,
            part_of_speech ASC,
            CASE WHEN frequency IS NULL THEN 1 ELSE 0 END ASC,
            frequency ASC,
            id ASC
        """
    else:
        order_sql = """
            CASE WHEN frequency IS NULL THEN 1 ELSE 0 END ASC,
            frequency ASC,
            lower(word) ASC,
            part_of_speech ASC,
            id ASC
        """

    total_row = db.execute(
        f"""
        SELECT COUNT(*) AS count
        FROM words
        WHERE library_id = ?
        {filter_sql}
        """,
        [library_id, *filter_params],
    ).fetchone()
    total = int(total_row["count"])
    total_pages = max(1, ceil(total / per_page))
    page = max(1, min(page, total_pages))
    offset = (page - 1) * per_page

    rows = db.execute(
        f"""
        SELECT *
        FROM words
        WHERE library_id = ?
        {filter_sql}
        ORDER BY {order_sql}
        LIMIT ? OFFSET ?
        """,
        [library_id, *filter_params, per_page, offset],
    ).fetchall()

    pagination = {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "start": offset + 1 if total else 0,
        "end": min(offset + len(rows), total),
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": max(1, page - 1),
        "next_page": min(total_pages, page + 1),
        "search": search,
        "sort": sort_mode,
    }
    return rows, pagination


def fetch_words_by_ids(ids: list[int]) -> list[sqlite3.Row]:
    return word_repository.fetch_by_ids(get_db(), get_active_library_id(), ids)


def fetch_word(word_id: int) -> sqlite3.Row | None:
    return word_repository.fetch_one(get_db(), get_active_library_id(), word_id)


def clear_practice_session() -> None:
    session.pop("practice_ids", None)
    session.pop("practice_index", None)
    session.pop("awaiting_next", None)
    session.pop("last_result", None)
    session.pop("practice_mode", None)
    session.pop("retry_ids", None)
    session.pop("missed_ids", None)
    session.pop("practice_round", None)
    session.pop("prompt_mode", None)
    session.pop("fallback_prompt_mode", None)
    session.pop("cloze_scope", None)
    session.pop("pending_cloze_ids", None)
    session.pop("cloze_followup_active", None)
    session.pop("show_definition", None)
    session.pop("show_phonetic", None)
    session.pop("practice_example", None)
    session.pop("cloze_feedback_context", None)


def redirect_back(default_endpoint: str = "index"):
    next_url = request.form.get("next", "").strip()
    if next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect(url_for(default_endpoint))


def base_context() -> dict[str, object]:
    return {
        "total_count": count_words(),
        "new_count": count_words(STATUS_NEW),
        "learned_count": count_words(STATUS_LEARNED),
        "wrong_count": count_words(STATUS_WRONG),
        "due_review_count": review_due_count(),
        "scheduled_review_count": review_scheduled_count(),
        "due_wrong_count": wrong_due_count(),
        "scheduled_wrong_count": wrong_scheduled_count(),
        "review_target_count": review_target_count(),
        "min_review_target_count": MIN_REVIEW_TARGET_COUNT,
        "max_review_target_count": MAX_REVIEW_TARGET_COUNT,
        "wrong_review_target_count": wrong_review_target_count(),
        "min_wrong_review_target_count": MIN_WRONG_REVIEW_TARGET_COUNT,
        "max_wrong_review_target_count": MAX_WRONG_REVIEW_TARGET_COUNT,
        "libraries": fetch_libraries(),
        "active_library": get_active_library(),
        "ecdict_presets": ECDICT_PRESET_LIBRARIES,
        "current_review_date": today_iso(),
    }


def render_workspace(mode: str):
    status = {
        "home": STATUS_NEW,
        "learned": STATUS_LEARNED,
        "wrong": STATUS_WRONG,
        "libraries": None,
    }[mode]
    endpoint = {"home": "index", "learned": "learned", "wrong": "wrong", "libraries": "libraries"}[mode]
    edit_mode = mode == "libraries" and request.args.get("edit") == "1"
    raw_search_query = request.args.get("q", "").strip()
    search_mode = (
        mode == "libraries"
        and not edit_mode
        and (request.args.get("search") == "1" or "q" in request.args)
    )
    search_query = (
        raw_search_query
        if re.fullmatch(r"[A-Za-z][A-Za-z '\-]*", raw_search_query)
        else ""
    )
    editor_panel = request.args.get("panel", "") if edit_mode else ""
    if editor_panel not in {"", "new", "add", "import", "format", "export", "dedupe", "presets", "manage"}:
        editor_panel = ""
    try:
        selected_unit = max(1, int(request.args.get("unit", "1")))
    except ValueError:
        selected_unit = 1
    units = unit_repository.summaries(get_db(), get_active_library_id(), status)
    if units:
        selected_unit = min(selected_unit, units[-1]["number"])
    unit_words = (
        unit_repository.search_words(
            get_db(), get_active_library_id(), search_query
        )
        if search_mode
        else unit_repository.fetch(
            get_db(), get_active_library_id(), selected_unit, status
        )
    )
    selected_word = None
    selected_examples: list[dict[str, object]] = []
    selected_patterns: list[dict[str, object]] = []
    selected_definitions: list[str] = []
    try:
        selected_word_id = int(request.args.get("word", "0"))
    except ValueError:
        selected_word_id = 0
    if selected_word_id:
        candidate = fetch_word(selected_word_id)
        if candidate is not None and (status is None or candidate["status"] == status):
            selected_word = candidate
            selected_examples = example_candidates_for_word(candidate, include_tagged=True)
            selected_patterns = pattern_candidates_for_word(candidate)
            definition_records = lookup_wiktionary_definition_records(
                str(candidate["word"]), str(candidate["part_of_speech"]), limit=None
            )
            if definition_records:
                selected_definitions = [
                    str(record["definition"]) for record in definition_records
                ]
                rank_numbers = {
                    int(record["sense_rank"]): number
                    for number, record in enumerate(definition_records, start=1)
                }
                definition_numbers = {
                    str(record["raw_definition"]): number
                    for number, record in enumerate(definition_records, start=1)
                }
                for example in selected_examples:
                    if example.get("is_user"):
                        continue
                    number = None
                    if example.get("definition"):
                        number = definition_numbers.get(str(example["definition"]))
                    sense_rank = example.get("sense_rank")
                    if number is None and sense_rank is not None:
                        number = rank_numbers.get(int(sense_rank))
                    if number is not None:
                        example["definition_number"] = number
                for pattern in selected_patterns:
                    number = None
                    if pattern.get("definition"):
                        number = definition_numbers.get(str(pattern["definition"]))
                    sense_rank = pattern.get("sense_rank")
                    if number is None and sense_rank is not None:
                        number = rank_numbers.get(int(sense_rank))
                    if number is not None:
                        pattern["definition_number"] = number
            else:
                selected_definitions = definition_items(
                    str(candidate["definition"] or ""), str(candidate["part_of_speech"])
                )
    return render_template(
        "workspace.html",
        workspace_mode=mode,
        workspace_endpoint=endpoint,
        edit_mode=edit_mode,
        editor_panel=editor_panel,
        search_mode=search_mode,
        search_query=raw_search_query,
        page_title={"home": "待学", "learned": "复习", "wrong": "错词", "libraries": "词库"}[mode],
        units=units,
        selected_unit=selected_unit,
        unit_words=unit_words,
        selected_word=selected_word,
        selected_examples=selected_examples,
        selected_patterns=selected_patterns,
        selected_definitions=selected_definitions,
        part_of_speech_options=PART_OF_SPEECH_OPTIONS,
        add_word_messages=session.pop("add_word_messages", []),
        workspace_add_draft=session.pop("workspace_add_draft", {}),
        comparable_libraries=[
            library for library in fetch_libraries()
            if int(library["id"]) != get_active_library_id()
        ],
        hide_global_stats=True,
        **base_context(),
    )


@app.route("/")
def index():
    edit_mode = request.args.get("edit") == "1"
    if not edit_mode:
        return render_workspace("home")
    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        page = 1
    search = request.args.get("q", "").strip()
    sort_mode = request.args.get("sort", SORT_FREQUENCY).strip()
    if sort_mode not in LIBRARY_SORT_MODES:
        sort_mode = SORT_FREQUENCY
    words, pagination = fetch_words_page(page, LIBRARY_PAGE_SIZE, search, sort_mode)
    comparable_libraries = [library for library in fetch_libraries() if int(library["id"]) != get_active_library_id()]

    # Surface a pending preset-rebuild confirmation, if one was requested.
    preset_confirm = None
    if request.args.get("confirm_preset") == "1" and session.get("pending_preset_key"):
        preset_confirm = {
            "key": session["pending_preset_key"],
            "name": session.get("pending_preset_name", ""),
            "count": session.get("pending_preset_count", 0),
        }

    return render_template(
        "index.html",
        words=words,
        edit_mode=edit_mode,
        pagination=pagination,
        sort_modes={"frequency": "按词频", "alpha": "按字母"},
        comparable_libraries=comparable_libraries,
        part_of_speech_options=PART_OF_SPEECH_OPTIONS,
        add_word_messages=session.pop("add_word_messages", []),
        preset_confirm=preset_confirm,
        hide_global_stats=True,
        **base_context(),
    )


@app.route("/import-format")
def import_format():
    return render_template("import_format.html", **base_context())


@app.post("/libraries/select")
def select_library():
    try:
        library_id = int(request.form.get("library_id", ""))
    except ValueError:
        flash("请选择有效的词库。", "error")
        return redirect(url_for("index"))

    if not fetch_library(library_id):
        flash("该词库不存在。", "error")
        return redirect(url_for("index"))

    session["active_library_id"] = library_id
    clear_practice_session()
    return redirect_back()


@app.post("/libraries/add")
def add_library():
    name = request.form.get("library_name", "").strip()
    workspace_edit = request.form.get("workspace") == "1"
    add_redirect = url_for("libraries", edit=1, panel="new") if workspace_edit else url_for("index")
    if not name:
        flash("请输入词库名称。", "error")
        return redirect(add_redirect)
    if len(name) > 80:
        flash("词库名称不能超过 80 个字符。", "error")
        return redirect(add_redirect)

    try:
        cursor = get_db().execute(
            "INSERT INTO libraries (user_id, name) VALUES (?, ?)",
            (current_user_id(), name),
        )
        get_db().commit()
        session["active_library_id"] = int(cursor.lastrowid)
        clear_practice_session()
        flash("词库已创建。", "success")
    except sqlite3.IntegrityError:
        flash("同名词库已经存在。", "error")

    return redirect(url_for("libraries", edit=1) if workspace_edit else url_for("index"))


@app.post("/libraries/rename")
def rename_library():
    name = request.form.get("library_name", "").strip()
    if not name:
        flash("请输入词库名称。", "error")
    elif len(name) > 80:
        flash("词库名称不能超过 80 个字符。", "error")
    else:
        try:
            library_repository.rename(get_db(), get_active_library_id(), name)
            flash("词库名称已更新。", "success")
        except sqlite3.IntegrityError:
            get_db().rollback()
            flash("同名词库已经存在。", "error")
    return redirect(url_for("libraries", edit=1, panel="manage"))


@app.post("/libraries/delete")
def delete_library():
    active_id = get_active_library_id()
    remaining = [row for row in fetch_libraries() if int(row["id"]) != active_id]
    if not remaining:
        flash("至少需要保留一个词库。", "error")
        return redirect(url_for("libraries", edit=1, panel="manage"))
    library_repository.delete(get_db(), active_id)
    session["active_library_id"] = int(remaining[0]["id"])
    clear_practice_session()
    flash("词库及其学习记录已删除。", "success")
    return redirect(url_for("libraries", edit=1, panel="manage"))


def _export_cell(value: object) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n")


@app.get("/libraries/export")
def export_library():
    export_format = request.args.get("format", "csv").strip().casefold()
    scope = request.args.get("scope", "library").strip().casefold()
    if export_format not in {"txt", "csv"} or scope not in {"library", "unit"}:
        abort(400)
    try:
        selected_unit = max(1, int(request.args.get("unit", "1")))
    except ValueError:
        abort(400)

    library = get_active_library()
    unit_number = selected_unit if scope == "unit" else None
    rows = word_repository.fetch_for_export(
        get_db(), int(library["id"]), unit_number
    )
    buffer = io.StringIO(newline="")
    if export_format == "csv":
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow([
            "unit", "word", "part_of_speech", "meaning", "phonetic",
            "definition", "example_sentence", "example_translation",
            "status", "source_tags",
        ])
        for row in rows:
            writer.writerow([
                row["unit_number"], row["word"], row["part_of_speech"],
                row["meaning"], row["phonetic"], row["definition"],
                row["exported_example_sentence"],
                row["exported_example_translation"], row["status"],
                row["source_tags"],
            ])
    else:
        buffer.write(f"# TypEng · {_export_cell(library['name'])}\n")
        current_unit: int | None = None
        for row in rows:
            row_unit = int(row["unit_number"] or 0)
            if row_unit != current_unit:
                current_unit = row_unit
                buffer.write(f"# Unit {row_unit}\n")
            cells = [
                row["word"], row["part_of_speech"], row["meaning"],
                row["exported_example_sentence"],
                row["exported_example_translation"],
            ]
            # Tabs/newlines would change the importer's column structure.
            buffer.write("\t".join(
                re.sub(r"\s+", " ", _export_cell(cell)).strip()
                for cell in cells
            ).rstrip("\t") + "\n")

    payload = io.BytesIO(buffer.getvalue().encode("utf-8-sig"))
    safe_name = re.sub(
        r"[^\w.-]+", "-", str(library["name"]), flags=re.UNICODE
    ).strip("-.")
    safe_name = safe_name or f"library-{int(library['id'])}"
    scope_suffix = f"unit-{selected_unit}" if scope == "unit" else "all"
    return send_file(
        payload,
        mimetype=(
            "text/csv; charset=utf-8"
            if export_format == "csv"
            else "text/plain; charset=utf-8"
        ),
        as_attachment=True,
        download_name=f"{safe_name}-{scope_suffix}.{export_format}",
        max_age=0,
    )


@app.post("/libraries/units/add")
def add_library_unit():
    unit_number = unit_repository.create(get_db(), get_active_library_id())
    flash(f"已新建单元 {unit_number}。", "success")
    return redirect(url_for("libraries", edit=1, unit=unit_number, panel="add"))


@app.post("/review/settings")
def update_review_settings():
    try:
        target_count = int(request.form.get("review_target_count", str(DEFAULT_REVIEW_TARGET_COUNT)))
    except ValueError:
        target_count = DEFAULT_REVIEW_TARGET_COUNT
    target_count = max(MIN_REVIEW_TARGET_COUNT, min(target_count, MAX_REVIEW_TARGET_COUNT))
    get_db().execute(
        """
        UPDATE libraries
        SET review_target_count = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (target_count, get_active_library_id()),
    )
    get_db().commit()
    flash(f"复习目标已设为累计答对 {target_count} 次。", "success")
    return redirect_back()


@app.post("/wrong/settings")
def update_wrong_settings():
    try:
        target_count = int(request.form.get("wrong_review_target_count", str(DEFAULT_WRONG_REVIEW_TARGET_COUNT)))
    except ValueError:
        target_count = DEFAULT_WRONG_REVIEW_TARGET_COUNT
    target_count = max(MIN_WRONG_REVIEW_TARGET_COUNT, min(target_count, MAX_WRONG_REVIEW_TARGET_COUNT))
    get_db().execute(
        """
        UPDATE libraries
        SET wrong_review_target_count = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (target_count, get_active_library_id()),
    )
    get_db().commit()
    flash(f"错词巩固目标已设为累计答对 {target_count} 次。", "success")
    return redirect_back()


@app.post("/import")
def import_words():
    workspace_edit = request.form.get("workspace") == "1"
    try:
        workspace_unit = max(1, int(request.form.get("unit", "1")))
    except ValueError:
        workspace_unit = 1
    import_redirect = (
        url_for("libraries", edit=1, unit=workspace_unit, panel="import")
        if workspace_edit else url_for("index")
    )
    uploaded = request.files.get("word_file")
    if not uploaded or uploaded.filename == "":
        flash("请选择 TXT 或 CSV 文件。", "error")
        return redirect(import_redirect)

    try:
        entries, errors = parse_word_file(uploaded.filename, uploaded.read())
    except UnicodeDecodeError:
        flash("导入失败：请使用 UTF-8 编码的 TXT 或 CSV 文件。", "error")
        return redirect(import_redirect)

    enriched = 0
    if entries:
        enriched = enrich_entries_from_ecdict(entries)
        inserted, updated, _skipped = import_entries(entries)
        suffix = f" ECDICT filled {enriched} entries." if enriched else ""
        flash(f"已导入 {inserted} 个新词，并更新 {updated} 条已有词条。{suffix}", "success")
    if errors:
        preview = "; ".join(errors[:3])
        suffix = "" if len(errors) <= 3 else f" 另有 {len(errors) - 3} 条。"
        flash(f"部分内容已跳过：{preview}。{suffix}", "error")
    if not entries and not errors:
        flash("没有找到可用词条。", "error")

    return redirect(import_redirect)


@app.post("/examples/fill")
def fill_auto_examples():
    if not example_lookup_available():
        flash(
            "没有找到例句数据，请先安装 Wiktionary 数据。",
            "error",
        )
        return redirect(url_for("index", edit=1))

    start, end = parse_word_range("example", default_start=1, default_end=100, max_span=2000)
    mode = request.form.get("example_mode", "best")
    if mode not in {"best", "refresh"}:
        mode = "best"
    matched, checked = fill_examples_from_dictionaries(
        start,
        end,
        mode=mode,
    )
    if checked == 0:
        flash(f"第 {start}–{end} 条范围内没有词汇。", "success")
    elif mode == "refresh":
        flash(
            f"检查第 {start}–{end} 条中的 {checked} 个词后，已更新 {matched} 条默认例句。",
            "success",
        )
    else:
        flash(
            f"检查第 {start}–{end} 条中的 {checked} 个词后，已为 {matched} 个缺少例句的词条补充默认例句。",
            "success",
        )
    return redirect(url_for("index", edit=1))


@app.post("/import/ecdict")
def import_ecdict():
    uploaded = request.files.get("ecdict_file")
    if not uploaded or uploaded.filename == "":
        flash("请选择 ECDICT CSV 文件。", "error")
        return redirect(url_for("index", edit=1))

    try:
        grouped, errors = parse_ecdict_csv(uploaded.read())
    except UnicodeDecodeError:
        flash("ECDICT 导入失败：请使用 UTF-8 编码的 CSV 文件。", "error")
        return redirect(url_for("index", edit=1))

    if errors:
        flash(" ".join(errors), "error")
        return redirect(url_for("index", edit=1))

    summaries = []
    first_library_id = None
    preset_keys_by_name = {
        str(config["name"]): key
        for key, config in ECDICT_PRESET_LIBRARIES.items()
    }
    for library_name, entries in grouped.items():
        preset_key = preset_keys_by_name.get(library_name)
        if preset_key:
            entries, stats = apply_exam_policy(get_db(), preset_key, entries)
            if stats.get("wiktionary_definitions_unavailable"):
                summaries.append(f"{library_name}：缺少 Wiktionary 英文释义索引，已跳过")
                continue
            removed = int(stats.get("total", 0)) - len(entries)
            if not entries:
                summaries.append(f"{library_name}：没有通过英文释义与难度校验的词条")
                continue
        else:
            removed = 0
        library_id = get_or_create_library(library_name)
        reset_ecdict_library(library_id)
        if first_library_id is None:
            first_library_id = library_id
        inserted, _updated, _skipped = import_entries(entries, library_id=library_id)
        removed_note = f"，剔除 {removed} 个" if removed else ""
        summaries.append(f"{library_name}：新增 {inserted} 个{removed_note}")

    if first_library_id is not None:
        session["active_library_id"] = first_library_id
        clear_practice_session()

    flash("ECDICT 导入完成。" + "；".join(summaries), "success")
    return redirect(url_for("index"))


def clear_pending_preset() -> None:
    session.pop("pending_preset_key", None)
    session.pop("pending_preset_name", None)
    session.pop("pending_preset_count", None)


def load_preset_entries(preset_key: str) -> tuple[str, list[dict[str, str]] | None]:
    """Return (library_name, entries) for a preset key, or (name, None) on error
    after flashing an appropriate message."""
    preset = ECDICT_PRESET_LIBRARIES.get(preset_key)
    if not preset:
        flash("请选择有效的预设词库。", "error")
        return "", None

    # Release and web deployments use the normalized lookup cache, avoiding a
    # 63 MB CSV download and parse in the user's request.
    try:
        preset_tags = set(preset["tags"])
        clauses = " OR ".join("source_tags LIKE ?" for _ in preset_tags)
        rows = get_db().execute(
            f"""
            SELECT word, part_of_speech, meaning, phonetic,
                   definition, frequency, source_tags
            FROM ecdict_preset_entries
            WHERE {clauses}
            ORDER BY CASE WHEN frequency IS NULL THEN 1 ELSE 0 END,
                     frequency, lower(word), part_of_speech
            """,
            [f"%{tag}%" for tag in sorted(preset_tags)],
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    indexed_entries = [
        {
            "word": row["word"],
            "part_of_speech": row["part_of_speech"],
            "meaning": row["meaning"],
            "phonetic": row["phonetic"],
            "definition": row["definition"],
            "frequency": row["frequency"],
            "source": "ECDICT",
            "source_tags": row["source_tags"],
        }
        for row in rows
        if split_ecdict_tags(str(row["source_tags"] or "")) & preset_tags
    ]
    if indexed_entries:
        filtered, stats = apply_exam_policy(get_db(), preset_key, indexed_entries)
        if stats.get("wiktionary_definitions_unavailable"):
            flash("Wiktionary 英文释义索引不可用，无法安全生成预设词库。", "error")
            return str(preset["name"]), None
        if not filtered:
            flash(f"{preset['name']} 中没有通过英文释义与难度校验的词条。", "error")
            return str(preset["name"]), None
        return str(preset["name"]), filtered

    try:
        raw = load_ecdict_data()
    except Exception:
        flash(
            "无法载入 ECDICT 数据，请先在资源目录中安装 ecdict.csv。",
            "error",
        )
        return "", None

    grouped, errors = parse_ecdict_csv(raw, presets={preset_key: preset})
    if errors:
        flash(" ".join(errors), "error")
        return "", None

    library_name = str(preset["name"])
    entries = grouped.get(library_name, [])
    if not entries:
        flash(f"ECDICT 中没有找到 {library_name} 对应的词汇。", "error")
        return library_name, None
    filtered, stats = apply_exam_policy(get_db(), preset_key, entries)
    if stats.get("wiktionary_definitions_unavailable"):
        flash("Wiktionary 英文释义索引不可用，无法安全生成预设词库。", "error")
        return library_name, None
    if not filtered:
        flash(f"{library_name} 中没有通过英文释义与难度校验的词条。", "error")
        return library_name, None
    return library_name, filtered


def unique_library_name(base_name: str) -> str:
    """Return base_name, or base_name (2), (3), ... if it is already taken."""
    existing = {
        str(row["name"])
        for row in get_db().execute(
            "SELECT name FROM libraries WHERE user_id IS ?", (current_user_id(),)
        ).fetchall()
    }
    if base_name not in existing:
        return base_name
    index = 2
    while f"{base_name} ({index})" in existing:
        index += 1
    return f"{base_name} ({index})"


@app.post("/presets/ecdict")
def create_ecdict_preset():
    preset_key = request.form.get("preset_key", "").strip().lower()
    library_name, entries = load_preset_entries(preset_key)
    if entries is None:
        clear_pending_preset()
        return redirect(url_for("index"))

    # If a library with this name already exists and has user content, require
    # an explicit "confirm" flag to prevent an accidental rebuild that would
    # wipe the user's edits and deletions.
    existing_row = get_db().execute(
        "SELECT id FROM libraries WHERE name = ? AND user_id IS ?",
        (library_name, current_user_id()),
    ).fetchone()
    if existing_row and request.form.get("confirm") != "1":
        word_count = get_db().execute(
            "SELECT COUNT(*) AS c FROM words WHERE library_id = ?",
            (int(existing_row["id"]),),
        ).fetchone()["c"]
        if word_count > 0:
            session["pending_preset_key"] = preset_key
            session["pending_preset_name"] = library_name
            session["pending_preset_count"] = word_count
            return redirect(url_for("index", confirm_preset=1))

    library_id = get_or_create_library(library_name)
    reset_ecdict_library(library_id)
    inserted, _updated, _skipped = import_entries(entries, library_id=library_id)
    session["active_library_id"] = library_id
    clear_pending_preset()
    clear_practice_session()
    flash(f"{library_name} 词库已重建：新增 {inserted} 个词。", "success")
    return redirect(url_for("index"))


@app.post("/presets/ecdict/copy")
def create_ecdict_preset_copy():
    """Build the preset into a new, separately named library so the user's
    existing edited copy is left untouched."""
    preset_key = request.form.get("preset_key", "").strip().lower()
    workspace_edit = request.form.get("workspace") == "1"
    base_name, entries = load_preset_entries(preset_key)
    if entries is None:
        clear_pending_preset()
        return redirect(url_for("libraries", edit=1, panel="presets") if workspace_edit else url_for("index"))

    library_name = unique_library_name(base_name)
    library_id = get_or_create_library(library_name)
    inserted, _updated, _skipped = import_entries(entries, library_id=library_id)
    session["active_library_id"] = library_id
    clear_pending_preset()
    clear_practice_session()
    flash(f"已创建独立副本“{library_name}”：新增 {inserted} 个词。", "success")
    return redirect(url_for("libraries") if workspace_edit else url_for("index"))


@app.post("/preview")
def create_preview():
    try:
        requested_count = int(request.form.get("study_count", "10"))
    except ValueError:
        requested_count = 10
    requested_count = max(1, min(requested_count, 200))
    prompt_mode = prompt_mode_from_form(allow_cloze=True)
    with_cloze = with_cloze_from_form(allow_cloze=True)

    rows = unit_repository.fetch_batch(
        get_db(), get_active_library_id(), STATUS_NEW, requested_count
    )
    ids = [int(row["id"]) for row in rows]
    if not ids:
        flash("当前没有可学习的新词，请先导入词汇或练习错词。", "error")
        return redirect(url_for("index"))

    session["practice_ids"] = ids
    session["practice_index"] = 0
    session["practice_mode"] = "normal"
    set_practice_options(prompt_mode)
    session["pending_cloze_ids"] = cloze_ids_from_ids(ids) if with_cloze else []
    session.pop("cloze_followup_active", None)
    session["retry_ids"] = []
    session["missed_ids"] = []
    session["practice_round"] = 1
    return redirect(url_for("preview"))


@app.route("/preview")
def preview():
    words = fetch_words_by_ids([int(word_id) for word_id in session.get("practice_ids", [])])
    if not words:
        flash("尚未选择练习内容。", "error")
        return redirect(url_for("index"))
    return render_template(
        "preview.html",
        words=words,
        session_words=words,
        mode=session.get("practice_mode", "normal"),
        workspace_mode={"normal": "home", "review": "learned", "wrong": "wrong"}.get(
            session.get("practice_mode", "normal"), "home"
        ),
        prompt_mode=session.get("prompt_mode", PROMPT_MIXED),
        cloze_scope=cloze_scope_from_session(),
        show_phonetic=bool(session.get("show_phonetic", True)),
        hide_global_stats=True,
        **base_context(),
    )


@app.post("/practice/start")
def start_practice():
    session["practice_index"] = 0
    session["awaiting_next"] = False
    session["last_result"] = None
    session["retry_ids"] = []
    session["missed_ids"] = []
    session["practice_round"] = 1
    return redirect(url_for("practice"))


@app.post("/review/start")
def start_due_review():
    due_count = review_due_count()
    if due_count <= 0:
        flash("当前没有到期需要复习的单词。", "error")
        return redirect_back()

    try:
        requested_count = int(request.form.get("review_count", str(due_count)))
    except ValueError:
        requested_count = due_count
    requested_count = max(1, min(requested_count, due_count, 200))
    prompt_mode = prompt_mode_from_form(allow_cloze=True)
    with_cloze = with_cloze_from_form(allow_cloze=True)

    rows = get_db().execute(
        """
        SELECT words.id, words.word, words.example_sentence
        FROM words
        JOIN libraries ON libraries.id = words.library_id
        WHERE words.library_id = ?
          AND words.status = ?
          AND words.review_correct_count < libraries.review_target_count
          AND words.next_review_at IS NOT NULL
          AND date(words.next_review_at) <= ?
        ORDER BY words.next_review_at ASC, words.review_correct_count ASC, words.id ASC
        LIMIT ?
        """,
        (
            get_active_library_id(),
            STATUS_LEARNED,
            today_iso(),
            requested_count,
        ),
    ).fetchall()
    ids = [int(row["id"]) for row in rows]
    if not ids:
        flash("当前没有到期需要复习的单词。", "error")
        return redirect_back()

    session["practice_ids"] = ids
    session["practice_index"] = 0
    session["practice_mode"] = "review"
    set_practice_options(prompt_mode)
    session["pending_cloze_ids"] = cloze_ids_from_ids(ids) if with_cloze else []
    session.pop("cloze_followup_active", None)
    session["retry_ids"] = []
    session["missed_ids"] = []
    session["practice_round"] = 1
    session["awaiting_next"] = False
    session["last_result"] = None
    return redirect(url_for("preview"))


@app.route("/practice")
def practice():
    ids = [int(word_id) for word_id in session.get("practice_ids", [])]
    index = int(session.get("practice_index", 0))
    mode = session.get("practice_mode", "normal")
    if not ids:
        flash("当前没有进行中的练习。", "error")
        return redirect(url_for("index"))
    if index >= len(ids):
        if mode in {"normal", "review"}:
            retry_ids = [int(word_id) for word_id in session.get("retry_ids", [])]
            if retry_ids:
                session["practice_ids"] = retry_ids
                session["practice_index"] = 0
                session["retry_ids"] = []
                session["awaiting_next"] = False
                session["last_result"] = None
                session["practice_round"] = int(session.get("practice_round", 1)) + 1
                ids = retry_ids
                index = 0
            else:
                if start_pending_cloze_round():
                    return redirect(url_for("practice"))
                return redirect(url_for("session_done"))
        else:
            return redirect(url_for("session_done"))

    stored_word = fetch_word(ids[index])
    if stored_word is None:
        session["practice_index"] = index + 1
        return redirect(url_for("practice"))
    word = practice_word_with_example(stored_word)
    # Prefer Wiktionary's exact POS-scoped glosses during practice. ECDICT's
    # definition field may contain several parts of speech in one value.
    if wiktionary_lookup_available():
        matching_definition = lookup_wiktionary_definition(
            str(word["word"]), str(word["part_of_speech"])
        )
        if matching_definition:
            word["definition"] = matching_definition

    next_word = fetch_word(ids[index + 1]) if index + 1 < len(ids) else None

    full_cloze_text = cloze_prompt(word["example_sentence"], word["word"])
    cloze_text = truncate_cloze_prompt(full_cloze_text) if full_cloze_text else ""
    prompt_mode = effective_prompt_mode(word)
    return render_template(
        "practice.html",
        session_words=fetch_words_by_ids(ids),
        workspace_mode={"normal": "home", "review": "learned", "wrong": "wrong"}.get(mode, "home"),
        word=word,
        next_audio_word=str(next_word["word"]) if next_word is not None else "",
        index=index,
        total=len(ids),
        result=session.get("last_result"),
        awaiting_next=bool(session.get("awaiting_next", False)),
        mode=mode,
        prompt_mode=prompt_mode,
        cloze_scope=cloze_scope_from_session(),
        cloze_followup_active=bool(session.get("cloze_followup_active", False)),
        show_definition=bool(session.get("show_definition", False)),
        show_phonetic=bool(session.get("show_phonetic", True)),
        cloze_text=cloze_text,
        cloze_truncated=bool(full_cloze_text and cloze_text != full_cloze_text),
        cloze_answer=cloze_answer(word["example_sentence"], word["word"]),
        cloze_feedback=session.get("cloze_feedback_context"),
        missed_count=len(session.get("missed_ids", [])),
        practice_round=int(session.get("practice_round", 1)),
        hide_global_stats=True,
        **base_context(),
    )


def stage_cloze_feedback(
    word: sqlite3.Row | dict[str, object],
    prompt_mode: str,
    is_correct: bool,
    result: dict[str, object],
) -> bool:
    """Hold a Cloze result long enough to collect optional material feedback."""
    sentence = str(word.get("example_sentence") or "") if isinstance(word, dict) else str(word["example_sentence"] or "")
    if prompt_mode != PROMPT_CLOZE or not sentence:
        session.pop("cloze_feedback_context", None)
        return False
    value = lambda key, default=None: word.get(key, default) if isinstance(word, dict) else word[key]
    session["cloze_feedback_context"] = {
        "token": secrets.token_urlsafe(18),
        "word_id": int(value("id")),
        "word": str(value("word")),
        "part_of_speech": str(value("part_of_speech")),
        "sentence": sentence,
        "sentence_hash": hashlib.sha256(sentence.encode("utf-8")).hexdigest(),
        "material_type": str(value("cloze_material_type", "example") or "example"),
        "material_source": str(value("example_source", "") or "") or None,
        "answer_correct": bool(is_correct),
        "practice_mode": str(session.get("practice_mode", "normal")),
        "submitted_rating": None,
    }
    session["awaiting_next"] = True
    session["last_result"] = result
    return True


@app.post("/practice/submit")
def submit_answer():
    ids = [int(word_id) for word_id in session.get("practice_ids", [])]
    index = int(session.get("practice_index", 0))
    if index >= len(ids):
        return redirect(url_for("session_done"))

    stored_word = fetch_word(ids[index])
    if stored_word is None:
        return redirect(url_for("practice"))
    word = practice_word_with_example(stored_word)

    answer = request.form.get("answer", "").strip()
    prompt_mode = effective_prompt_mode(word)
    is_correct = answer_matches(word, answer, prompt_mode)
    form_hint_feedback = cloze_form_hint_feedback(word, answer, prompt_mode) if is_correct else None
    db = get_db()
    db.execute(
        """
        UPDATE words
        SET total_attempts = total_attempts + 1,
            correct_attempts = correct_attempts + ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND library_id = ?
        """,
        (1 if is_correct else 0, word["id"], get_active_library_id()),
    )

    mode = session.get("practice_mode", "normal")
    if bool(session.get("cloze_followup_active", False)):
        db.commit()
        if is_correct:
            staged_result = form_hint_feedback or answer_feedback(word, answer, True)
            if stage_cloze_feedback(word, prompt_mode, True, staged_result):
                return redirect(url_for("practice"))
            if form_hint_feedback:
                session["awaiting_next"] = True
                session["last_result"] = form_hint_feedback
                return redirect(url_for("practice"))
            session["practice_index"] = index + 1
            session["awaiting_next"] = False
            session["last_result"] = None
            return redirect(url_for("practice"))

        retry_ids = [int(word_id) for word_id in session.get("retry_ids", [])]
        if int(word["id"]) not in retry_ids:
            retry_ids.append(int(word["id"]))
        session["retry_ids"] = retry_ids

        missed_ids = [int(word_id) for word_id in session.get("missed_ids", [])]
        if int(word["id"]) not in missed_ids:
            missed_ids.append(int(word["id"]))
        session["missed_ids"] = missed_ids

        staged_result = answer_feedback(word, answer, False)
        if not stage_cloze_feedback(word, prompt_mode, False, staged_result):
            session["awaiting_next"] = True
            session["last_result"] = staged_result
        return redirect(url_for("practice"))

    if mode == "wrong":
        if is_correct:
            new_count = int(word["wrong_correct_count"]) + 1
            if new_count >= wrong_review_target_count():
                db.execute(
                    """
                    UPDATE words
                    SET status = ?,
                        wrong_correct_count = 0,
                        wrong_next_review_at = NULL,
                        review_stage = 0,
                        next_review_at = COALESCE(next_review_at, ?),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND library_id = ?
                    """,
                    (STATUS_LEARNED, next_review_date(0), word["id"], get_active_library_id()),
                )
            else:
                db.execute(
                    """
                    UPDATE words
                    SET wrong_correct_count = ?,
                        wrong_next_review_at = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND library_id = ?
                    """,
                    (new_count, next_review_date(0), word["id"], get_active_library_id()),
                )
        else:
            db.execute(
                """
                UPDATE words
                SET wrong_correct_count = 0,
                    wrong_next_review_at = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND library_id = ?
                """,
                (next_review_date(0), word["id"], get_active_library_id()),
            )

    db.commit()

    if mode == "review":
        if is_correct:
            complete_review(int(word["id"]))
            db.commit()
            staged_result = form_hint_feedback or answer_feedback(word, answer, True)
            if stage_cloze_feedback(word, prompt_mode, True, staged_result):
                return redirect(url_for("practice"))
            if form_hint_feedback:
                session["awaiting_next"] = True
                session["last_result"] = form_hint_feedback
                return redirect(url_for("practice"))
            session["practice_index"] = index + 1
            session["awaiting_next"] = False
            session["last_result"] = None
            return redirect(url_for("practice"))

        retry_ids = [int(word_id) for word_id in session.get("retry_ids", [])]
        if int(word["id"]) not in retry_ids:
            retry_ids.append(int(word["id"]))
        session["retry_ids"] = retry_ids

        missed_ids = [int(word_id) for word_id in session.get("missed_ids", [])]
        if int(word["id"]) not in missed_ids:
            missed_ids.append(int(word["id"]))
        session["missed_ids"] = missed_ids

        staged_result = answer_feedback(word, answer, False)
        if not stage_cloze_feedback(word, prompt_mode, False, staged_result):
            session["awaiting_next"] = True
            session["last_result"] = staged_result
        return redirect(url_for("practice"))

    if mode == "normal":
        if is_correct:
            db.execute(
                """
                UPDATE words
                SET status = ?,
                    review_stage = 0,
                    next_review_at = COALESCE(next_review_at, ?),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND library_id = ?
                """,
                (STATUS_LEARNED, next_review_date(0), word["id"], get_active_library_id()),
            )
            db.commit()
            staged_result = form_hint_feedback or answer_feedback(word, answer, True)
            if stage_cloze_feedback(word, prompt_mode, True, staged_result):
                return redirect(url_for("practice"))
            if form_hint_feedback:
                session["awaiting_next"] = True
                session["last_result"] = form_hint_feedback
                return redirect(url_for("practice"))
            session["practice_index"] = index + 1
            session["awaiting_next"] = False
            session["last_result"] = None
            return redirect(url_for("practice"))

        retry_ids = [int(word_id) for word_id in session.get("retry_ids", [])]
        if int(word["id"]) not in retry_ids:
            retry_ids.append(int(word["id"]))
        session["retry_ids"] = retry_ids

        missed_ids = [int(word_id) for word_id in session.get("missed_ids", [])]
        if int(word["id"]) not in missed_ids:
            missed_ids.append(int(word["id"]))
        session["missed_ids"] = missed_ids

        staged_result = answer_feedback(word, answer, False)
        if not stage_cloze_feedback(word, prompt_mode, False, staged_result):
            session["awaiting_next"] = True
            session["last_result"] = staged_result
        return redirect(url_for("practice"))

    staged_result = form_hint_feedback or answer_feedback(word, answer, is_correct)
    if not stage_cloze_feedback(word, prompt_mode, is_correct, staged_result):
        session["awaiting_next"] = True
        session["last_result"] = staged_result
    return redirect(url_for("practice"))


@app.post("/practice/feedback")
def submit_cloze_feedback():
    context = session.get("cloze_feedback_context") or {}
    supplied_token = request.form.get("feedback_token", "")
    rating = request.form.get("rating", "")
    if (
        not session.get("awaiting_next")
        or not supplied_token
        or not secrets.compare_digest(supplied_token, str(context.get("token", "")))
        or rating not in feedback_repository.RATINGS
    ):
        abort(400)
    word = fetch_word(int(context["word_id"]))
    if word is None:
        abort(404)
    feedback_repository.save(
        get_db(),
        feedback_token=supplied_token,
        library_id=get_active_library_id(),
        user_id=current_user_id(),
        word_id=int(context["word_id"]),
        word=str(context["word"]),
        part_of_speech=str(context["part_of_speech"]),
        sentence=str(context["sentence"]),
        sentence_hash=str(context["sentence_hash"]),
        material_type=str(context["material_type"]),
        material_source=context.get("material_source"),
        rating=rating,
        answer_correct=bool(context["answer_correct"]),
        practice_mode=str(context["practice_mode"]),
    )
    context["submitted_rating"] = rating
    session["cloze_feedback_context"] = context
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify({"saved": True, "rating": rating})
    return redirect(url_for("practice"))


@app.post("/practice/next")
def next_word():
    action = request.form.get("action", "next")
    ids = [int(word_id) for word_id in session.get("practice_ids", [])]
    index = int(session.get("practice_index", 0))
    mode = session.get("practice_mode", "normal")

    if ids and index < len(ids):
        word_id = ids[index]
        result = session.get("last_result") or {}
        if not result.get("correct") and mode != "wrong":
            retry_ids = [int(item) for item in session.get("retry_ids", [])]
            if word_id not in retry_ids:
                retry_ids.append(word_id)
                session["retry_ids"] = retry_ids

            missed_ids = [int(item) for item in session.get("missed_ids", [])]
            if word_id not in missed_ids:
                missed_ids.append(word_id)
                session["missed_ids"] = missed_ids

    session["practice_index"] = index + 1
    session["awaiting_next"] = False
    session["last_result"] = None
    session.pop("cloze_feedback_context", None)
    return redirect(url_for("practice"))


@app.route("/session-done")
def session_done():
    mode = session.get("practice_mode", "normal")
    session_words = fetch_words_by_ids([int(word_id) for word_id in session.get("practice_ids", [])])
    missed_words = []
    if mode == "normal":
        missed_words = fetch_words_by_ids([int(word_id) for word_id in session.get("missed_ids", [])])

    if not missed_words or mode == "review":
        clear_practice_session()

    return render_template(
        "session_done.html",
        mode=mode,
        missed_words=missed_words,
        session_words=session_words,
        workspace_mode={"normal": "home", "review": "learned", "wrong": "wrong"}.get(mode, "home"),
        hide_global_stats=True,
        **base_context(),
    )


@app.post("/practice/finalize")
def finalize_practice():
    missed_ids = [int(word_id) for word_id in session.get("missed_ids", [])]
    selected_ids = {
        int(word_id)
        for word_id in request.form.getlist("wrong_ids")
        if word_id.isdigit()
    }

    if missed_ids:
        db = get_db()
        for word_id in missed_ids:
            if word_id in selected_ids:
                db.execute(
                    """
                    UPDATE words
                    SET status = ?,
                        wrong_correct_count = 0,
                        wrong_next_review_at = ?,
                        review_correct_count = 0,
                        review_stage = 0,
                        next_review_at = NULL,
                        last_reviewed_at = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND library_id = ?
                    """,
                    (STATUS_WRONG, next_review_date(0), word_id, get_active_library_id()),
                )
            else:
                db.execute(
                    """
                    UPDATE words
                    SET status = ?,
                        review_stage = 0,
                        next_review_at = COALESCE(next_review_at, ?),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND library_id = ?
                    """,
                    (STATUS_LEARNED, next_review_date(0), word_id, get_active_library_id()),
                )
        db.commit()

    clear_practice_session()
    if selected_ids:
        flash(f"已将 {len(selected_ids)} 个词加入错词。", "success")
        return redirect(url_for("wrong"))

    flash("练习结果已保存，没有单词被加入错词。", "success")
    return redirect(url_for("index"))


@app.route("/learned")
def learned():
    return render_workspace("learned")


@app.route("/wrong")
def wrong():
    return render_workspace("wrong")


@app.route("/libraries")
def libraries():
    return render_workspace("libraries")


@app.post("/words/<int:word_id>/edit")
def edit_word(word_id: int):
    existing_word = fetch_word(word_id)
    if existing_word is None:
        flash("没有找到该单词。", "error")
        return redirect(request.referrer or url_for("index"))

    word = request.form.get("word", "").strip()
    part_of_speech = normalize_user_pos(request.form.get("part_of_speech", "").strip())
    raw_meaning = request.form.get("meaning", "").strip()
    meaning = raw_meaning or existing_word["meaning"]
    example_sentence = request.form.get("example_sentence", "").strip()

    if not word or not part_of_speech or not meaning:
        flash("单词、词性和中文释义均为必填项。", "error")
        return redirect(request.referrer or url_for("index"))
    if example_sentence and not valid_example_sentence(example_sentence, word):
        flash("例句未保存：句子中没有包含目标词。", "error")
        return redirect(request.referrer or url_for("index", edit=1))

    entry = {"word": word, "part_of_speech": part_of_speech, "meaning": meaning}
    # Editing a meaning or personal example should be instant. Dictionary
    # enrichment is only relevant when the lexical identity actually changes.
    if (
        word.lower() != str(existing_word["word"]).lower()
        or part_of_speech != str(existing_word["part_of_speech"])
    ):
        enrich_entries_from_ecdict([entry])

    try:
        get_db().execute(
            """
            UPDATE words
            SET word = ?,
                part_of_speech = ?,
                meaning = ?,
                example_sentence = ?,
                example_translation = NULL,
                example_note = NULL,
                example_source = ?,
                phonetic = COALESCE(?, phonetic),
                definition = COALESCE(?, definition),
                frequency = COALESCE(?, frequency),
                source = COALESCE(?, source),
                source_tags = COALESCE(?, source_tags),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND library_id = ?
            """,
            (
                word,
                part_of_speech,
                meaning,
                example_sentence or None,
                "user" if example_sentence else None,
                entry.get("phonetic"),
                entry.get("definition"),
                entry.get("frequency"),
                entry.get("source"),
                entry.get("source_tags"),
                word_id,
                get_active_library_id(),
            ),
        )
        lexicon_repository.sync_learning_word(get_db(), word_id)
        example_repository.replace_user_example(get_db(), word_id, example_sentence or None)
        get_db().commit()
        flash("词条已更新。", "success")
    except sqlite3.IntegrityError:
        flash("更新失败：该单词与词性的组合已存在。", "error")

    return redirect(request.referrer or url_for("index"))


def pattern_form_values(word: sqlite3.Row) -> tuple[str, str | None, int | None, str | None, bool] | None:
    expression = re.sub(r"\s+", " ", request.form.get("expression", "")).strip()
    usage_label = request.form.get("usage_label", "").strip() or None
    if not expression:
        flash("请输入固定搭配。", "error")
        return None
    if len(expression) > 140 or not 2 <= english_word_count(expression) <= 12:
        flash("固定搭配应包含 2—12 个英文单词，且不超过 140 个字符。", "error")
        return None
    if not cloze_prompt(expression, str(word["word"])):
        flash("固定搭配必须包含当前单词或它的合法词形。", "error")
        return None
    if usage_label and len(usage_label) > 60:
        flash("用法标签不能超过 60 个字符。", "error")
        return None
    definition = None
    sense_rank = None
    raw_number = request.form.get("definition_number", "").strip()
    if raw_number:
        try:
            number = int(raw_number)
        except ValueError:
            flash("请选择有效的英文释义。", "error")
            return None
        records = lookup_wiktionary_definition_records(
            str(word["word"]), str(word["part_of_speech"]), limit=None
        )
        if number < 1 or number > len(records):
            flash("所选英文释义已经变化，请重新选择。", "error")
            return None
        record = records[number - 1]
        definition = str(record["raw_definition"])
        sense_rank = int(record["sense_rank"])
    enabled = request.form.get("enabled_for_cloze") == "on"
    return expression, definition, sense_rank, usage_label, enabled


@app.post("/words/<int:word_id>/patterns/add")
def add_word_pattern(word_id: int):
    word = fetch_word(word_id)
    if word is None:
        flash("没有找到该词条。", "error")
        return redirect(url_for("libraries", edit=1))
    values = pattern_form_values(word)
    if values is not None:
        try:
            pattern_repository.add_user_pattern(get_db(), word_id, *values)
            flash("固定搭配已添加。", "success")
        except sqlite3.IntegrityError:
            get_db().rollback()
            flash("这条固定搭配已经存在。", "error")
    return redirect(request.referrer or url_for("libraries", edit=1, word=word_id))


@app.post("/words/<int:word_id>/patterns/<int:pattern_id>/edit")
def edit_word_pattern(word_id: int, pattern_id: int):
    word = fetch_word(word_id)
    if word is None or pattern_repository.fetch_user_pattern(get_db(), pattern_id, word_id) is None:
        flash("没有找到该固定搭配。", "error")
        return redirect(url_for("libraries", edit=1))
    values = pattern_form_values(word)
    if values is not None:
        try:
            pattern_repository.update_user_pattern(get_db(), pattern_id, word_id, *values)
            flash("固定搭配已更新。", "success")
        except sqlite3.IntegrityError:
            get_db().rollback()
            flash("这条固定搭配已经存在。", "error")
    return redirect(request.referrer or url_for("libraries", edit=1, word=word_id))


@app.post("/words/<int:word_id>/patterns/<int:pattern_id>/delete")
def delete_word_pattern(word_id: int, pattern_id: int):
    word = fetch_word(word_id)
    if word is None or not pattern_repository.delete_user_pattern(
        get_db(), pattern_id, word_id
    ):
        flash("没有找到该固定搭配。", "error")
    else:
        flash("固定搭配已删除。", "success")
    return redirect(request.referrer or url_for("libraries", edit=1, word=word_id))


@app.post("/words/add")
def add_word():
    workspace_edit = request.form.get("workspace") == "1"
    try:
        workspace_unit = max(1, int(request.form.get("unit", "1")))
    except ValueError:
        workspace_unit = 1
    add_redirect = (
        url_for("libraries", edit=1, unit=workspace_unit, panel="add")
        if workspace_edit else url_for("index", edit=1)
    )
    words = request.form.getlist("word[]")
    parts = request.form.getlist("part_of_speech[]")
    meanings = request.form.getlist("meaning[]")
    examples = request.form.getlist("example_sentence[]")
    max_rows = max(len(words), len(parts), len(meanings), len(examples))
    entries = []
    errors = []
    ecdict_raw: bytes | None = None

    for index in range(max_rows):
        word = words[index].strip() if index < len(words) else ""
        raw_part = parts[index].strip() if index < len(parts) else ""
        part_of_speech = normalize_user_pos(raw_part) if raw_part else ""
        meaning = meanings[index].strip() if index < len(meanings) else ""
        example_sentence = examples[index].strip() if index < len(examples) else ""

        if not word and not part_of_speech and not meaning and not example_sentence:
            continue
        if not word:
            errors.append(f"第 {index + 1} 行：必须填写单词。")
            continue
        if workspace_edit and not raw_part:
            errors.append(f"第 {index + 1} 行：请选择词性后再自动补全。")
            continue
        if meaning and not part_of_speech:
            errors.append(f"第 {index + 1} 行：填写自定义释义时必须选择词性。")
            continue
        if example_sentence and not valid_example_sentence(example_sentence, word):
            errors.append(f"第 {index + 1} 行：例句必须包含目标词。")
            continue
        if workspace_edit:
            if not wiktionary_part_lookup_available():
                errors.append(f"第 {index + 1} 行：Wiktionary 数据不可用，暂时无法验证单词和词性。")
                continue
            if not wiktionary_part_exists(word, part_of_speech):
                errors.append(f"第 {index + 1} 行：Wiktionary 中没有找到“{word} / {part_of_speech}”。")
                continue
        row_entries: list[dict[str, object]] = []
        if part_of_speech and meaning:
            row_entries = [{"word": word, "part_of_speech": part_of_speech, "meaning": meaning}]
        else:
            row_entries = ecdict_entries_for_word(word, part_of_speech, meaning)
            if not row_entries and ecdict_raw is None:
                try:
                    ecdict_raw = load_ecdict_data()
                except Exception:
                    ecdict_raw = b""
            if not row_entries and ecdict_raw:
                row_entries = ecdict_entries_for_word(
                    word, part_of_speech, meaning, raw=ecdict_raw
                )
            if not row_entries:
                errors.append(
                    f"第 {index + 1} 行：没有找到“{word} / {part_of_speech}”的中文释义，请手动补充完整。"
                )
                continue
        for entry in row_entries:
            if example_sentence:
                entry["example_sentence"] = example_sentence
                entry["example_source"] = "user"
            entries.append(entry)

    if not entries:
        message = " ".join(errors[:3]) if errors else "请至少添加一个词条。"
        if workspace_edit:
            session["workspace_add_draft"] = {
                "word": words[0].strip() if words else "",
                "part_of_speech": parts[0].strip() if parts else "",
                "meaning": meanings[0].strip() if meanings else "",
                "example_sentence": examples[0].strip() if examples else "",
            }
            flash(message, "error")
        else:
            session["add_word_messages"] = [("error", message)]
        return redirect(add_redirect)

    db = get_db()
    existing_keys = {
        (str(row["word"]), str(row["part_of_speech"]))
        for row in db.execute(
            "SELECT word, part_of_speech FROM words WHERE library_id = ?",
            (get_active_library_id(),),
        ).fetchall()
    }
    enriched = enrich_entries_from_ecdict(entries)
    inserted, updated, skipped = import_entries(entries, update_existing=False)
    if workspace_edit and inserted:
        inserted_ids = [
            int(row["id"])
            for entry in entries
            if (str(entry["word"]), str(entry["part_of_speech"])) not in existing_keys
            for row in db.execute(
                """
                SELECT id FROM words
                WHERE library_id = ? AND word = ? AND part_of_speech = ?
                """,
                (get_active_library_id(), entry["word"], entry["part_of_speech"]),
            ).fetchall()
        ]
        unit_repository.place_words(
            db, get_active_library_id(), inserted_ids, workspace_unit
        )
        db.commit()
    suffix = f" ECDICT 已补充 {enriched} 个词条。" if enriched else ""
    messages = []
    if inserted:
        messages.append(("success", f"已添加 {inserted} 个新词。{suffix}"))
    if skipped:
        messages.append(("success", f"{skipped} 个词条已存在，已保持不变。"))
    if errors:
        messages.append(("error", f"以下内容未添加：{' '.join(errors[:3])}"))
    if not messages:
        messages.append(("error", "没有添加新词。"))
    if workspace_edit:
        session.pop("workspace_add_draft", None)
        for category, message in messages:
            flash(message, category)
    else:
        session["add_word_messages"] = messages
    return redirect(add_redirect)


@app.post("/words/save-page")
def save_page_edits():
    selected_ids = [int(word_id) for word_id in request.form.getlist("word_ids") if word_id.isdigit()]
    page = request.form.get("page", "1")
    search = request.form.get("q", "").strip()
    sort_mode = request.form.get("sort", SORT_FREQUENCY)
    if sort_mode not in LIBRARY_SORT_MODES:
        sort_mode = SORT_FREQUENCY

    edit_redirect_args = {"edit": 1, "page": page, "sort": sort_mode}
    if search:
        edit_redirect_args["q"] = search

    updates: list[dict[str, object]] = []
    errors: list[str] = []
    seen_keys: set[tuple[str, str]] = set()

    for word_id in selected_ids:
        existing_word = fetch_word(word_id)
        if existing_word is None:
            errors.append(f"Word {word_id}: word not found.")
            continue
        word = request.form.get(f"word_{word_id}", "").strip()
        part_of_speech = normalize_user_pos(request.form.get(f"part_of_speech_{word_id}", "").strip())
        raw_meaning = request.form.get(f"meaning_{word_id}", "").strip()
        meaning = raw_meaning or existing_word["meaning"]
        example_sentence = request.form.get(f"example_sentence_{word_id}", "").strip()

        if not word or not part_of_speech or not meaning:
            errors.append(f"Word {word_id}: word, part of speech, and meaning are required.")
            continue
        if example_sentence and not valid_example_sentence(example_sentence, word):
            errors.append(f"{word}: example sentence must contain the target word.")
            continue

        key = (word.lower(), part_of_speech)
        if key in seen_keys:
            errors.append(f"{word} / {part_of_speech}: duplicate on this page.")
            continue
        seen_keys.add(key)
        updates.append(
            {
                "id": word_id,
                "word": word,
                "part_of_speech": part_of_speech,
                "meaning": meaning,
                "example_sentence": example_sentence or None,
            }
        )

    if errors:
        flash(" ".join(errors[:3]), "error")
        return redirect(url_for("index", **edit_redirect_args))

    db = get_db()
    try:
        for update in updates:
            db.execute(
                """
                UPDATE words
                SET word = ?,
                    part_of_speech = ?,
                    meaning = ?,
                    example_sentence = ?,
                    example_translation = NULL,
                    example_note = NULL,
                    example_source = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND library_id = ?
                """,
                (
                    update["word"],
                    update["part_of_speech"],
                    update["meaning"],
                    update["example_sentence"],
                    "user" if update["example_sentence"] else None,
                    update["id"],
                    get_active_library_id(),
                ),
            )
            lexicon_repository.sync_learning_word(db, int(update["id"]))
            example_repository.replace_user_example(
                db, int(update["id"]), str(update["example_sentence"] or "") or None,
            )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        flash("保存失败：词库中存在重复的单词与词性组合。", "error")
        return redirect(url_for("index", **edit_redirect_args))

    flash(f"已保存 {len(updates)} 个词条。", "success")
    # "Save" keeps the user in edit mode on the same page/search/sort; the
    # separate "Done" link exits without saving.
    if request.form.get("stay") == "1":
        return redirect(url_for("index", **edit_redirect_args))
    return redirect(url_for("index"))


@app.post("/words/<int:word_id>/delete")
def delete_word(word_id: int):
    deleted = delete_word_ids({word_id}, get_active_library_id())
    if deleted:
        flash("词条已删除；本单元的其余单词保持原位。", "success")
    else:
        flash("当前词库中没有找到该词条。", "error")
    if request.form.get("next"):
        return redirect_back()
    return redirect(request.referrer or url_for("index"))


@app.post("/words/bulk-delete")
def bulk_delete_words():
    selected_ids = {int(word_id) for word_id in request.form.getlist("word_ids") if word_id.isdigit()}
    page = request.form.get("page", "1")
    search = request.form.get("q", "").strip()
    sort_mode = request.form.get("sort", SORT_FREQUENCY)
    if sort_mode not in LIBRARY_SORT_MODES:
        sort_mode = SORT_FREQUENCY
    workspace_edit = request.form.get("workspace") == "1"
    try:
        workspace_unit = max(1, int(request.form.get("unit", "1")))
    except ValueError:
        workspace_unit = 1
    redirect_args = {"edit": 1, "page": page, "sort": sort_mode}
    if search:
        redirect_args["q"] = search
    if not selected_ids:
        flash("请至少选择一个要删除的词条。", "error")
        return redirect(
            url_for("libraries", edit=1, unit=workspace_unit)
            if workspace_edit else url_for("index", **redirect_args)
        )

    deleted = delete_word_ids(selected_ids, get_active_library_id())
    flash(f"已删除 {deleted} 个词条；只有清空的单元会自动折叠。", "success")
    return redirect(
        url_for("libraries", edit=1, unit=workspace_unit)
        if workspace_edit else url_for("index", **redirect_args)
    )


@app.post("/libraries/exclude")
def exclude_library_words():
    workspace_edit = request.form.get("workspace") == "1"
    try:
        workspace_unit = max(1, int(request.form.get("unit", "1")))
    except ValueError:
        workspace_unit = 1
    dedupe_redirect = (
        url_for("libraries", edit=1, unit=workspace_unit, panel="dedupe")
        if workspace_edit else url_for("index", edit=1)
    )
    try:
        source_library_id = int(request.form.get("source_library_id", ""))
    except ValueError:
        flash("请选择要用于排除的词库。", "error")
        return redirect(dedupe_redirect)

    active_library_id = get_active_library_id()
    if source_library_id == active_library_id or not fetch_library(source_library_id):
        flash("请选择另一个已有词库。", "error")
        return redirect(dedupe_redirect)

    match_scope = request.form.get("match_scope", "word_part")
    db = get_db()
    if match_scope == "word":
        rows = db.execute(
            """
            SELECT target.id
            FROM words AS target
            WHERE target.library_id = ?
              AND EXISTS (
                  SELECT 1
                  FROM words AS source
                  WHERE source.library_id = ?
                    AND lower(source.word) = lower(target.word)
              )
            """,
            (active_library_id, source_library_id),
        ).fetchall()
    else:
        rows = db.execute(
            """
            SELECT target.id
            FROM words AS target
            WHERE target.library_id = ?
              AND EXISTS (
                  SELECT 1
                  FROM words AS source
                  WHERE source.library_id = ?
                    AND lower(source.word) = lower(target.word)
                    AND source.part_of_speech = target.part_of_speech
              )
            """,
            (active_library_id, source_library_id),
        ).fetchall()

    word_ids = {int(row["id"]) for row in rows}
    if not word_ids:
        flash("没有找到重合词条。", "success")
        return redirect(dedupe_redirect)

    deleted = delete_word_ids(word_ids, active_library_id)
    source_library = fetch_library(source_library_id)
    scope_label = "仅单词" if match_scope == "word" else "单词 + 词性"
    flash(f"已排除同时存在于 {source_library['name']} 的 {deleted} 个词条（{scope_label}）。", "success")
    return redirect(dedupe_redirect)


@app.post("/words/clear")
def clear_words():
    get_db().execute("DELETE FROM words WHERE library_id = ?", (get_active_library_id(),))
    get_db().commit()
    clear_practice_session()
    flash("全部词条与学习记录已清空。", "success")
    return redirect(url_for("index"))


@app.post("/wrong/start")
def start_wrong_review():
    due_count = wrong_due_count()
    if due_count <= 0:
        flash("今天没有到期的错词。", "error")
        return redirect(url_for("wrong"))

    try:
        requested_count = int(request.form.get("wrong_count", str(due_count)))
    except ValueError:
        requested_count = due_count
    requested_count = max(1, min(requested_count, due_count, 200))

    prompt_mode = prompt_mode_from_form(allow_cloze=True)
    with_cloze = with_cloze_from_form(allow_cloze=True)
    rows = get_db().execute(
        """
        SELECT id, word, example_sentence FROM words
        WHERE library_id = ?
          AND status = ?
          AND wrong_next_review_at IS NOT NULL
          AND date(wrong_next_review_at) <= ?
        ORDER BY wrong_next_review_at ASC, id ASC
        """,
        (get_active_library_id(), STATUS_WRONG, today_iso()),
    ).fetchall()
    ids = [int(row["id"]) for row in rows[:requested_count]]
    if not ids:
        flash("当前没有可练习的错词。", "error")
        return redirect(url_for("wrong"))
    session["practice_ids"] = ids
    session["practice_index"] = 0
    session["practice_mode"] = "wrong"
    set_practice_options(prompt_mode)
    session["pending_cloze_ids"] = cloze_ids_from_ids(ids) if with_cloze else []
    session.pop("cloze_followup_active", None)
    session["retry_ids"] = []
    session["missed_ids"] = []
    session["practice_round"] = 1
    session["awaiting_next"] = False
    session["last_result"] = None
    return redirect(url_for("preview"))


@app.post("/words/<int:word_id>/reset")
def reset_word(word_id: int):
    get_db().execute(
        """
        UPDATE words
        SET status = ?,
            wrong_correct_count = 0,
            wrong_next_review_at = NULL,
            review_correct_count = 0,
            review_stage = 0,
            next_review_at = NULL,
            last_reviewed_at = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND library_id = ?
        """,
        (STATUS_NEW, word_id, get_active_library_id()),
    )
    get_db().commit()
    return redirect(request.referrer or url_for("index"))


@app.post("/words/<int:word_id>/wrong")
def mark_wrong(word_id: int):
    get_db().execute(
        """
        UPDATE words
        SET status = ?,
            wrong_correct_count = 0,
            wrong_next_review_at = ?,
            review_correct_count = 0,
            review_stage = 0,
            next_review_at = NULL,
            last_reviewed_at = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND library_id = ?
        """,
        (STATUS_WRONG, next_review_date(0), word_id, get_active_library_id()),
    )
    get_db().commit()
    return redirect(request.referrer or url_for("index"))


if __name__ == "__main__":
    # Werkzeug's debugger allows arbitrary Python execution from the browser;
    # keep it opt-in and never enable it in releases.
    app.run(
        host="127.0.0.1",
        debug=os.environ.get("TYPENG_DEBUG") == "1",
        threaded=True,
    )
