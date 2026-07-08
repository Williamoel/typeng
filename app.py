from __future__ import annotations

import csv
import io
import json
import os
import random
import re
import secrets
import sqlite3
import sys
import threading
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone
from math import ceil
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for

try:
    from opencc import OpenCC
except ImportError:
    OpenCC = None


def resolve_bundle_dir() -> Path:
    """Directory that holds bundled read-only assets such as templates/ and static/."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent


def resolve_app_home() -> Path:
    """Directory for user-visible, writable app files such as data/ and resources/."""
    env_home = os.environ.get("TYPENG_HOME", "").strip()
    if env_home:
        return Path(env_home).resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resolve_resource_dir() -> Path:
    """Prefer external resources/ so users can drop large dictionary files beside the app."""
    external = APP_HOME / "resources"
    if external.exists():
        return external
    return APP_ROOT / "resources"


APP_ROOT = resolve_bundle_dir()
APP_HOME = resolve_app_home()
BASE_DIR = APP_ROOT
DATA_DIR = APP_HOME / "data"
RESOURCE_DIR = resolve_resource_dir()
DB_PATH = DATA_DIR / "typeng.db"
BUNDLED_ECDICT_PATH = RESOURCE_DIR / "ecdict.csv"
ECDICT_CACHE_PATH = DATA_DIR / "ecdict.csv"
ECDICT_SOURCE_URL = "https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv"
ECDICT_LOOKUP_SCHEMA_VERSION = 1
WORDNET_DIR = RESOURCE_DIR / "wordnet"
WORDNET_ZIP_PATH = WORDNET_DIR / "english-wordnet-2025-json.zip"
WORDNET_SCHEMA_VERSION = 1
WIKTIONARY_DIR = RESOURCE_DIR / "wiktionary"
WIKTIONARY_JSONL_CANDIDATES = [
    APP_HOME / "kaikki.org-dictionary-English.jsonl",
    BASE_DIR / "kaikki.org-dictionary-English.jsonl",
    WIKTIONARY_DIR / "kaikki.org-dictionary-English.jsonl",
]
WIKTIONARY_SCHEMA_VERSION = 5
TRADITIONAL_TO_SIMPLIFIED = str.maketrans(
    {
        "國": "国",
        "發": "发",
        "線": "线",
        "戲": "戏",
        "遊": "游",
        "讓": "让",
        "納": "纳",
        "稅": "税",
        "預": "预",
        "算": "算",
        "買": "买",
        "罐": "罐",
        "番": "番",
        "茄": "茄",
        "這": "这",
        "個": "个",
        "對": "对",
        "為": "为",
        "會": "会",
        "們": "们",
        "學": "学",
        "習": "习",
        "說": "说",
        "語": "语",
        "與": "与",
        "離": "离",
        "遠": "远",
        "還": "还",
        "沒": "没",
        "麼": "么",
        "樣": "样",
        "種": "种",
        "應": "应",
        "該": "该",
        "時": "时",
        "間": "间",
        "題": "题",
        "實": "实",
        "現": "现",
        "處": "处",
        "理": "理",
        "選": "选",
        "擇": "择",
        "體": "体",
        "驗": "验",
        "單": "单",
        "詞": "词",
        "書": "书",
        "電": "电",
        "腦": "脑",
        "網": "网",
        "頁": "页",
        "開": "开",
        "關": "关",
        "閉": "闭",
        "異": "异",
        "義": "义",
        "舊": "旧",
        "計": "计",
        "劃": "划",
        "標": "标",
        "籤": "签",
        "復": "复",
        "雜": "杂",
        "戰": "战",
        "輸": "输",
        "入": "入",
        "顯": "显",
        "隱": "隐",
        "藏": "藏",
        "測": "测",
        "試": "试",
        "錯": "错",
        "誤": "误",
        "確": "确",
        "認": "认",
        "聽": "听",
        "聖": "圣",
        "飯": "饭",
        "飲": "饮",
        "頭": "头",
        "風": "风",
        "飛": "飞",
        "馬": "马",
        "魚": "鱼",
        "鳥": "鸟",
        "愛": "爱",
        "帶": "带",
        "無": "无",
        "萬": "万",
        "長": "长",
        "門": "门",
        "問": "问",
        "聞": "闻",
        "陳": "陈",
        "隊": "队",
        "陽": "阳",
        "陰": "阴",
        "難": "难",
        "雖": "虽",
        "雙": "双",
        "邊": "边",
        "過": "过",
        "進": "进",
        "運": "运",
        "連": "连",
        "週": "周",
        "達": "达",
        "遲": "迟",
        "醫": "医",
        "錢": "钱",
        "銀": "银",
        "銷": "销",
        "錄": "录",
        "鐵": "铁",
        "車": "车",
        "輕": "轻",
        "轉": "转",
        "較": "较",
        "辦": "办",
        "農": "农",
        "讀": "读",
        "誰": "谁",
        "課": "课",
        "請": "请",
        "諾": "诺",
        "變": "变",
        "豐": "丰",
        "貝": "贝",
        "負": "负",
        "費": "费",
        "貿": "贸",
        "資": "资",
        "賽": "赛",
        "贏": "赢",
        "趕": "赶",
        "趨": "趋",
        "跡": "迹",
        "踐": "践",
        "身": "身",
        "軟": "软",
        "軍": "军",
        "員": "员",
        "圓": "圆",
        "園": "园",
        "圖": "图",
        "團": "团",
        "執": "执",
        "堅": "坚",
        "場": "场",
        "報": "报",
        "壓": "压",
        "壞": "坏",
        "聲": "声",
        "壹": "壹",
        "夠": "够",
        "夢": "梦",
        "夥": "伙",
        "獎": "奖",
        "奧": "奥",
        "婦": "妇",
        "嬰": "婴",
        "孫": "孙",
        "寶": "宝",
        "實": "实",
        "寧": "宁",
        "寬": "宽",
        "寫": "写",
        "尋": "寻",
        "將": "将",
        "專": "专",
        "導": "导",
        "層": "层",
        "屬": "属",
        "歲": "岁",
        "島": "岛",
        "嶺": "岭",
        "幣": "币",
        "幫": "帮",
        "幹": "干",
        "幾": "几",
        "庫": "库",
        "廠": "厂",
        "廣": "广",
        "廳": "厅",
        "張": "张",
        "強": "强",
        "彈": "弹",
        "彎": "弯",
        "彙": "汇",
        "後": "后",
        "徑": "径",
        "從": "从",
        "徠": "徕",
        "復": "复",
        "徵": "征",
        "德": "德",
        "憶": "忆",
        "懷": "怀",
        "態": "态",
        "慣": "惯",
        "慮": "虑",
        "慶": "庆",
        "憂": "忧",
        "懼": "惧",
        "懶": "懒",
        "戲": "戏",
        "戶": "户",
        "拋": "抛",
        "挾": "挟",
        "捨": "舍",
        "掃": "扫",
        "掙": "挣",
        "掛": "挂",
        "採": "采",
        "揚": "扬",
        "換": "换",
        "揮": "挥",
        "損": "损",
        "搖": "摇",
        "搶": "抢",
        "擁": "拥",
        "擇": "择",
        "擊": "击",
        "擔": "担",
        "據": "据",
        "擴": "扩",
        "擺": "摆",
        "攝": "摄",
        "攜": "携",
        "敵": "敌",
        "數": "数",
        "斷": "断",
        "於": "于",
        "暫": "暂",
        "曆": "历",
        "曉": "晓",
        "暢": "畅",
        "機": "机",
        "條": "条",
        "來": "来",
        "東": "东",
        "極": "极",
        "構": "构",
        "標": "标",
        "樣": "样",
        "樓": "楼",
        "樂": "乐",
        "樹": "树",
        "橋": "桥",
        "檢": "检",
        "權": "权",
        "歡": "欢",
        "歐": "欧",
        "歲": "岁",
        "歷": "历",
        "歸": "归",
        "殘": "残",
        "殺": "杀",
        "殼": "壳",
        "氣": "气",
        "漢": "汉",
        "湯": "汤",
        "溫": "温",
        "滅": "灭",
        "滾": "滚",
        "滿": "满",
        "漁": "渔",
        "漢": "汉",
        "潔": "洁",
        "潛": "潜",
        "潤": "润",
        "澤": "泽",
        "濃": "浓",
        "濟": "济",
        "濤": "涛",
        "濫": "滥",
        "灣": "湾",
        "燈": "灯",
        "靈": "灵",
        "爐": "炉",
        "爭": "争",
        "爺": "爷",
        "牆": "墙",
        "牽": "牵",
        "狀": "状",
        "獨": "独",
        "獲": "获",
        "環": "环",
        "現": "现",
        "產": "产",
        "畢": "毕",
        "畫": "画",
        "當": "当",
        "疇": "畴",
        "療": "疗",
        "癡": "痴",
        "盜": "盗",
        "盡": "尽",
        "監": "监",
        "盤": "盘",
        "著": "着",
        "眾": "众",
        "睜": "睁",
        "矯": "矫",
        "礎": "础",
        "禮": "礼",
        "禱": "祷",
        "離": "离",
        "種": "种",
        "積": "积",
        "穩": "稳",
        "窮": "穷",
        "竅": "窍",
        "筆": "笔",
        "節": "节",
        "範": "范",
        "簡": "简",
        "籃": "篮",
        "糧": "粮",
        "糾": "纠",
        "紀": "纪",
        "約": "约",
        "紅": "红",
        "紋": "纹",
        "納": "纳",
        "紐": "纽",
        "純": "纯",
        "紙": "纸",
        "級": "级",
        "細": "细",
        "終": "终",
        "組": "组",
        "結": "结",
        "絕": "绝",
        "統": "统",
        "絲": "丝",
        "經": "经",
        "綠": "绿",
        "維": "维",
        "網": "网",
        "緊": "紧",
        "線": "线",
        "練": "练",
        "縣": "县",
        "總": "总",
        "績": "绩",
        "織": "织",
        "繼": "继",
        "續": "续",
        "缺": "缺",
        "罷": "罢",
        "羅": "罗",
        "罰": "罚",
        "聰": "聪",
        "聯": "联",
        "職": "职",
        "聽": "听",
        "肅": "肃",
        "脫": "脱",
        "腎": "肾",
        "腳": "脚",
        "腦": "脑",
        "臉": "脸",
        "臟": "脏",
        "舉": "举",
        "舊": "旧",
        "艱": "艰",
        "藝": "艺",
        "蘇": "苏",
        "處": "处",
        "虛": "虚",
        "號": "号",
        "蟲": "虫",
        "衛": "卫",
        "衝": "冲",
        "製": "制",
        "複": "复",
        "褲": "裤",
        "親": "亲",
        "覺": "觉",
        "觀": "观",
        "規": "规",
        "視": "视",
        "覽": "览",
        "觸": "触",
        "訂": "订",
        "訓": "训",
        "記": "记",
        "註": "注",
        "詩": "诗",
        "試": "试",
        "話": "话",
        "該": "该",
        "詳": "详",
        "誇": "夸",
        "誌": "志",
        "語": "语",
        "誠": "诚",
        "誤": "误",
        "說": "说",
        "讀": "读",
        "變": "变",
        "讓": "让",
        "讚": "赞",
        "館": "馆",
        "嗎": "吗",
        "猶": "犹",
    }
)

STATUS_NEW = "new"
STATUS_LEARNED = "learned"
STATUS_WRONG = "wrong"

PROMPT_CHINESE = "chinese"
PROMPT_AUDIO = "audio"
PROMPT_MIXED = "mixed"
PROMPT_CLOZE = "cloze"
PROMPT_MODES = {PROMPT_CHINESE, PROMPT_AUDIO, PROMPT_MIXED, PROMPT_CLOZE}
CLOZE_SCOPE_WITH = "with"
CLOZE_SCOPE_ONLY = "only"
CLOZE_SCOPES = {CLOZE_SCOPE_WITH, CLOZE_SCOPE_ONLY}
LIBRARY_PAGE_SIZE = 100
DEFAULT_REVIEW_TARGET_COUNT = 3
MIN_REVIEW_TARGET_COUNT = 3
MAX_REVIEW_TARGET_COUNT = 10
DEFAULT_WRONG_REVIEW_TARGET_COUNT = 3
MIN_WRONG_REVIEW_TARGET_COUNT = 3
MAX_WRONG_REVIEW_TARGET_COUNT = 10
REVIEW_INTERVAL_DAYS = [1, 2, 4, 7, 15, 30, 60, 120, 180, 365]
SORT_FREQUENCY = "frequency"
SORT_ALPHA = "alpha"
LIBRARY_SORT_MODES = {SORT_FREQUENCY, SORT_ALPHA}
CLOZE_IRREGULAR_FORMS = {
    "be": {"am", "is", "are", "was", "were", "been", "being"},
    "go": {"goes", "went", "gone", "going"},
    "do": {"does", "did", "done", "doing"},
    "have": {"has", "had", "having"},
    "make": {"makes", "made", "making"},
    "take": {"takes", "took", "taken", "taking"},
    "get": {"gets", "got", "gotten", "getting"},
    "give": {"gives", "gave", "given", "giving"},
    "write": {"writes", "wrote", "written", "writing"},
    "speak": {"speaks", "spoke", "spoken", "speaking"},
    "see": {"sees", "saw", "seen", "seeing"},
    "come": {"comes", "came", "coming"},
    "run": {"runs", "ran", "running"},
    "begin": {"begins", "began", "begun", "beginning"},
}
PART_OF_SPEECH_OPTIONS = [
    ("n", "n. noun"),
    ("v", "v. verb"),
    ("adj", "adj. adjective"),
    ("adv", "adv. adverb"),
    ("pron", "pron. pronoun"),
    ("prep", "prep. preposition"),
    ("conj", "conj. conjunction"),
    ("interj", "interj. interjection"),
    ("abbr", "abbr. abbreviation"),
    ("num", "num. numeral"),
    ("aux", "aux. auxiliary"),
    ("pref", "pref. prefix"),
    ("suf", "suf. suffix"),
    ("phrase", "phrase"),
]
ECDICT_PRESET_LIBRARIES = {
    "zk": {"name": "中考", "tags": {"zk"}},
    "gk": {"name": "高考", "tags": {"gk"}},
    "cet4": {"name": "CET4", "tags": {"cet4"}},
    "cet6": {"name": "CET6", "tags": {"cet6"}},
    "kaoyan": {"name": "考研", "tags": {"ky", "kaoyan"}},
    "ielts": {"name": "IELTS", "tags": {"ielts"}},
    "toefl": {"name": "TOEFL", "tags": {"toefl"}},
    "gre": {"name": "GRE", "tags": {"gre"}},
}
ECDICT_POS_MAP = {
    "n": "n",
    "noun": "n",
    "pl": "n",
    "plural": "n",
    "v": "v",
    "vi": "v",
    "vt": "v",
    "verb": "v",
    "a": "adj",
    "adj": "adj",
    "adjective": "adj",
    "s": "adj",
    "ad": "adv",
    "adv": "adv",
    "adverb": "adv",
    "pron": "pron",
    "pronoun": "pron",
    "prep": "prep",
    "preposition": "prep",
    "conj": "conj",
    "conjunction": "conj",
    "int": "interj",
    "interj": "interj",
    "interjection": "interj",
    "abbr": "abbr",
    "num": "num",
    "aux": "aux",
    "pref": "pref",
    "prefix": "pref",
    "suf": "suf",
    "suff": "suf",
    "suffix": "suf",
    "phr": "phrase",
    "phrase": "phrase",
}
ECDICT_POS_PREFIX_RE = re.compile(r"^\s*([A-Za-z][A-Za-z-]*)\.\s*(.*)$")
ECDICT_DEFINITION_SPLIT_RE = re.compile(r"\s+(?=(?:n|v|s|a|r|adj|adv)\.\s)")
ECDICT_DEFINITION_POS_RE = re.compile(
    r"^\s*(n|v|a|s|r|adj|adv|noun|verb|adjective|adverb)\.?\s+",
    re.IGNORECASE,
)
BLOCKED_EXAMPLE_WORDS = {
    "shit",
    "bullshit",
    "fuck",
    "fucking",
    "fucker",
    "motherfucker",
    "bitch",
    "bastard",
    "asshole",
    "damn",
}


app = Flask(
    __name__,
    template_folder=str(APP_ROOT / "templates"),
    static_folder=str(APP_ROOT / "static"),
)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
OPENCC_T2S = OpenCC("t2s") if OpenCC is not None else None
DB_INITIALIZED = False
DB_INIT_LOCK = threading.Lock()


def load_secret_key() -> str:
    """Persist a per-installation random secret key under data/."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / "secret_key"
    try:
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value
    except OSError:
        pass
    value = secrets.token_hex(32)
    try:
        path.write_text(value, encoding="utf-8")
    except OSError:
        pass
    return value


app.config["SECRET_KEY"] = os.environ.get("TYPENG_SECRET_KEY") or load_secret_key()


def is_local_host(host_or_origin: str | None) -> bool:
    value = (host_or_origin or "").strip()
    if not value:
        return False
    if "://" not in value:
        value = f"http://{value}"
    try:
        hostname = urlsplit(value).hostname or ""
    except ValueError:
        return False
    return hostname.lower() in {"127.0.0.1", "localhost", "::1"}


def is_local_origin(origin: str | None) -> bool:
    if not origin or origin == "null":
        return False
    return is_local_host(origin)


@app.before_request
def protect_local_app() -> None:
    if not is_local_host(request.host):
        abort(403)
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("Origin")
        if origin and not is_local_origin(origin):
            abort(403)


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        DATA_DIR.mkdir(exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_: object) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


DEFINITION_DISPLAY_POS_RE = re.compile(
    r"\s*[;；]\s*(?=(?:n|v|adj|adv|pron|prep|conj|interj|abbr|num|aux|phrase)\.\s)",
    re.IGNORECASE,
)


def display_pos_label(part_of_speech: str | None) -> str:
    part = normalize_part_group(str(part_of_speech or ""))
    return {
        "n": "n.",
        "v": "v.",
        "adj": "adj.",
        "adv": "adv.",
        "pron": "pron.",
        "prep": "prep.",
        "conj": "conj.",
        "interj": "interj.",
        "abbr": "abbr.",
        "num": "num.",
        "aux": "aux.",
        "pref": "pref.",
        "suf": "suf.",
        "phrase": "phrase.",
    }.get(part, f"{part}.") if part else ""


@app.template_filter("definition_lines")
def definition_lines(value: str | None, part_of_speech: str | None = None) -> str:
    lines: list[str] = []
    for raw_line in (value or "").replace("\\n", "\n").splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        parts = [part.strip() for part in DEFINITION_DISPLAY_POS_RE.split(line) if part.strip()]
        lines.extend(parts or [line])
    label = display_pos_label(part_of_speech)
    if label:
        prefixed: list[str] = []
        for line in lines:
            if re.match(r"^(?:n|v|adj|adv|pron|prep|conj|interj|abbr|num|aux|pref|suf|phrase)\.\s", line, re.IGNORECASE):
                prefixed.append(line)
            else:
                prefixed.append(f"{label} {line}")
        lines = prefixed
    return "\n".join(lines)


def table_columns(db: sqlite3.Connection, table_name: str) -> set[str]:
    return {row["name"] for row in db.execute(f"PRAGMA table_info({table_name})").fetchall()}


def normalize_user_pos(raw_pos: str) -> str:
    normalized = normalize_ecdict_pos(raw_pos)
    return "v" if normalized in {"vi", "vt", "verb"} else normalized


def merge_text_values(*values: str | None) -> str | None:
    seen: set[str] = set()
    merged: list[str] = []
    for value in values:
        for part in re.split(r"[；;\n]+", value or ""):
            cleaned = part.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                merged.append(cleaned)
    return "；".join(merged) if merged else None


def merge_verb_part_duplicates(db: sqlite3.Connection) -> None:
    rows = db.execute(
        """
        SELECT *
        FROM words
        WHERE part_of_speech IN ('vi', 'vt', 'verb', 'v')
        ORDER BY library_id ASC, lower(word) ASC, id ASC
        """
    ).fetchall()
    groups: dict[tuple[int, str], list[sqlite3.Row]] = {}
    for row in rows:
        groups.setdefault((int(row["library_id"]), str(row["word"]).lower()), []).append(row)

    status_rank = {STATUS_NEW: 0, STATUS_LEARNED: 1, STATUS_WRONG: 2}
    for (library_id, _word_key), group in groups.items():
        if not group:
            continue
        target = next((row for row in group if row["part_of_speech"] == "v"), group[0])
        duplicate_rows = [row for row in group if int(row["id"]) != int(target["id"])]
        if not duplicate_rows and target["part_of_speech"] == "v":
            continue

        all_rows = [target, *duplicate_rows]
        best_status = max((row["status"] for row in all_rows), key=lambda status: status_rank.get(status, 0))
        meaning = merge_text_values(*(row["meaning"] for row in all_rows)) or target["meaning"]
        definition = merge_text_values(*(row["definition"] for row in all_rows))
        source_tags = merge_text_values(*(row["source_tags"] for row in all_rows))
        example_row = next((row for row in all_rows if row["example_sentence"]), target)
        phonetic_row = next((row for row in all_rows if row["phonetic"]), target)
        source_row = next((row for row in all_rows if row["source"]), target)
        frequency_values = [int(row["frequency"]) for row in all_rows if row["frequency"] is not None]
        frequency = min(frequency_values) if frequency_values else None
        wrong_correct_count = max(int(row["wrong_correct_count"]) for row in all_rows)
        review_correct_count = max(int(row["review_correct_count"]) for row in all_rows)
        review_stage = max(int(row["review_stage"]) for row in all_rows)
        total_attempts = sum(int(row["total_attempts"]) for row in all_rows)
        correct_attempts = sum(int(row["correct_attempts"]) for row in all_rows)
        wrong_next_review_at = min((row["wrong_next_review_at"] for row in all_rows if row["wrong_next_review_at"]), default=None)
        next_review_at = min((row["next_review_at"] for row in all_rows if row["next_review_at"]), default=None)
        last_reviewed_at = max((row["last_reviewed_at"] for row in all_rows if row["last_reviewed_at"]), default=None)

        try:
            db.execute(
                """
                UPDATE words
                SET part_of_speech = ?,
                    meaning = ?,
                    example_sentence = ?,
                    example_translation = ?,
                    phonetic = ?,
                    definition = ?,
                    frequency = ?,
                    source = ?,
                    source_tags = ?,
                    status = ?,
                    wrong_correct_count = ?,
                    wrong_next_review_at = ?,
                    review_correct_count = ?,
                    review_stage = ?,
                    next_review_at = ?,
                    last_reviewed_at = ?,
                    total_attempts = ?,
                    correct_attempts = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND library_id = ?
                """,
                (
                    "v",
                    meaning,
                    example_row["example_sentence"],
                    example_row["example_translation"],
                    phonetic_row["phonetic"],
                    definition,
                    frequency,
                    source_row["source"],
                    source_tags,
                    best_status,
                    wrong_correct_count,
                    wrong_next_review_at,
                    review_correct_count,
                    review_stage,
                    next_review_at,
                    last_reviewed_at,
                    total_attempts,
                    correct_attempts,
                    target["id"],
                    library_id,
                ),
            )
        except sqlite3.IntegrityError:
            existing = db.execute(
                """
                SELECT *
                FROM words
                WHERE library_id = ? AND lower(word) = lower(?) AND part_of_speech = 'v'
                """,
                (library_id, target["word"]),
            ).fetchone()
            if existing and int(existing["id"]) != int(target["id"]):
                duplicate_rows.append(target)
                target = existing
                db.execute(
                    """
                    UPDATE words
                    SET meaning = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND library_id = ?
                    """,
                    (merge_text_values(existing["meaning"], meaning) or meaning, existing["id"], library_id),
                )

        duplicate_ids = [int(row["id"]) for row in duplicate_rows]
        if duplicate_ids:
            placeholders = ",".join("?" for _ in duplicate_ids)
            db.execute(
                f"""
                DELETE FROM words
                WHERE library_id = ? AND id IN ({placeholders})
                """,
                [library_id, *duplicate_ids],
            )


def migrate_plural_phrase_entries(db: sqlite3.Connection) -> None:
    rows = db.execute(
        """
        SELECT *
        FROM words
        WHERE part_of_speech = 'phrase'
          AND lower(trim(meaning)) LIKE 'pl.%'
        ORDER BY library_id ASC, lower(word) ASC, id ASC
        """
    ).fetchall()
    for row in rows:
        existing = db.execute(
            """
            SELECT *
            FROM words
            WHERE library_id = ?
              AND lower(word) = lower(?)
              AND part_of_speech = 'n'
              AND id != ?
            """,
            (row["library_id"], row["word"], row["id"]),
        ).fetchone()
        if existing:
            merged_meaning = merge_text_values(existing["meaning"], row["meaning"]) or existing["meaning"]
            db.execute(
                """
                UPDATE words
                SET meaning = ?,
                    example_sentence = COALESCE(example_sentence, ?),
                    example_translation = COALESCE(example_translation, ?),
                    phonetic = COALESCE(phonetic, ?),
                    definition = COALESCE(definition, ?),
                    frequency = COALESCE(frequency, ?),
                    source = COALESCE(source, ?),
                    source_tags = COALESCE(source_tags, ?),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND library_id = ?
                """,
                (
                    merged_meaning,
                    row["example_sentence"],
                    row["example_translation"],
                    row["phonetic"],
                    row["definition"],
                    row["frequency"],
                    row["source"],
                    row["source_tags"],
                    existing["id"],
                    existing["library_id"],
                ),
            )
            db.execute("DELETE FROM words WHERE id = ? AND library_id = ?", (row["id"], row["library_id"]))
        else:
            db.execute(
                """
                UPDATE words
                SET part_of_speech = 'n',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND library_id = ?
                """,
                (row["id"], row["library_id"]),
            )


def update_word_part_preserving_duplicate(db: sqlite3.Connection, row: sqlite3.Row, target_part: str) -> None:
    existing = db.execute(
        """
        SELECT *
        FROM words
        WHERE library_id = ?
          AND lower(word) = lower(?)
          AND part_of_speech = ?
          AND id != ?
        """,
        (row["library_id"], row["word"], target_part, row["id"]),
    ).fetchone()
    if existing:
        merged_meaning = merge_text_values(existing["meaning"], row["meaning"]) or existing["meaning"]
        db.execute(
            """
            UPDATE words
            SET meaning = ?,
                example_sentence = COALESCE(example_sentence, ?),
                example_translation = COALESCE(example_translation, ?),
                phonetic = COALESCE(phonetic, ?),
                definition = COALESCE(definition, ?),
                frequency = COALESCE(frequency, ?),
                source = COALESCE(source, ?),
                source_tags = COALESCE(source_tags, ?),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND library_id = ?
            """,
            (
                merged_meaning,
                row["example_sentence"],
                row["example_translation"],
                row["phonetic"],
                row["definition"],
                row["frequency"],
                row["source"],
                row["source_tags"],
                existing["id"],
                existing["library_id"],
            ),
        )
        db.execute("DELETE FROM words WHERE id = ? AND library_id = ?", (row["id"], row["library_id"]))
    else:
        db.execute(
            """
            UPDATE words
            SET part_of_speech = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND library_id = ?
            """,
            (target_part, row["id"], row["library_id"]),
        )


def migrate_inferred_phrase_entries(db: sqlite3.Connection) -> None:
    rows = db.execute(
        """
        SELECT *
        FROM words
        WHERE part_of_speech = 'phrase'
          AND instr(trim(word), ' ') = 0
        ORDER BY library_id ASC, lower(word) ASC, id ASC
        """
    ).fetchall()
    for row in rows:
        inferred = infer_pos_from_ecdict_definition(row["definition"] or "")
        if not inferred:
            inferred = infer_pos_from_word_shape(row["word"] or "", row["meaning"] or "")
        if inferred and inferred != "phrase":
            update_word_part_preserving_duplicate(db, row, inferred)


def migrate_db(db: sqlite3.Connection) -> None:
    db.execute(
        """
        INSERT OR IGNORE INTO libraries (id, name)
        VALUES (1, 'Default Library')
        """
    )

    library_columns = table_columns(db, "libraries")
    if "review_target_count" not in library_columns:
        db.execute(
            f"ALTER TABLE libraries ADD COLUMN review_target_count INTEGER NOT NULL DEFAULT {DEFAULT_REVIEW_TARGET_COUNT}"
        )
    if "wrong_review_target_count" not in library_columns:
        db.execute(
            f"ALTER TABLE libraries ADD COLUMN wrong_review_target_count INTEGER NOT NULL DEFAULT {DEFAULT_WRONG_REVIEW_TARGET_COUNT}"
        )

    columns = table_columns(db, "words")
    if "library_id" not in columns:
        db.execute("ALTER TABLE words RENAME TO words_legacy")
        db.execute(
            """
            CREATE TABLE words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                library_id INTEGER NOT NULL DEFAULT 1,
                word TEXT NOT NULL,
                part_of_speech TEXT NOT NULL,
                meaning TEXT NOT NULL,
                example_sentence TEXT,
                example_translation TEXT,
                phonetic TEXT,
                definition TEXT,
                frequency INTEGER,
                source TEXT,
                source_tags TEXT,
                status TEXT NOT NULL DEFAULT 'new',
                wrong_correct_count INTEGER NOT NULL DEFAULT 0,
                wrong_next_review_at TEXT,
                review_correct_count INTEGER NOT NULL DEFAULT 0,
                review_stage INTEGER NOT NULL DEFAULT 0,
                next_review_at TEXT,
                last_reviewed_at TEXT,
                total_attempts INTEGER NOT NULL DEFAULT 0,
                correct_attempts INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(library_id, word, part_of_speech),
                FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE CASCADE
            )
            """
        )
        db.execute(
            """
            INSERT INTO words (
                id, library_id, word, part_of_speech, meaning, status,
                wrong_correct_count, total_attempts, correct_attempts,
                created_at, updated_at
            )
            SELECT
                id, 1, word, part_of_speech, meaning, status,
                wrong_correct_count, total_attempts, correct_attempts,
                created_at, updated_at
            FROM words_legacy
            """
        )
        db.execute("DROP TABLE words_legacy")
        columns = table_columns(db, "words")

    for column_name, column_sql in {
        "phonetic": "ALTER TABLE words ADD COLUMN phonetic TEXT",
        "example_sentence": "ALTER TABLE words ADD COLUMN example_sentence TEXT",
        "example_translation": "ALTER TABLE words ADD COLUMN example_translation TEXT",
        "definition": "ALTER TABLE words ADD COLUMN definition TEXT",
        "frequency": "ALTER TABLE words ADD COLUMN frequency INTEGER",
        "source": "ALTER TABLE words ADD COLUMN source TEXT",
        "source_tags": "ALTER TABLE words ADD COLUMN source_tags TEXT",
        "wrong_next_review_at": "ALTER TABLE words ADD COLUMN wrong_next_review_at TEXT",
        "review_correct_count": "ALTER TABLE words ADD COLUMN review_correct_count INTEGER NOT NULL DEFAULT 0",
        "review_stage": "ALTER TABLE words ADD COLUMN review_stage INTEGER NOT NULL DEFAULT 0",
        "next_review_at": "ALTER TABLE words ADD COLUMN next_review_at TEXT",
        "last_reviewed_at": "ALTER TABLE words ADD COLUMN last_reviewed_at TEXT",
    }.items():
        if column_name not in columns:
            db.execute(column_sql)

    db.execute(
        """
        UPDATE words
        SET next_review_at = ?
        WHERE status = ?
          AND next_review_at IS NULL
          AND review_correct_count = 0
        """,
        (next_review_date(0), STATUS_LEARNED),
    )
    db.execute(
        """
        UPDATE words
        SET wrong_next_review_at = ?
        WHERE status = ?
          AND wrong_next_review_at IS NULL
        """,
        (next_review_date(0), STATUS_WRONG),
    )
    clear_invalid_example_sentences(db)
    simplify_existing_example_translations(db)
    merge_verb_part_duplicates(db)
    migrate_plural_phrase_entries(db)
    migrate_inferred_phrase_entries(db)


def ensure_metadata_table(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )


def init_db() -> None:
    db = get_db()
    ensure_metadata_table(db)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS libraries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            review_target_count INTEGER NOT NULL DEFAULT 3,
            wrong_review_target_count INTEGER NOT NULL DEFAULT 3,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            library_id INTEGER NOT NULL DEFAULT 1,
            word TEXT NOT NULL,
            part_of_speech TEXT NOT NULL,
            meaning TEXT NOT NULL,
            example_sentence TEXT,
            example_translation TEXT,
            phonetic TEXT,
            definition TEXT,
            frequency INTEGER,
            source TEXT,
            source_tags TEXT,
            status TEXT NOT NULL DEFAULT 'new',
            wrong_correct_count INTEGER NOT NULL DEFAULT 0,
            wrong_next_review_at TEXT,
            review_correct_count INTEGER NOT NULL DEFAULT 0,
            review_stage INTEGER NOT NULL DEFAULT 0,
            next_review_at TEXT,
            last_reviewed_at TEXT,
            total_attempts INTEGER NOT NULL DEFAULT 0,
            correct_attempts INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(library_id, word, part_of_speech),
            FOREIGN KEY(library_id) REFERENCES libraries(id) ON DELETE CASCADE
        )
        """
    )
    migrate_db(db)
    db.commit()


@app.before_request
def ensure_db() -> None:
    # init_db() runs schema migrations plus several full-table cleanup scans.
    # Running it on every request makes large libraries increasingly slow, so
    # run it once per process instead.
    global DB_INITIALIZED
    if DB_INITIALIZED:
        return
    with DB_INIT_LOCK:
        if not DB_INITIALIZED:
            init_db()
            DB_INITIALIZED = True


def count_words(status: str | None = None) -> int:
    db = get_db()
    library_id = get_active_library_id()
    if status is None:
        row = db.execute("SELECT COUNT(*) AS count FROM words WHERE library_id = ?", (library_id,)).fetchone()
    else:
        row = db.execute(
            "SELECT COUNT(*) AS count FROM words WHERE library_id = ? AND status = ?",
            (library_id, status),
        ).fetchone()
    return int(row["count"])


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0).isoformat(sep=" ")


def today_iso() -> str:
    return datetime.now().date().isoformat()


def review_due_count() -> int:
    row = get_db().execute(
        """
        SELECT COUNT(*) AS count
        FROM words
        JOIN libraries ON libraries.id = words.library_id
        WHERE words.library_id = ?
          AND words.status = ?
          AND words.review_correct_count < libraries.review_target_count
          AND words.next_review_at IS NOT NULL
          AND date(words.next_review_at) <= ?
        """,
        (get_active_library_id(), STATUS_LEARNED, today_iso()),
    ).fetchone()
    return int(row["count"])


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
    row = get_db().execute(
        """
        SELECT COUNT(*) AS count
        FROM words
        WHERE library_id = ?
          AND status = ?
          AND wrong_next_review_at IS NOT NULL
          AND date(wrong_next_review_at) <= ?
        """,
        (get_active_library_id(), STATUS_WRONG, today_iso()),
    ).fetchone()
    return int(row["count"])


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


def next_review_date(stage: int) -> str:
    index = max(0, min(stage, len(REVIEW_INTERVAL_DAYS) - 1))
    return (datetime.now().date() + timedelta(days=REVIEW_INTERVAL_DAYS[index])).isoformat()


def cloze_forms(word: str) -> set[str]:
    base = word.strip().lower()
    if not base or not re.fullmatch(r"[a-z]+", base):
        return {base} if base else set()

    forms = {base}
    forms.update(CLOZE_IRREGULAR_FORMS.get(base, set()))

    if base.endswith("y") and len(base) > 1 and base[-2] not in "aeiou":
        forms.add(f"{base[:-1]}ies")
        forms.add(f"{base[:-1]}ied")
    else:
        if base.endswith(("s", "x", "z", "ch", "sh", "o")):
            forms.add(f"{base}es")
        else:
            forms.add(f"{base}s")
        forms.add(f"{base}ed")

    if base.endswith("e") and not base.endswith("ee"):
        forms.add(f"{base}d")
        forms.add(f"{base[:-1]}ing")
    else:
        forms.add(f"{base}ing")

    if len(base) >= 3 and base[-1] not in "aeiouwxy" and base[-2] in "aeiou" and base[-3] not in "aeiou":
        forms.add(f"{base}{base[-1]}ed")
        forms.add(f"{base}{base[-1]}ing")

    return {form for form in forms if form}


def cloze_match_pattern(word: str) -> re.Pattern[str] | None:
    forms = sorted(cloze_forms(word), key=len, reverse=True)
    if not forms:
        return None
    alternatives = "|".join(re.escape(form) for form in forms)
    return re.compile(rf"(?<![A-Za-z'])({alternatives})(?![A-Za-z'])", re.IGNORECASE)


def cloze_answer(sentence: str | None, word: str) -> str:
    sentence = (sentence or "").strip()
    pattern = cloze_match_pattern(word)
    if not sentence or pattern is None:
        return ""
    match = pattern.search(sentence)
    return match.group(1) if match else ""


def cloze_prompt(sentence: str | None, word: str) -> str:
    sentence = (sentence or "").strip()
    if not sentence or not word:
        return ""
    pattern = cloze_match_pattern(word)
    if pattern is None:
        return ""
    prompt, replacements = pattern.subn("____", sentence, count=1)
    return prompt if replacements else ""


def valid_example_sentence(sentence: str | None, word: str) -> bool:
    return bool(cloze_prompt(sentence, word))


def english_word_count(sentence: str) -> int:
    return len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", sentence))


def contains_blocked_example_word(sentence: str) -> bool:
    words = {word.lower() for word in re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", sentence)}
    return bool(words & BLOCKED_EXAMPLE_WORDS)


def example_target_position_penalty(sentence: str, word: str) -> int:
    pattern = cloze_match_pattern(word)
    if pattern is None:
        return 3
    match = pattern.search(sentence)
    if not match:
        return 3

    tokens = list(re.finditer(r"[A-Za-z]+(?:'[A-Za-z]+)?", sentence))
    if len(tokens) < 4:
        return 2

    target_index = None
    for index, token in enumerate(tokens):
        if token.start() <= match.start() < token.end():
            target_index = index
            break
    if target_index is None:
        return 2

    if target_index == 0 or target_index == len(tokens) - 1:
        return 3
    if target_index == 1 or target_index == len(tokens) - 2:
        return 1
    return 0


def normalize_answer(value: str) -> str:
    return value.strip()


def answer_matches(word: sqlite3.Row, answer: str, prompt_mode: str) -> bool:
    normalized = normalize_answer(answer)
    if prompt_mode == PROMPT_CLOZE:
        accepted = {word["word"], cloze_answer(word["example_sentence"], word["word"])}
        return normalized.lower() in {item.lower() for item in accepted if item}
    return normalized == word["word"]


def answer_feedback(word: sqlite3.Row, answer: str, is_correct: bool) -> dict[str, object]:
    return {
        "correct": is_correct,
        "answer": answer,
        "word": word["word"],
        "part_of_speech": word["part_of_speech"],
        "meaning": word["meaning"],
        "example_sentence": word["example_sentence"],
        "cloze_text": cloze_prompt(word["example_sentence"], word["word"]),
        "cloze_answer": cloze_answer(word["example_sentence"], word["word"]),
    }


def cloze_form_hint_feedback(word: sqlite3.Row, answer: str, prompt_mode: str) -> dict[str, object] | None:
    if prompt_mode != PROMPT_CLOZE:
        return None
    sentence_form = cloze_answer(word["example_sentence"], word["word"])
    if not sentence_form:
        return None
    normalized_answer = normalize_answer(answer).lower()
    if normalized_answer != word["word"].lower() or normalized_answer == sentence_form.lower():
        return None
    feedback = answer_feedback(word, answer, True)
    feedback["form_hint"] = True
    sentence = word["example_sentence"] or ""
    pattern = cloze_match_pattern(word["word"])
    match = pattern.search(sentence) if pattern is not None else None
    if match:
        feedback["example_before"] = sentence[:match.start()]
        feedback["example_match"] = sentence[match.start():match.end()]
        feedback["example_after"] = sentence[match.end():]
    return feedback


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


def ids_with_cloze(rows: list[sqlite3.Row], limit: int) -> list[int]:
    ids: list[int] = []
    for row in rows:
        if cloze_prompt(row["example_sentence"], row["word"]):
            ids.append(int(row["id"]))
            if len(ids) >= limit:
                break
    return ids


def cloze_ids_from_ids(ids: list[int]) -> list[int]:
    return [
        int(row["id"])
        for row in fetch_words_by_ids(ids)
        if cloze_prompt(row["example_sentence"], row["word"])
    ]


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


def clear_invalid_example_sentences(db: sqlite3.Connection) -> None:
    rows = db.execute(
        """
        SELECT id, word, example_sentence
        FROM words
        WHERE example_sentence IS NOT NULL
          AND trim(example_sentence) != ''
        """
    ).fetchall()
    invalid_ids = [
        int(row["id"])
        for row in rows
        if not valid_example_sentence(row["example_sentence"], row["word"])
        or contains_blocked_example_word(row["example_sentence"] or "")
    ]
    for start in range(0, len(invalid_ids), 500):
        batch = invalid_ids[start : start + 500]
        placeholders = ",".join("?" for _ in batch)
        db.execute(
            f"""
            UPDATE words
            SET example_sentence = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id IN ({placeholders})
            """,
            batch,
        )


def simplify_existing_example_translations(db: sqlite3.Connection) -> None:
    rows = db.execute(
        """
        SELECT id, example_translation
        FROM words
        WHERE example_translation IS NOT NULL
          AND trim(example_translation) != ''
        """
    ).fetchall()
    for row in rows:
        simplified = simplify_chinese(row["example_translation"])
        if simplified and simplified != row["example_translation"]:
            db.execute(
                """
                UPDATE words
                SET example_translation = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (simplified, row["id"]),
            )


def normalize_part_group(part_of_speech: str) -> str:
    part = normalize_ecdict_pos(part_of_speech)
    if part in {"vt", "vi"}:
        return "v"
    if part in {"noun"}:
        return "n"
    if part in {"adjective"}:
        return "adj"
    if part in {"adverb"}:
        return "adv"
    return part


def matched_form_in_sentence(sentence: str, word: str) -> str:
    pattern = cloze_match_pattern(word)
    if pattern is None:
        return ""
    match = pattern.search(sentence)
    return match.group(1).lower() if match else ""


def sentence_tokens(sentence: str) -> list[str]:
    return [token.lower() for token in re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", sentence)]


def first_match_context(sentence: str, word: str) -> tuple[list[str], int]:
    form = matched_form_in_sentence(sentence, word)
    if not form:
        return [], -1
    tokens = sentence_tokens(sentence)
    for index, token in enumerate(tokens):
        if token == form:
            return tokens, index
    return tokens, -1


def token_after_adverbs(tokens: list[str], index: int) -> str:
    adverbs = {
        "only",
        "also",
        "still",
        "just",
        "really",
        "probably",
        "possibly",
        "easily",
        "hardly",
        "never",
        "always",
        "simply",
        "quickly",
        "actually",
        "even",
    }
    cursor = index + 1
    while cursor < len(tokens) and tokens[cursor] in adverbs:
        cursor += 1
    return tokens[cursor] if cursor < len(tokens) else ""


def high_ambiguity_pos_allowed(sentence: str, word: str, part_of_speech: str) -> bool:
    group = normalize_part_group(part_of_speech)
    base = word.lower()
    tokens, index = first_match_context(sentence, word)
    if index < 0:
        return False
    previous_token = tokens[index - 1] if index > 0 else ""
    next_token = tokens[index + 1] if index < len(tokens) - 1 else ""
    next_content_token = token_after_adverbs(tokens, index)
    determiners = {"a", "an", "the", "this", "that", "these", "those", "my", "your", "his", "her", "our", "their", "another"}
    base_verbs = {
        "be",
        "have",
        "do",
        "go",
        "get",
        "make",
        "take",
        "see",
        "come",
        "help",
        "use",
        "work",
        "find",
        "learn",
        "speak",
        "read",
        "write",
        "play",
        "change",
        "become",
        "move",
        "show",
        "tell",
        "give",
        "keep",
        "try",
        "start",
        "stop",
        "leave",
        "bring",
        "put",
        "let",
        "say",
        "wonder",
        "phrase",
    }
    if base == "can":
        if group == "aux":
            return next_content_token in base_verbs
        if group == "n":
            return previous_token in determiners or next_token in {"of", "with"}
        if group == "v":
            return (previous_token == "to" and next_token != "of") or next_token in {"up", "food"}
        return False
    if base == "way":
        if group == "adv":
            return next_token in {"too", "more", "less", "better", "worse", "ahead", "back", "out"} and previous_token not in (determiners | {"own"})
        if group == "n":
            return previous_token in determiners or previous_token in {"my", "your", "his", "her", "our", "their"} or next_token in {"of", "to"}
    if base == "even":
        if group == "adv":
            return next_token in {"though", "if", "when", "so", "more", "less", "better", "worse"} or previous_token not in determiners
        if group == "adj":
            return next_token in {"number", "numbers", "surface", "surfaces", "distribution", "chance", "chances"}
        if group == "n":
            return previous_token in determiners and next_token in {"number", "numbers"}
        if group == "v":
            return next_token in {"out", "up"}
        return False
    if base == "still":
        if group == "adv":
            return previous_token not in determiners and next_token not in {"life", "lives", "water", "waters", "picture", "pictures", "photograph", "photographs"}
        if group == "adj":
            return next_token in {"water", "waters", "life", "lives", "picture", "pictures", "photograph", "photographs"}
        if group == "n":
            return previous_token in determiners and next_token in {"photo", "photos", "photograph", "photographs", "image", "images"}
        if group == "v":
            return previous_token == "to" and next_token in {"the", "his", "her", "their", "its"}
        if group == "conj":
            return index == 0 and len(tokens) > 3 and tokens[1] not in {"want", "wants", "wanted"}
        return False
    if base == "well":
        if group == "adv":
            return previous_token not in determiners and (index == len(tokens) - 1 or next_token in {"enough", "aware", "known", "suited"})
        if group == "adj":
            return previous_token in {"am", "is", "are", "was", "were", "be", "been", "being", "feel", "feels", "felt"} and next_token not in {"looked", "known", "done", "made", "suited"}
        if group == "n":
            return previous_token in determiners or next_token in {"of"}
        if group == "interj":
            return index == 0
        if group == "v":
            return next_token in {"up", "out"}
    return True


def part_of_speech_penalty(sentence: str, word: str, part_of_speech: str) -> int:
    group = normalize_part_group(part_of_speech)
    if group == "phrase":
        return 0
    if not high_ambiguity_pos_allowed(sentence, word, part_of_speech):
        return 10
    form = matched_form_in_sentence(sentence, word)
    if not form:
        return 6

    base_word = word.lower()
    if group in {"v", "adj", "adv", "aux"} and form == f"{base_word}s":
        return 10

    lowered = sentence.lower()
    tokens, token_index = first_match_context(sentence, word)
    previous_token = tokens[token_index - 1] if token_index > 0 else ""
    next_token = tokens[token_index + 1] if 0 <= token_index < len(tokens) - 1 else ""
    next_content_token = token_after_adverbs(tokens, token_index) if token_index >= 0 else ""
    common_nouns_after_adjective = {
        "speech",
        "task",
        "job",
        "work",
        "problem",
        "question",
        "issue",
        "situation",
        "experience",
        "role",
        "case",
        "idea",
        "project",
        "course",
        "position",
        "time",
        "thing",
        "things",
        "people",
        "life",
    }
    escaped = re.escape(form)
    determiners = {"a", "an", "the", "this", "that", "these", "those", "my", "your", "his", "her", "our", "their", "another", "enough"}
    noun_preceders = determiners | {"real", "great", "big", "new", "major", "serious", "important", "difficult"}
    before = previous_token in noun_preceders or re.search(rf"\b(?:a|an|the|this|that|these|those|my|your|his|her|our|their|another|enough|real|great|big|new|major|serious|important|difficult)\s+{escaped}\b", lowered)
    after = re.search(rf"\b{escaped}\s+(?:of|for|from|with|in|on|to|that|which)\b", lowered)
    base_verbs = {
        "be",
        "have",
        "do",
        "go",
        "get",
        "make",
        "take",
        "see",
        "come",
        "help",
        "use",
        "work",
        "find",
        "learn",
        "speak",
        "read",
        "write",
        "play",
        "change",
        "become",
        "move",
        "show",
        "tell",
        "give",
        "keep",
        "try",
        "start",
        "stop",
        "leave",
        "bring",
        "put",
        "let",
        "say",
        "wonder",
        "phrase",
    }
    aux_use = next_content_token in base_verbs
    to_verb = re.search(rf"\bto\s+{escaped}\b", lowered)
    copulas = {"am", "is", "are", "was", "were", "be", "been", "being", "feel", "feels", "felt", "seem", "seems", "seemed", "look", "looks", "looked"}
    be_adj = previous_token in copulas or re.search(rf"\b(?:am|is|are|was|were|be|been|being|feel|feels|felt|seem|seems|seemed|look|looks|looked)\s+{escaped}\b", lowered)
    ly_form = form.endswith("ly")
    noun_phrase_use = bool(before or after or re.search(rf"\b(?:in|on|by|from|with|through|into)\s+(?:a|an|the|this|that|another|my|your|his|her|our|their)?\s*{escaped}\b", lowered))
    adverbial_end_use = token_index == len(tokens) - 1 and previous_token not in determiners

    if group == "aux":
        return 0 if aux_use else 6
    if group == "n":
        penalty = 0
        if form.endswith("s") and form != word.lower():
            penalty += 7
        if aux_use or to_verb:
            penalty += 8
        if noun_phrase_use:
            penalty -= 2
        elif word.lower() in {"can", "well", "way"}:
            penalty += 4
        return max(0, penalty)
    if group == "v":
        penalty = 0
        if form.endswith("ing") and next_token in common_nouns_after_adjective:
            return 10
        if before and not to_verb and not form.endswith("s"):
            penalty += 5
        if aux_use or to_verb or form.endswith(("ed", "ing", "s")):
            penalty -= 1
        if form.endswith("ing") and previous_token not in {"am", "is", "are", "was", "were", "be", "been", "being", "keep", "keeps", "kept", "start", "starts", "started", "stop", "stops", "stopped"}:
            penalty += 3
        if form.endswith("s") and previous_token in determiners:
            penalty += 4
        if word.lower() == "can" and aux_use:
            penalty += 5
        return max(0, penalty)
    if group == "adj":
        penalty = 0
        if be_adj:
            penalty -= 2
        elif next_token and next_token not in {"of", "to", "for", "with", "in", "on"} and not aux_use:
            penalty -= 1
        elif word.lower() in {"well"}:
            penalty += 4
        if aux_use:
            penalty += 5
        if adverbial_end_use and word.lower() in {"well"}:
            penalty += 5
        if ly_form:
            penalty += 2
        return max(0, penalty)
    if group == "adv":
        penalty = 0
        if ly_form:
            penalty -= 2
        if before:
            penalty += 4
        if aux_use:
            penalty += 3
        if word.lower() == "way" and noun_phrase_use:
            penalty += 5
        if word.lower() == "well" and adverbial_end_use:
            penalty -= 2
        return max(0, penalty)
    return 1


def sentence_quality_score(
    sentence: str,
    word: str = "",
    part_of_speech: str = "",
    source: str = "dictionary",
) -> tuple[int, int, int, int, str]:
    word_count = english_word_count(sentence)
    if 6 <= word_count <= 18:
        length_penalty = 0
    elif 4 <= word_count <= 24:
        length_penalty = 1
    else:
        length_penalty = 3

    punctuation_penalty = 0
    if re.search(r"https?://|www\.|[@#]", sentence, re.IGNORECASE):
        punctuation_penalty += 5
    if re.search(r"[_{}\[\]<>]", sentence):
        punctuation_penalty += 2
    if sentence.count('"') > 2:
        punctuation_penalty += 1
    if re.search(r",\s*(?:guys|man|dude|sir|madam|mom|dad)[.!?]?$", sentence, re.IGNORECASE):
        punctuation_penalty += 2
    if sentence.rstrip().endswith("!"):
        punctuation_penalty += 1

    target_position_penalty = example_target_position_penalty(sentence, word) if word else 0
    pos_penalty = part_of_speech_penalty(sentence, word, part_of_speech) if word and part_of_speech else 0
    translation_penalty = 3
    return (
        translation_penalty,
        pos_penalty,
        length_penalty + punctuation_penalty + target_position_penalty,
        len(sentence),
        sentence.lower(),
    )


def ambiguous_library_words(rows: list[sqlite3.Row]) -> set[str]:
    row_words = sorted({str(row["word"]).strip().lower() for row in rows if str(row["word"]).strip()})
    if not row_words:
        return set()

    placeholders = ",".join("?" for _ in row_words)
    library_rows = get_db().execute(
        f"""
        SELECT lower(word) AS word_key, part_of_speech
        FROM words
        WHERE library_id = ?
          AND lower(word) IN ({placeholders})
        """,
        [get_active_library_id(), *row_words],
    ).fetchall()

    grouped_parts: dict[str, set[str]] = {}
    for row in library_rows:
        word = str(row["word_key"]).strip().lower()
        if not word:
            continue
        grouped_parts.setdefault(word, set()).add(normalize_part_group(str(row["part_of_speech"])))
    return {word for word, parts in grouped_parts.items() if len(parts) > 1}


def usable_wordnet_example(sentence: str, word: str) -> bool:
    stripped = sentence.strip()
    if not stripped or not valid_example_sentence(stripped, word):
        return False
    if contains_blocked_example_word(stripped):
        return False
    if len(stripped) < 6 or len(stripped) > 180:
        return False
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
    return f"{path.name}:{stat.st_size}:{int(stat.st_mtime)}:{WIKTIONARY_SCHEMA_VERSION}"


def wiktionary_part_group(part_of_speech: str) -> str:
    group = normalize_part_group(part_of_speech)
    if group == "aux":
        return "v"
    if group == "conj":
        return "adv"
    if group == "noun":
        return "n"
    if group == "verb":
        return "v"
    if group == "adjective":
        return "adj"
    if group == "adverb":
        return "adv"
    return group


def wiktionary_lookup_groups(part_of_speech: str, word: str) -> list[str]:
    primary = wiktionary_part_group(part_of_speech)
    groups = [primary]
    if primary == "phrase" and re.search(r"\s", word.strip()):
        groups.extend(["prep", "v", "adj", "adv", "n"])
    return list(dict.fromkeys(group for group in groups if group))


def normalize_wiktionary_pos(pos: str) -> str:
    mapping = {
        "noun": "n",
        "proper noun": "n",
        "verb": "v",
        "adj": "adj",
        "adjective": "adj",
        "adv": "adv",
        "adverb": "adv",
        "pron": "pron",
        "pronoun": "pron",
        "prep": "prep",
        "preposition": "prep",
        "conj": "conj",
        "conjunction": "conj",
        "interj": "interj",
        "intj": "interj",
        "interjection": "interj",
        "num": "num",
        "numeral": "num",
        "det": "det",
        "determiner": "det",
        "phrase": "phrase",
    }
    return mapping.get(pos.strip().lower(), pos.strip().lower())


def clean_wiktionary_example_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = cleaned.replace(" ", " ")
    return cleaned


def usable_wiktionary_example(sentence: str, word: str) -> bool:
    stripped = clean_wiktionary_example_text(sentence)
    if not stripped or not valid_example_sentence(stripped, word):
        return False
    if contains_blocked_example_word(stripped):
        return False
    if len(stripped) < 6 or len(stripped) > 180:
        return False
    if re.search(r"https?://|www\.|[@#]|→|<|>|[_{}\[\]]", stripped):
        return False
    if stripped.startswith(("Synonyms:", "Antonyms:", "Holonyms:", "Meronyms:", "Hyponyms:", "Hypernyms:")):
        return False
    if len(re.findall(r"[A-Za-z]+", stripped)) < 2:
        return False
    return True


def wiktionary_example_rank(example: dict[str, object], sentence: str) -> int:
    rank = 0
    if example.get("type") == "quotation":
        rank += 80
    if example.get("ref"):
        rank += 3
    if sentence.lower().startswith("to "):
        rank += 12
    if sentence.count(";") or " / " in sentence:
        rank += 8
    if len(sentence) > 120:
        rank += 2
    return rank


def simplify_chinese(text: str | None) -> str | None:
    if text is None:
        return None
    if OPENCC_T2S is not None:
        return OPENCC_T2S.convert(text)
    return text.translate(TRADITIONAL_TO_SIMPLIFIED)


def fill_examples_from_dictionaries(
    start: int = 1,
    end: int = 100,
    mode: str = "best",
) -> tuple[int, int]:
    if not WORDNET_ZIP_PATH.exists() and not wiktionary_jsonl_path():
        return 0, -1

    rows = fetch_word_range(start, end, "id, word, part_of_speech, example_sentence")
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
        else:
            definition = lookup_wordnet_definition(word, part_of_speech)
            if definition:
                definitions[int(row["id"])] = definition

        if mode == "refresh":
            lookup = refresh_example_candidate(word, part_of_speech, row["example_sentence"], top_n=8)
            if lookup:
                matches[int(row["id"])] = (lookup["example_sentence"], lookup["definition"])
            continue

        lookup = lookup_wiktionary_example(word, part_of_speech)
        if lookup:
            matches[int(row["id"])] = (lookup["example_sentence"], lookup["definition"])
            continue
        lookup = lookup_wordnet_example(word, part_of_speech)
        if lookup:
            matches[int(row["id"])] = (lookup["example_sentence"], lookup["definition"])

    missing_ids = sorted({int(row["id"]) for row in rows} - set(matches))
    if mode != "refresh":
        for batch_start in range(0, len(missing_ids), 500):
            batch = missing_ids[batch_start : batch_start + 500]
            placeholders = ",".join("?" for _ in batch)
            get_db().execute(
                f"""
                UPDATE words
                SET example_sentence = NULL,
                    example_translation = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE library_id = ?
                  AND id IN ({placeholders})
                """,
                [get_active_library_id(), *batch],
            )

    for word_id, (sentence, example_definition) in matches.items():
        definition = definitions.get(word_id) or example_definition
        get_db().execute(
            """
            UPDATE words
            SET example_sentence = ?,
                example_translation = NULL,
                definition = COALESCE(?, definition),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND library_id = ?
            """,
            (sentence, definition, word_id, get_active_library_id()),
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
    get_db().commit()
    return len(matches), len(rows)


def schedule_initial_review(word_id: int) -> None:
    get_db().execute(
        """
        UPDATE words
        SET review_stage = 0,
            next_review_at = COALESCE(next_review_at, ?),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND library_id = ?
        """,
        (next_review_date(0), word_id, get_active_library_id()),
    )


def complete_review(word_id: int) -> None:
    word = fetch_word(word_id)
    if word is None:
        return
    target = review_target_count()
    new_count = int(word["review_correct_count"]) + 1
    new_stage = int(word["review_stage"]) + 1
    next_at = None if new_count >= target else next_review_date(new_stage)
    get_db().execute(
        """
        UPDATE words
        SET status = ?,
            review_correct_count = ?,
            review_stage = ?,
            next_review_at = ?,
            last_reviewed_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND library_id = ?
        """,
        (STATUS_LEARNED, new_count, new_stage, next_at, word_id, get_active_library_id()),
    )


def reset_review_schedule(word_id: int) -> None:
    get_db().execute(
        """
        UPDATE words
        SET review_correct_count = 0,
            review_stage = 0,
            next_review_at = NULL,
            last_reviewed_at = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND library_id = ?
        """,
        (word_id, get_active_library_id()),
    )


def fetch_libraries() -> list[sqlite3.Row]:
    return get_db().execute(
        """
        SELECT
            libraries.*,
            COUNT(words.id) AS word_count
        FROM libraries
        LEFT JOIN words ON words.library_id = libraries.id
        GROUP BY libraries.id
        ORDER BY libraries.id ASC
        """
    ).fetchall()


def fetch_library(library_id: int) -> sqlite3.Row | None:
    return get_db().execute("SELECT * FROM libraries WHERE id = ?", (library_id,)).fetchone()


def get_active_library_id() -> int:
    db = get_db()
    requested_id = session.get("active_library_id")
    if requested_id is not None:
        row = fetch_library(int(requested_id))
        if row:
            return int(row["id"])

    row = db.execute("SELECT id FROM libraries ORDER BY id ASC LIMIT 1").fetchone()
    if row is None:
        db.execute("INSERT INTO libraries (name) VALUES (?)", ("Default Library",))
        db.commit()
        row = db.execute("SELECT id FROM libraries ORDER BY id ASC LIMIT 1").fetchone()
    session["active_library_id"] = int(row["id"])
    return int(row["id"])


def get_active_library() -> sqlite3.Row:
    return fetch_library(get_active_library_id())


def get_or_create_library(name: str) -> int:
    row = get_db().execute("SELECT id FROM libraries WHERE name = ?", (name,)).fetchone()
    if row:
        return int(row["id"])
    cursor = get_db().execute("INSERT INTO libraries (name) VALUES (?)", (name,))
    get_db().commit()
    return int(cursor.lastrowid)


def reset_ecdict_library(library_id: int) -> None:
    get_db().execute(
        """
        DELETE FROM words
        WHERE library_id = ? AND source = ?
        """,
        (library_id, "ECDICT"),
    )
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
    get_db().commit()
    prune_word_ids_from_session(word_ids)
    return deleted


def parse_word_file(filename: str, raw: bytes) -> tuple[list[dict[str, str]], list[str]]:
    text = raw.decode("utf-8-sig")
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        return parse_csv(text)
    return parse_text_lines(text)


def normalize_entry(row: list[str], line_number: int) -> tuple[dict[str, str] | None, str | None]:
    if len(row) < 3:
        return None, f"Line {line_number}: expected word, part of speech, and meaning."

    word = row[0].strip()
    part_of_speech = normalize_user_pos(row[1].strip())
    meaning = row[2].strip()
    example_sentence = row[3].strip() if len(row) > 3 else ""
    example_translation = row[4].strip() if len(row) > 4 else ""

    if not word or not part_of_speech or not meaning:
        return None, f"Line {line_number}: word, part of speech, and meaning are required."

    entry = {"word": word, "part_of_speech": part_of_speech, "meaning": meaning}
    if example_sentence:
        if valid_example_sentence(example_sentence, word):
            entry["example_sentence"] = example_sentence
            if example_translation:
                entry["example_translation"] = example_translation
        else:
            return entry, f"Line {line_number}: example sentence ignored because it does not contain the target word."
    return entry, None


def parse_csv(text: str) -> tuple[list[dict[str, str]], list[str]]:
    entries: list[dict[str, str]] = []
    errors: list[str] = []
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)

    if not rows:
        return entries, ["The file is empty."]

    first = [cell.strip().lower() for cell in rows[0]]
    has_header = {"word", "part_of_speech", "meaning"}.issubset(set(first))

    start_index = 1 if has_header else 0
    field_indexes = (0, 1, 2)
    if has_header:
        field_indexes = (first.index("word"), first.index("part_of_speech"), first.index("meaning"))
        example_index = first.index("example_sentence") if "example_sentence" in first else None
        example_translation_index = first.index("example_translation") if "example_translation" in first else None
    else:
        example_index = 3
        example_translation_index = 4

    for index, row in enumerate(rows[start_index:], start=start_index + 1):
        if not row or all(not cell.strip() for cell in row):
            continue
        selected = [row[i] if i < len(row) else "" for i in field_indexes]
        if example_index is not None:
            selected.append(row[example_index] if example_index < len(row) else "")
        if example_translation_index is not None:
            selected.append(row[example_translation_index] if example_translation_index < len(row) else "")
        entry, error = normalize_entry(selected, index)
        if entry:
            entries.append(entry)
        if error:
            errors.append(error)

    return entries, errors


def parse_text_lines(text: str) -> tuple[list[dict[str, str]], list[str]]:
    entries: list[dict[str, str]] = []
    errors: list[str] = []

    for index, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if "\t" in stripped:
            row = stripped.split("\t", 4)
        elif "|" in stripped:
            row = stripped.split("|", 4)
        else:
            row = re.split(r"\s*,\s*", stripped, maxsplit=4)

        entry, error = normalize_entry(row, index)
        if entry:
            entries.append(entry)
        if error:
            errors.append(error)

    if not entries and not errors:
        errors.append("The file does not contain any usable words.")

    return entries, errors


def split_ecdict_tags(raw_tags: str) -> set[str]:
    return {tag.strip().lower() for tag in re.split(r"[\s,/;|]+", raw_tags or "") if tag.strip()}


def clean_ecdict_text(value: str, line_separator: str = " ") -> str:
    text = (value or "").replace("\\n", "\n")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return ""
    return line_separator.join(lines)


def format_ecdict_definition(raw_definition: str) -> str:
    lines: list[str] = []
    for line in (raw_definition or "").replace("\\n", "\n").splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        lines.extend(part.strip() for part in ECDICT_DEFINITION_SPLIT_RE.split(line) if part.strip())
    return "\n".join(lines)


def normalize_ecdict_pos(raw_pos: str) -> str:
    first = re.split(r"[\s,/;|.]+", raw_pos.strip().lower())[0] if raw_pos else ""
    return ECDICT_POS_MAP.get(first, "phrase")


def infer_pos_from_ecdict_definition(raw_definition: str) -> str:
    counts: dict[str, int] = {}
    for line in (raw_definition or "").replace("\\n", "\n").splitlines():
        match = ECDICT_DEFINITION_POS_RE.match(line)
        if not match:
            continue
        part = normalize_ecdict_pos(match.group(1))
        if part == "phrase":
            continue
        counts[part] = counts.get(part, 0) + 1
    if not counts:
        return ""
    return max(counts.items(), key=lambda item: item[1])[0]


def infer_pos_from_ecdict_exchange(raw_exchange: str) -> str:
    tokens = {token.strip().lower() for token in re.split(r"[/,;|\s]+", raw_exchange or "") if token.strip()}
    if {"1:s", "p:s", "plural", "pl"} & tokens:
        return "n"
    return ""


def infer_pos_from_word_shape(word: str, meaning: str) -> str:
    word_key = word.strip().lower()
    if not word_key or re.search(r"\s", word_key):
        return ""
    if "-" in word_key:
        if meaning.strip().endswith("的"):
            return "adj"
        return ""
    noun_suffixes = (
        "tion",
        "sion",
        "ment",
        "ness",
        "ity",
        "ism",
        "ance",
        "ence",
        "ship",
        "graph",
        "er",
        "or",
    )
    adjective_suffixes = (
        "al",
        "ial",
        "ical",
        "ic",
        "ive",
        "ous",
        "less",
        "able",
        "ible",
        "ary",
        "ory",
        "ant",
        "ent",
        "ed",
    )
    if word_key.endswith("ly"):
        return "adv"
    if word_key.endswith(noun_suffixes):
        return "n"
    if word_key.endswith(adjective_suffixes) or meaning.strip().endswith("的"):
        return "adj"
    return ""


def infer_ecdict_fallback_pos(row: dict[str, str]) -> str:
    explicit_pos = normalize_ecdict_pos(row.get("pos", ""))
    if explicit_pos != "phrase":
        return explicit_pos

    definition_pos = infer_pos_from_ecdict_definition(row.get("definition", ""))
    if definition_pos:
        return definition_pos

    exchange_pos = infer_pos_from_ecdict_exchange(row.get("exchange", ""))
    if exchange_pos:
        return exchange_pos

    shape_pos = infer_pos_from_word_shape(row.get("word", ""), row.get("translation", ""))
    if shape_pos:
        return shape_pos

    return "phrase"


def split_ecdict_translation(raw_translation: str, fallback_pos: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    current_pos = ""
    current_meaning: list[str] = []

    def flush_current() -> None:
        if not current_meaning:
            return
        meaning = clean_ecdict_text("\n".join(current_meaning), line_separator="；")
        if meaning:
            entries.append((current_pos or fallback_pos, meaning))

    for line in (raw_translation or "").replace("\\n", "\n").splitlines():
        line = line.strip()
        if not line:
            continue

        match = ECDICT_POS_PREFIX_RE.match(line)
        if match:
            prefix = normalize_ecdict_pos(match.group(1))
            remainder = match.group(2).strip()
            if prefix != "phrase":
                flush_current()
                current_pos = prefix
                current_meaning = [remainder] if remainder else []
                continue

        if current_meaning:
            current_meaning.append(line)
        else:
            current_pos = fallback_pos
            current_meaning = [line]

    flush_current()

    if entries:
        return entries
    cleaned = clean_ecdict_text(raw_translation)
    return [(fallback_pos, cleaned)] if cleaned else []


def normalize_ecdict_frequency(row: dict[str, str]) -> int | None:
    for key in ("frq", "bnc"):
        value = (row.get(key) or "").strip()
        if not value:
            continue
        try:
            frequency = int(float(value))
        except ValueError:
            continue
        if frequency > 0:
            return frequency
    return None


def parse_ecdict_csv(
    raw: bytes,
    presets: dict[str, dict[str, object]] | None = None,
) -> tuple[dict[str, list[dict[str, str]]], list[str]]:
    if presets is None:
        presets = ECDICT_PRESET_LIBRARIES

    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return {}, ["The ECDICT file is empty or missing a header row."]

    fieldnames = {name.strip().lower() for name in reader.fieldnames if name}
    required = {"word", "translation", "tag"}
    missing = required - fieldnames
    if missing:
        return {}, [f"ECDICT CSV is missing required columns: {', '.join(sorted(missing))}."]

    grouped: dict[str, list[dict[str, str]]] = {
        str(config["name"]): [] for config in presets.values()
    }
    errors: list[str] = []

    for line_number, row in enumerate(reader, start=2):
        normalized = {(key or "").strip().lower(): (value or "").strip() for key, value in row.items()}
        word = normalized.get("word", "")
        translation = normalized.get("translation", "")
        tags = split_ecdict_tags(normalized.get("tag", ""))
        if not word or not translation or not tags:
            continue

        target_libraries = []
        for config in presets.values():
            preset_tags = set(config["tags"])
            if tags & preset_tags:
                target_libraries.append(str(config["name"]))
        if not target_libraries:
            continue

        fallback_pos = infer_ecdict_fallback_pos(normalized)
        translations = split_ecdict_translation(translation, fallback_pos)
        for part_of_speech, meaning in translations:
            entry = {
                "word": word,
                "part_of_speech": part_of_speech,
                "meaning": meaning,
                "phonetic": normalized.get("phonetic") or None,
                "definition": format_ecdict_definition(normalized.get("definition", "")) or None,
                "frequency": normalize_ecdict_frequency(normalized),
                "source": "ECDICT",
                "source_tags": normalized.get("tag") or None,
            }

            for library_name in target_libraries:
                grouped[library_name].append(entry)

    grouped = {library_name: entries for library_name, entries in grouped.items() if entries}
    if not grouped:
        errors.append("No supported ECDICT tags were found. Supported tags include zk, gk, cet4, cet6, ky, ielts, toefl, gre.")

    return grouped, errors


def ecdict_entries_for_word(
    word: str,
    part_of_speech: str = "",
    meaning: str = "",
    raw: bytes | None = None,
) -> list[dict[str, object]]:
    word_key = word.strip().lower()
    if not word_key:
        return []

    if raw is None:
        try:
            raw = load_ecdict_data()
        except Exception:
            return []

    requested_part = normalize_user_pos(part_of_speech.strip()) if part_of_speech else ""
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    merged: dict[str, dict[str, object]] = {}
    for row in reader:
        normalized = {(key or "").strip().lower(): (value or "").strip() for key, value in row.items()}
        if normalized.get("word", "").lower() != word_key:
            continue

        fallback_pos = infer_ecdict_fallback_pos(normalized)
        translations = split_ecdict_translation(normalized.get("translation", ""), fallback_pos)
        for entry_part, entry_meaning in translations:
            part = normalize_user_pos(entry_part)
            if requested_part and part != requested_part:
                continue
            if not entry_meaning and not meaning:
                continue
            existing = merged.setdefault(
                part,
                {
                    "word": normalized.get("word") or word,
                    "part_of_speech": part,
                    "meaning_parts": [],
                    "phonetic": normalized.get("phonetic") or None,
                    "definition": format_ecdict_definition(normalized.get("definition", "")) or None,
                    "frequency": normalize_ecdict_frequency(normalized),
                    "source": "ECDICT",
                    "source_tags": normalized.get("tag") or None,
                },
            )
            if entry_meaning:
                existing["meaning_parts"].append(entry_meaning)

    entries: list[dict[str, object]] = []
    for part, entry in merged.items():
        selected_meaning = meaning or merge_text_values(*(entry.pop("meaning_parts") or []))
        if selected_meaning:
            entry["meaning"] = selected_meaning
            entries.append(entry)

    if requested_part and meaning and not entries:
        entries.append({"word": word, "part_of_speech": requested_part, "meaning": meaning})

    return entries


def load_ecdict_data() -> bytes:
    if BUNDLED_ECDICT_PATH.exists():
        return BUNDLED_ECDICT_PATH.read_bytes()

    if ECDICT_CACHE_PATH.exists():
        return ECDICT_CACHE_PATH.read_bytes()

    DATA_DIR.mkdir(exist_ok=True)
    with urllib.request.urlopen(ECDICT_SOURCE_URL, timeout=30) as response:
        raw = response.read()
    ECDICT_CACHE_PATH.write_bytes(raw)
    return raw


def ecdict_source_signature() -> str | None:
    if BUNDLED_ECDICT_PATH.exists():
        path = BUNDLED_ECDICT_PATH
    elif ECDICT_CACHE_PATH.exists():
        path = ECDICT_CACHE_PATH
    else:
        return None
    stat = path.stat()
    return f"{path.name}:{stat.st_size}:{int(stat.st_mtime)}:{ECDICT_LOOKUP_SCHEMA_VERSION}"


def ensure_ecdict_lookup_index() -> None:
    signature = ecdict_source_signature()
    if not signature:
        return

    db = get_db()
    existing = db.execute("SELECT value FROM metadata WHERE key = ?", ("ecdict_lookup_signature",)).fetchone()
    table_exists = db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        ("ecdict_lookup",),
    ).fetchone()
    if table_exists and existing and existing["value"] == signature:
        return

    try:
        raw = load_ecdict_data()
    except OSError:
        # No bundled/cached ECDICT and the download failed (e.g. offline).
        # Skip enrichment instead of turning an import/edit into a 500.
        return
    db.execute("DROP TABLE IF EXISTS ecdict_lookup")
    db.execute(
        """
        CREATE TABLE ecdict_lookup (
            word_key TEXT PRIMARY KEY,
            word TEXT NOT NULL,
            phonetic TEXT,
            definition TEXT,
            frequency INTEGER,
            source_tags TEXT
        )
        """
    )

    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows: dict[str, dict[str, object]] = {}
    for row in reader:
        normalized = {(key or "").strip().lower(): (value or "").strip() for key, value in row.items()}
        word = normalized.get("word", "")
        word_key = word.lower()
        if not word_key:
            continue

        candidate = {
            "word_key": word_key,
            "word": word,
            "phonetic": normalized.get("phonetic") or None,
            "definition": format_ecdict_definition(normalized.get("definition", "")) or None,
            "frequency": normalize_ecdict_frequency(normalized),
            "source_tags": normalized.get("tag") or None,
        }
        existing_candidate = rows.get(word_key)
        if existing_candidate is None:
            rows[word_key] = candidate
            continue

        current_frequency = existing_candidate.get("frequency")
        candidate_frequency = candidate.get("frequency")
        if current_frequency is None and candidate_frequency is not None:
            rows[word_key] = candidate
        elif (
            current_frequency is not None
            and candidate_frequency is not None
            and int(candidate_frequency) < int(current_frequency)
        ):
            rows[word_key] = candidate

    db.executemany(
        """
        INSERT INTO ecdict_lookup (
            word_key, word, phonetic, definition, frequency, source_tags
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row["word_key"],
                row["word"],
                row["phonetic"],
                row["definition"],
                row["frequency"],
                row["source_tags"],
            )
            for row in rows.values()
        ],
    )
    db.execute(
        """
        INSERT INTO metadata (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        ("ecdict_lookup_signature", signature),
    )
    db.commit()


def lookup_ecdict_word(word: str) -> sqlite3.Row | None:
    if not word.strip():
        return None
    ensure_ecdict_lookup_index()
    return get_db().execute(
        """
        SELECT phonetic, definition, frequency, source_tags
        FROM ecdict_lookup
        WHERE word_key = ?
        """,
        (word.strip().lower(),),
    ).fetchone()


def wordnet_source_signature() -> str | None:
    if not WORDNET_ZIP_PATH.exists():
        return None
    stat = WORDNET_ZIP_PATH.stat()
    return f"{WORDNET_ZIP_PATH.name}:{stat.st_size}:{int(stat.st_mtime)}:{WORDNET_SCHEMA_VERSION}"


def wordnet_part_group(part_of_speech: str) -> str:
    group = normalize_part_group(part_of_speech)
    if group == "adj":
        return "a"
    if group in {"n", "v", "adv"}:
        return {"n": "n", "v": "v", "adv": "r"}[group]
    return group


def wordnet_entry_filenames() -> list[str]:
    return [f"entries-{character}.json" for character in "0abcdefghijklmnopqrstuvwxyz"]


def ensure_wordnet_lookup_index() -> None:
    signature = wordnet_source_signature()
    if not signature:
        return

    db = get_db()
    existing = db.execute("SELECT value FROM metadata WHERE key = ?", ("wordnet_lookup_signature",)).fetchone()
    table_exists = db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        ("wordnet_examples",),
    ).fetchone()
    if table_exists and existing and existing["value"] == signature:
        return

    with zipfile.ZipFile(WORDNET_ZIP_PATH) as archive:
        synsets: dict[str, dict[str, object]] = {}
        for name in archive.namelist():
            if not name.startswith(("noun.", "verb.", "adj.", "adv.")) or not name.endswith(".json"):
                continue
            data = json.loads(archive.read(name))
            if isinstance(data, dict):
                synsets.update(data)

        rows: list[tuple[str, str, str, str | None, str | None, int]] = []
        seen: set[tuple[str, str, str]] = set()
        for name in wordnet_entry_filenames():
            if name not in archive.namelist():
                continue
            entries = json.loads(archive.read(name))
            if not isinstance(entries, dict):
                continue
            for word, parts in entries.items():
                word_key = word.lower().replace("_", " ").strip()
                if not word_key or not isinstance(parts, dict):
                    continue
                for wn_part, payload in parts.items():
                    if wn_part not in {"n", "v", "a", "s", "r"} or not isinstance(payload, dict):
                        continue
                    normalized_part = "a" if wn_part == "s" else wn_part
                    senses = payload.get("sense") or []
                    for rank, sense in enumerate(senses):
                        synset_id = sense.get("synset") if isinstance(sense, dict) else None
                        synset = synsets.get(synset_id or "")
                        if not synset:
                            continue
                        examples = synset.get("example") or []
                        definitions = synset.get("definition") or []
                        if not examples:
                            continue
                        for example in examples:
                            sentence = str(example).strip()
                            if not valid_example_sentence(sentence, word_key):
                                continue
                            key = (word_key, normalized_part, sentence)
                            if key in seen:
                                continue
                            seen.add(key)
                            rows.append(
                                (
                                    word_key,
                                    normalized_part,
                                    sentence,
                                    "\n".join(str(item).strip() for item in definitions if str(item).strip()) or None,
                                    synset_id,
                                    rank,
                                )
                            )

    db.execute("DROP TABLE IF EXISTS wordnet_examples")
    db.execute(
        """
        CREATE TABLE wordnet_examples (
            word_key TEXT NOT NULL,
            part_group TEXT NOT NULL,
            example_sentence TEXT NOT NULL,
            definition TEXT,
            synset_id TEXT,
            sense_rank INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    db.executemany(
        """
        INSERT INTO wordnet_examples (
            word_key, part_group, example_sentence, definition, synset_id, sense_rank
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    db.execute("CREATE INDEX idx_wordnet_examples_word_part ON wordnet_examples(word_key, part_group, sense_rank)")
    db.execute(
        """
        INSERT INTO metadata (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        ("wordnet_lookup_signature", signature),
    )
    db.commit()


def ranked_wordnet_example_candidates(word: str, part_of_speech: str, limit: int = 20) -> list[sqlite3.Row]:
    if not word.strip() or not WORDNET_ZIP_PATH.exists():
        return []
    ensure_wordnet_lookup_index()
    part_group = wordnet_part_group(part_of_speech)
    if part_group not in {"n", "v", "a", "r"}:
        return []
    rows = get_db().execute(
        """
        SELECT example_sentence, definition, synset_id
        FROM wordnet_examples
        WHERE word_key = ? AND part_group = ?
        ORDER BY sense_rank ASC, length(example_sentence) ASC
        LIMIT 20
        """,
        (word.strip().lower(), part_group),
    ).fetchall()
    scored: list[tuple[tuple[int, int, int, int, str], sqlite3.Row]] = []
    for row in rows:
        sentence = row["example_sentence"]
        if not usable_wordnet_example(sentence, word):
            continue
        score = sentence_quality_score(sentence, word, part_of_speech, source="wordnet")
        if score[1] >= 6:
            continue
        scored.append((score, row))
    scored.sort(key=lambda item: item[0])
    return [row for _, row in scored[:limit]]


def lookup_wordnet_example(word: str, part_of_speech: str) -> sqlite3.Row | None:
    candidates = ranked_wordnet_example_candidates(word, part_of_speech, limit=1)
    return candidates[0] if candidates else None


def ensure_wiktionary_lookup_index(target_words: set[str] | None = None) -> None:
    path = wiktionary_jsonl_path()
    signature = wiktionary_source_signature()
    if not path or not signature:
        return

    db = get_db()
    existing = db.execute("SELECT value FROM metadata WHERE key = ?", ("wiktionary_lookup_signature",)).fetchone()
    table_exists = db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        ("wiktionary_examples",),
    ).fetchone()
    definition_table_exists = db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        ("wiktionary_definitions",),
    ).fetchone()
    indexed_table_exists = db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        ("wiktionary_indexed_words",),
    ).fetchone()
    needs_rebuild = not (table_exists and definition_table_exists and indexed_table_exists and existing and existing["value"] == signature)
    normalized_targets = {word.strip().lower() for word in target_words if word.strip()} if target_words is not None else None
    if target_words is not None and not normalized_targets:
        return
    if not needs_rebuild and normalized_targets is None:
        return

    if not needs_rebuild and normalized_targets is not None:
        placeholders = ",".join("?" for _ in normalized_targets)
        indexed_rows = db.execute(
            f"SELECT word_key FROM wiktionary_indexed_words WHERE word_key IN ({placeholders})",
            sorted(normalized_targets),
        ).fetchall()
        indexed_words = {row["word_key"] for row in indexed_rows}
        normalized_targets = normalized_targets - indexed_words
        if not normalized_targets:
            return

    if needs_rebuild:
        db.execute("DROP TABLE IF EXISTS wiktionary_examples")
        db.execute("DROP TABLE IF EXISTS wiktionary_definitions")
        db.execute("DROP TABLE IF EXISTS wiktionary_indexed_words")
        db.execute(
            """
            CREATE TABLE wiktionary_examples (
                word_key TEXT NOT NULL,
                part_group TEXT NOT NULL,
                example_sentence TEXT NOT NULL,
                definition TEXT,
                example_type TEXT,
                sense_tags TEXT,
                sense_rank INTEGER NOT NULL DEFAULT 0,
                example_rank INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        db.execute(
            """
            CREATE TABLE wiktionary_definitions (
                word_key TEXT NOT NULL,
                part_group TEXT NOT NULL,
                definition TEXT NOT NULL,
                sense_tags TEXT,
                sense_rank INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        db.execute(
            """
            CREATE TABLE wiktionary_indexed_words (
                word_key TEXT PRIMARY KEY
            )
            """
        )
        db.execute(
            """
            INSERT INTO metadata (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            ("wiktionary_lookup_signature", signature),
        )
    else:
        db.execute("DROP INDEX IF EXISTS idx_wiktionary_examples_word_part")
        db.execute("DROP INDEX IF EXISTS idx_wiktionary_definitions_word_part")

    words_to_index = normalized_targets

    rows: list[tuple[str, str, str, str | None, str | None, str | None, int, int]] = []
    definition_rows: list[tuple[str, str, str, str | None, int]] = []
    seen: set[tuple[str, str, str]] = set()
    seen_definitions: set[tuple[str, str, str]] = set()

    def flush_rows() -> None:
        nonlocal rows, definition_rows
        if rows:
            db.executemany(
                """
                INSERT INTO wiktionary_examples (
                    word_key, part_group, example_sentence, definition,
                    example_type, sense_tags, sense_rank, example_rank
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        if definition_rows:
            db.executemany(
                """
                INSERT INTO wiktionary_definitions (
                    word_key, part_group, definition, sense_tags, sense_rank
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                definition_rows,
            )
        rows = []
        definition_rows = []

    with path.open("rt", encoding="utf-8") as handle:
        for line in handle:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("lang_code") != "en":
                continue
            word_key = str(entry.get("word") or "").lower().strip()
            if words_to_index is not None and word_key not in words_to_index:
                continue
            part_group = normalize_wiktionary_pos(str(entry.get("pos") or ""))
            if not word_key or part_group not in {"n", "v", "adj", "adv", "pron", "prep", "conj", "interj", "num", "det", "phrase"}:
                continue
            senses = entry.get("senses") or []
            if not isinstance(senses, list):
                continue
            for sense_rank, sense in enumerate(senses):
                if not isinstance(sense, dict):
                    continue
                definition = "\n".join(str(item).strip() for item in sense.get("glosses", []) if str(item).strip()) or None
                sense_tags = ",".join(str(item).strip().lower() for item in sense.get("tags", []) if str(item).strip()) or None
                tag_set = {str(tag).strip().lower() for tag in sense.get("tags", []) if str(tag).strip()}
                if definition and not ({"archaic", "obsolete", "dated", "rare", "form-of"} & tag_set):
                    definition_key = (word_key, part_group, definition)
                    if definition_key not in seen_definitions:
                        seen_definitions.add(definition_key)
                        definition_rows.append((word_key, part_group, definition, sense_tags, sense_rank))
                examples = sense.get("examples") or []
                if not isinstance(examples, list):
                    continue
                for example in examples:
                    if not isinstance(example, dict):
                        continue
                    sentence = clean_wiktionary_example_text(str(example.get("text") or ""))
                    if not usable_wiktionary_example(sentence, word_key):
                        continue
                    key = (word_key, part_group, sentence)
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(
                        (
                            word_key,
                            part_group,
                            sentence,
                            definition,
                            str(example.get("type") or ""),
                            sense_tags,
                            sense_rank,
                            wiktionary_example_rank(example, sentence),
                        )
                    )
                    if len(rows) >= 5000:
                        flush_rows()
                if len(definition_rows) >= 5000:
                    flush_rows()
    flush_rows()
    if words_to_index is not None:
        db.executemany(
            "INSERT OR IGNORE INTO wiktionary_indexed_words (word_key) VALUES (?)",
            [(word,) for word in sorted(words_to_index)],
        )
    db.execute("CREATE INDEX idx_wiktionary_examples_word_part ON wiktionary_examples(word_key, part_group, sense_rank, example_rank)")
    db.execute("CREATE INDEX idx_wiktionary_definitions_word_part ON wiktionary_definitions(word_key, part_group, sense_rank)")
    db.commit()


def ranked_wiktionary_example_candidates(word: str, part_of_speech: str, limit: int = 8) -> list[sqlite3.Row]:
    if not word.strip() or not wiktionary_jsonl_path():
        return []
    ensure_wiktionary_lookup_index({word.strip().lower()})
    lookup_groups = wiktionary_lookup_groups(part_of_speech, word)
    placeholders = ",".join("?" for _ in lookup_groups)
    rows = get_db().execute(
        f"""
        SELECT example_sentence, definition, example_type, sense_tags, part_group
        FROM wiktionary_examples
        WHERE word_key = ? AND part_group IN ({placeholders})
        ORDER BY example_rank ASC, sense_rank ASC, length(example_sentence) ASC
        LIMIT 80
        """,
        (word.strip().lower(), *lookup_groups),
    ).fetchall()
    requested_group = normalize_part_group(part_of_speech)
    usable_rows: list[tuple[sqlite3.Row, set[str]]] = []
    for row in rows:
        sentence = row["example_sentence"]
        if not usable_wiktionary_example(sentence, word):
            continue
        tags = {tag.strip() for tag in str(row["sense_tags"] or "").split(",") if tag.strip()}
        usable_rows.append((row, tags))

    candidates = [
        (row, tags)
        for row, tags in usable_rows
        if not ({"archaic", "obsolete", "dated", "rare"} & tags)
    ]

    scored: list[tuple[tuple[int, int, bool, int, int, str], sqlite3.Row]] = []
    for row, tags in candidates:
        tag_penalty = 0
        if requested_group == "aux":
            if "auxiliary" in tags or "modal" in tags:
                tag_penalty -= 8
            else:
                tag_penalty += 12
        elif requested_group == "v" and ("auxiliary" in tags or "modal" in tags):
            tag_penalty += 8
        elif requested_group == "conj":
            if "conjunctive" in tags:
                tag_penalty -= 8
            else:
                tag_penalty += 10
        elif requested_group == "phrase" and row["part_group"] != "phrase":
            tag_penalty += 1
        if "obsolete" in tags:
            tag_penalty += 18
        if "archaic" in tags:
            tag_penalty += 12
        if "dated" in tags:
            tag_penalty += 8
        if "rare" in tags:
            tag_penalty += 5
        score = sentence_quality_score(sentence, word, part_of_speech, source="wiktionary")
        if score[1] > 10:
            continue
        short_sentence_penalty = 0 if english_word_count(sentence) >= 6 else 1
        ranked_score = (tag_penalty, short_sentence_penalty, row["example_type"] == "quotation", score[2], score[3], score[4])
        scored.append((ranked_score, row))
    scored.sort(key=lambda item: item[0])
    return [row for _, row in scored[:limit]]


def lookup_wiktionary_example(word: str, part_of_speech: str) -> sqlite3.Row | None:
    candidates = ranked_wiktionary_example_candidates(word, part_of_speech, limit=1)
    return candidates[0] if candidates else None


def lookup_wiktionary_definition(word: str, part_of_speech: str) -> str | None:
    if not word.strip() or not wiktionary_jsonl_path():
        return None
    ensure_wiktionary_lookup_index({word.strip().lower()})
    lookup_groups = wiktionary_lookup_groups(part_of_speech, word)
    placeholders = ",".join("?" for _ in lookup_groups)
    rows = get_db().execute(
        f"""
        SELECT definition, sense_tags, part_group, sense_rank
        FROM wiktionary_definitions
        WHERE word_key = ? AND part_group IN ({placeholders})
        ORDER BY sense_rank ASC, length(definition) ASC
        LIMIT 12
        """,
        (word.strip().lower(), *lookup_groups),
    ).fetchall()
    if not rows:
        return None
    definitions: list[str] = []
    seen: set[str] = set()
    for row in rows:
        tags = {tag.strip() for tag in str(row["sense_tags"] or "").split(",") if tag.strip()}
        if {"archaic", "obsolete", "dated", "rare", "form-of"} & tags:
            continue
        definition = str(row["definition"] or "").strip()
        if not definition or definition in seen:
            continue
        seen.add(definition)
        definitions.append(definition)
        if len(definitions) >= 4:
            break
    return "\n".join(definitions) if definitions else None


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

    if len(candidates) < top_n:
        for row in ranked_wordnet_example_candidates(word, part_of_speech, limit=top_n):
            sentence = str(row["example_sentence"] or "").strip()
            if not sentence or sentence in seen_sentences:
                continue
            seen_sentences.add(sentence)
            candidates.append(row)
            if len(candidates) >= top_n:
                break

    return random.choice(candidates[:top_n]) if candidates else None


def lookup_wordnet_definition(word: str, part_of_speech: str) -> str | None:
    lookup = lookup_wordnet_example(word, part_of_speech)
    if lookup and lookup["definition"]:
        return lookup["definition"]
    return None


def has_dictionary_example_support(word: str, part_of_speech: str) -> bool:
    return lookup_wiktionary_example(word, part_of_speech) is not None or lookup_wordnet_example(word, part_of_speech) is not None


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


def unsupported_dictionary_entries(start: int = 1, end: int = 100) -> tuple[list[sqlite3.Row], dict[str, int]]:
    total = get_db().execute(
        "SELECT COUNT(*) AS total FROM words WHERE library_id = ?",
        (get_active_library_id(),),
    ).fetchone()["total"]
    if total:
        start = max(1, min(start, int(total)))
        end = max(start, min(end, int(total)))
    else:
        start = 0
        end = 0
    rows = fetch_word_range(start, end, "id, word, part_of_speech, meaning, status") if total else []
    if wiktionary_jsonl_path():
        ensure_wiktionary_lookup_index({str(row["word"]).strip().lower() for row in rows})
    unsupported = [
        row for row in rows
        if not has_dictionary_example_support(str(row["word"]), str(row["part_of_speech"]))
    ]
    word_range = {
        "start": start,
        "end": end,
        "count": len(rows),
        "total": total,
        "prev_start": max(1, start - max(1, end - start + 1)),
        "prev_end": max(1, start - 1),
        "next_start": min(total if total else 1, end + 1),
        "next_end": min(total if total else 1, end + max(1, end - start + 1)),
        "has_prev": bool(total and start > 1),
        "has_next": bool(total and end < total),
    }
    return unsupported, word_range


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
    db = get_db()
    if library_id is None:
        library_id = get_active_library_id()
    inserted = 0
    updated = 0
    skipped = 0

    for entry in entries:
        entry["part_of_speech"] = normalize_user_pos(str(entry["part_of_speech"]))
        existing = db.execute(
            "SELECT id FROM words WHERE library_id = ? AND word = ? AND part_of_speech = ?",
            (library_id, entry["word"], entry["part_of_speech"]),
        ).fetchone()
        if existing:
            if not update_existing:
                skipped += 1
                continue
            db.execute(
                """
                UPDATE words
                SET meaning = ?,
                    example_sentence = COALESCE(?, example_sentence),
                    example_translation = COALESCE(?, example_translation),
                    phonetic = COALESCE(?, phonetic),
                    definition = COALESCE(?, definition),
                    frequency = COALESCE(?, frequency),
                    source = COALESCE(?, source),
                    source_tags = COALESCE(?, source_tags),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND library_id = ?
                """,
                (
                    entry["meaning"],
                    entry.get("example_sentence"),
                    entry.get("example_translation"),
                    entry.get("phonetic"),
                    entry.get("definition"),
                    entry.get("frequency"),
                    entry.get("source"),
                    entry.get("source_tags"),
                    existing["id"],
                    library_id,
                ),
            )
            updated += 1
        else:
            db.execute(
                """
                INSERT INTO words (
                    library_id, word, part_of_speech, meaning, example_sentence, example_translation,
                    phonetic, definition, frequency, source, source_tags
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    library_id,
                    entry["word"],
                    entry["part_of_speech"],
                    entry["meaning"],
                    entry.get("example_sentence"),
                    entry.get("example_translation"),
                    entry.get("phonetic"),
                    entry.get("definition"),
                    entry.get("frequency"),
                    entry.get("source"),
                    entry.get("source_tags"),
                ),
            )
            inserted += 1

    db.commit()
    return inserted, updated, skipped


def fetch_words(status: str | None = None) -> list[sqlite3.Row]:
    db = get_db()
    library_id = get_active_library_id()
    if status is None:
        return db.execute(
            """
            SELECT * FROM words
            WHERE library_id = ?
            ORDER BY id ASC
            """,
            (library_id,),
        ).fetchall()
    return db.execute(
        """
        SELECT * FROM words
        WHERE library_id = ? AND status = ?
        ORDER BY id ASC
        """,
        (library_id, status),
    ).fetchall()


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
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    library_id = get_active_library_id()
    rows = get_db().execute(
        f"SELECT * FROM words WHERE library_id = ? AND id IN ({placeholders}) ORDER BY id ASC",
        [library_id, *ids],
    ).fetchall()
    by_id = {row["id"]: row for row in rows}
    return [by_id[word_id] for word_id in ids if word_id in by_id]


def fetch_word(word_id: int) -> sqlite3.Row | None:
    return get_db().execute(
        "SELECT * FROM words WHERE id = ? AND library_id = ?",
        (word_id, get_active_library_id()),
    ).fetchone()


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


@app.route("/")
def index():
    edit_mode = request.args.get("edit") == "1"
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
    return render_template(
        "index.html",
        words=words,
        edit_mode=edit_mode,
        pagination=pagination,
        sort_modes={"frequency": "Frequency", "alpha": "A-Z"},
        comparable_libraries=comparable_libraries,
        part_of_speech_options=PART_OF_SPEECH_OPTIONS,
        add_word_messages=session.pop("add_word_messages", []),
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
        flash("Choose a valid library.", "error")
        return redirect(url_for("index"))

    if not fetch_library(library_id):
        flash("That library does not exist.", "error")
        return redirect(url_for("index"))

    session["active_library_id"] = library_id
    clear_practice_session()
    return redirect(url_for("index"))


@app.post("/libraries/add")
def add_library():
    name = request.form.get("library_name", "").strip()
    if not name:
        flash("Library name is required.", "error")
        return redirect(url_for("index"))

    try:
        cursor = get_db().execute("INSERT INTO libraries (name) VALUES (?)", (name,))
        get_db().commit()
        session["active_library_id"] = int(cursor.lastrowid)
        clear_practice_session()
        flash("Library created.", "success")
    except sqlite3.IntegrityError:
        flash("A library with that name already exists.", "error")

    return redirect(url_for("index"))


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
    flash(f"Review target set to {target_count} successful reviews.", "success")
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
    flash(f"Wrong-word target set to {target_count} cumulative correct answers.", "success")
    return redirect_back()


@app.post("/import")
def import_words():
    uploaded = request.files.get("word_file")
    if not uploaded or uploaded.filename == "":
        flash("Please choose a TXT or CSV file.", "error")
        return redirect(url_for("index"))

    try:
        entries, errors = parse_word_file(uploaded.filename, uploaded.read())
    except UnicodeDecodeError:
        flash("Import failed: please use UTF-8 encoded TXT or CSV files.", "error")
        return redirect(url_for("index"))

    enriched = 0
    if entries:
        enriched = enrich_entries_from_ecdict(entries)
        inserted, updated, _skipped = import_entries(entries)
        suffix = f" ECDICT filled {enriched} entries." if enriched else ""
        flash(f"Imported {inserted} new words and updated {updated} existing entries.{suffix}", "success")
    if errors:
        preview = "; ".join(errors[:3])
        suffix = "" if len(errors) <= 3 else f" And {len(errors) - 3} more."
        flash(f"Some rows were skipped: {preview}.{suffix}", "error")
    if not entries and not errors:
        flash("No usable words were found.", "error")

    return redirect(url_for("index"))


@app.post("/examples/fill")
def fill_auto_examples():
    if not WORDNET_ZIP_PATH.exists() and not wiktionary_jsonl_path():
        flash(
            "Auto example sources were not found. Put Wiktionary JSONL in the project root or resources/wiktionary, or WordNet in resources/wordnet.",
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
        flash(f"No words found in range {start}-{end}.", "success")
    else:
        action = "refreshed from top-8 suitable candidates" if mode == "refresh" else "filled with the best candidates"
        flash(
            f"Auto examples {action}: updated {matched} example sentences after checking {checked} words in range {start}-{end}.",
            "success",
        )
    return redirect(url_for("index", edit=1))


@app.post("/import/ecdict")
def import_ecdict():
    uploaded = request.files.get("ecdict_file")
    if not uploaded or uploaded.filename == "":
        flash("Please choose an ECDICT CSV file.", "error")
        return redirect(url_for("index", edit=1))

    try:
        grouped, errors = parse_ecdict_csv(uploaded.read())
    except UnicodeDecodeError:
        flash("ECDICT import failed: please use UTF-8 encoded CSV.", "error")
        return redirect(url_for("index", edit=1))

    if errors:
        flash(" ".join(errors), "error")
        return redirect(url_for("index", edit=1))

    summaries = []
    first_library_id = None
    for library_name, entries in grouped.items():
        library_id = get_or_create_library(library_name)
        reset_ecdict_library(library_id)
        if first_library_id is None:
            first_library_id = library_id
        inserted, updated, _skipped = import_entries(entries, library_id=library_id)
        summaries.append(f"{library_name}: {inserted} added, {updated} updated")

    if first_library_id is not None:
        session["active_library_id"] = first_library_id
        clear_practice_session()

    flash("ECDICT import complete. " + "; ".join(summaries), "success")
    return redirect(url_for("index"))


@app.post("/presets/ecdict")
def create_ecdict_preset():
    preset_key = request.form.get("preset_key", "").strip().lower()
    preset = ECDICT_PRESET_LIBRARIES.get(preset_key)
    if not preset:
        flash("Choose a valid preset library.", "error")
        return redirect(url_for("index"))

    try:
        raw = load_ecdict_data()
    except Exception as exc:
        flash(
            "Could not load ECDICT data. Add resources/ecdict.csv when packaging, or use Edit library -> Import ECDICT with a local ecdict.csv file.",
            "error",
        )
        return redirect(url_for("index"))

    grouped, errors = parse_ecdict_csv(raw, presets={preset_key: preset})
    if errors:
        flash(" ".join(errors), "error")
        return redirect(url_for("index"))

    library_name = str(preset["name"])
    entries = grouped.get(library_name, [])
    if not entries:
        flash(f"No words found for {library_name} in ECDICT.", "error")
        return redirect(url_for("index"))

    library_id = get_or_create_library(library_name)
    reset_ecdict_library(library_id)
    inserted, updated, _skipped = import_entries(entries, library_id=library_id)
    session["active_library_id"] = library_id
    clear_practice_session()
    flash(f"{library_name} library rebuilt: {inserted} added, {updated} updated.", "success")
    return redirect(url_for("index"))


@app.post("/preview")
def create_preview():
    try:
        requested_count = int(request.form.get("study_count", "10"))
    except ValueError:
        requested_count = 10
    requested_count = max(1, min(requested_count, 200))
    prompt_mode = prompt_mode_from_form(allow_cloze=True)
    with_cloze = with_cloze_from_form(allow_cloze=True)

    rows = get_db().execute(
        """
        SELECT id, word, example_sentence FROM words
        WHERE library_id = ? AND status = ?
        ORDER BY
            CASE WHEN frequency IS NULL THEN 1 ELSE 0 END ASC,
            frequency ASC,
            id ASC
        LIMIT ?
        """,
        (get_active_library_id(), STATUS_NEW, requested_count),
    ).fetchall()
    ids = [int(row["id"]) for row in rows]
    if not ids:
        flash("There are no new words to study. Import words or review wrong words.", "error")
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
        flash("No practice session is selected.", "error")
        return redirect(url_for("index"))
    return render_template(
        "preview.html",
        words=words,
        prompt_mode=session.get("prompt_mode", PROMPT_MIXED),
        cloze_scope=cloze_scope_from_session(),
        show_phonetic=bool(session.get("show_phonetic", True)),
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
        flash("No words are due for review right now.", "error")
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
        flash("No words are due for review right now.", "error")
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
    return redirect(url_for("practice"))


@app.route("/practice")
def practice():
    ids = [int(word_id) for word_id in session.get("practice_ids", [])]
    index = int(session.get("practice_index", 0))
    mode = session.get("practice_mode", "normal")
    if not ids:
        flash("No active practice session.", "error")
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

    word = fetch_word(ids[index])
    if word is None:
        session["practice_index"] = index + 1
        return redirect(url_for("practice"))

    cloze_text = cloze_prompt(word["example_sentence"], word["word"])
    prompt_mode = effective_prompt_mode(word)
    return render_template(
        "practice.html",
        word=word,
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
        cloze_answer=cloze_answer(word["example_sentence"], word["word"]),
        missed_count=len(session.get("missed_ids", [])),
        practice_round=int(session.get("practice_round", 1)),
        hide_global_stats=True,
        **base_context(),
    )


@app.post("/practice/submit")
def submit_answer():
    ids = [int(word_id) for word_id in session.get("practice_ids", [])]
    index = int(session.get("practice_index", 0))
    if index >= len(ids):
        return redirect(url_for("session_done"))

    word = fetch_word(ids[index])
    if word is None:
        return redirect(url_for("practice"))

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

        session["awaiting_next"] = True
        session["last_result"] = answer_feedback(word, answer, False)
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

        session["awaiting_next"] = True
        session["last_result"] = answer_feedback(word, answer, False)
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

        session["awaiting_next"] = True
        session["last_result"] = answer_feedback(word, answer, False)
        return redirect(url_for("practice"))

    session["awaiting_next"] = True
    session["last_result"] = form_hint_feedback or answer_feedback(word, answer, is_correct)
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
    return redirect(url_for("practice"))


@app.route("/session-done")
def session_done():
    mode = session.get("practice_mode", "normal")
    missed_words = []
    if mode == "normal":
        missed_words = fetch_words_by_ids([int(word_id) for word_id in session.get("missed_ids", [])])

    if not missed_words or mode == "review":
        clear_practice_session()

    return render_template("session_done.html", mode=mode, missed_words=missed_words, **base_context())


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
        flash(f"Added {len(selected_ids)} words to wrong words.", "success")
        return redirect(url_for("wrong"))

    flash("Session saved. No words were added to wrong words.", "success")
    return redirect(url_for("index"))


@app.route("/learned")
def learned():
    return render_template("learned.html", words=fetch_words(STATUS_LEARNED), **base_context())


@app.route("/wrong")
def wrong():
    return render_template("wrong.html", words=fetch_words(STATUS_WRONG), **base_context())


@app.post("/words/<int:word_id>/edit")
def edit_word(word_id: int):
    existing_word = fetch_word(word_id)
    if existing_word is None:
        flash("Word not found.", "error")
        return redirect(request.referrer or url_for("index"))

    word = request.form.get("word", "").strip()
    part_of_speech = normalize_user_pos(request.form.get("part_of_speech", "").strip())
    raw_meaning = request.form.get("meaning", "").strip()
    meaning = raw_meaning or existing_word["meaning"]
    example_sentence = request.form.get("example_sentence", "").strip()

    if not word or not part_of_speech or not meaning:
        flash("Word, part of speech, and meaning are required.", "error")
        return redirect(request.referrer or url_for("index"))
    if example_sentence and not valid_example_sentence(example_sentence, word):
        flash("Example sentence was not saved because it does not contain the target word.", "error")
        return redirect(request.referrer or url_for("index", edit=1))

    entry = {"word": word, "part_of_speech": part_of_speech, "meaning": meaning}
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
                entry.get("phonetic"),
                entry.get("definition"),
                entry.get("frequency"),
                entry.get("source"),
                entry.get("source_tags"),
                word_id,
                get_active_library_id(),
            ),
        )
        get_db().commit()
        flash("Word updated.", "success")
    except sqlite3.IntegrityError:
        flash("Update failed: that word and part of speech already exist.", "error")

    return redirect(request.referrer or url_for("index"))


@app.post("/words/add")
def add_word():
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
            errors.append(f"Row {index + 1}: word is required.")
            continue
        if meaning and not part_of_speech:
            errors.append(f"Row {index + 1}: part of speech is required when a custom meaning is provided.")
            continue
        if example_sentence and not valid_example_sentence(example_sentence, word):
            errors.append(f"Row {index + 1}: example sentence must contain the target word.")
            continue
        row_entries: list[dict[str, object]] = []
        if part_of_speech and meaning:
            row_entries = [{"word": word, "part_of_speech": part_of_speech, "meaning": meaning}]
        else:
            if ecdict_raw is None:
                try:
                    ecdict_raw = load_ecdict_data()
                except Exception:
                    ecdict_raw = b""
            row_entries = ecdict_entries_for_word(word, part_of_speech, meaning, raw=ecdict_raw or None)
            if not row_entries:
                errors.append(f"Row {index + 1}: '{word}' was not found in ECDICT. Add part of speech and Chinese meaning manually.")
                continue
        for entry in row_entries:
            if example_sentence:
                entry["example_sentence"] = example_sentence
            entries.append(entry)

    if not entries:
        message = " ".join(errors[:3]) if errors else "Add at least one word row."
        session["add_word_messages"] = [("error", message)]
        return redirect(url_for("index", edit=1))

    enriched = enrich_entries_from_ecdict(entries)
    inserted, updated, skipped = import_entries(entries, update_existing=False)
    suffix = f" ECDICT filled {enriched} entries." if enriched else ""
    messages = []
    if inserted:
        messages.append(("success", f"Added {inserted} new words.{suffix}"))
    if skipped:
        messages.append(("success", f"{skipped} existing entries were already in this library and were left unchanged."))
    if errors:
        messages.append(("error", f"These rows were not added: {' '.join(errors[:3])}"))
    if not messages:
        messages.append(("error", "No new words were added."))
    session["add_word_messages"] = messages
    return redirect(url_for("index", edit=1))


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
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND library_id = ?
                """,
                (
                    update["word"],
                    update["part_of_speech"],
                    update["meaning"],
                    update["example_sentence"],
                    update["id"],
                    get_active_library_id(),
                ),
            )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        flash("Save failed: duplicate word and part of speech in this library.", "error")
        return redirect(url_for("index", **edit_redirect_args))

    flash(f"Saved {len(updates)} words.", "success")
    return redirect(url_for("index"))


@app.post("/words/<int:word_id>/delete")
def delete_word(word_id: int):
    deleted = delete_word_ids({word_id}, get_active_library_id())
    if deleted:
        flash("Word deleted.", "success")
    else:
        flash("Word was not found in this library.", "error")
    return redirect(request.referrer or url_for("index"))


@app.post("/words/bulk-delete")
def bulk_delete_words():
    selected_ids = {int(word_id) for word_id in request.form.getlist("word_ids") if word_id.isdigit()}
    page = request.form.get("page", "1")
    search = request.form.get("q", "").strip()
    sort_mode = request.form.get("sort", SORT_FREQUENCY)
    if sort_mode not in LIBRARY_SORT_MODES:
        sort_mode = SORT_FREQUENCY
    redirect_args = {"edit": 1, "page": page, "sort": sort_mode}
    if search:
        redirect_args["q"] = search
    if not selected_ids:
        flash("Select at least one word to delete.", "error")
        return redirect(url_for("index", **redirect_args))

    deleted = delete_word_ids(selected_ids, get_active_library_id())
    flash(f"Deleted {deleted} selected words.", "success")
    return redirect(url_for("index", **redirect_args))


@app.post("/libraries/clean/preview")
def preview_unsupported_entries():
    start, end = parse_word_range("cleanup", default_start=1, default_end=100, max_span=2000)
    unsupported, word_range = unsupported_dictionary_entries(start=start, end=end)
    session["unsupported_cleanup_ids"] = [int(row["id"]) for row in unsupported]
    session["unsupported_cleanup_start"] = word_range["start"]
    session["unsupported_cleanup_end"] = word_range["end"]
    return render_template(
        "cleanup_preview.html",
        unsupported_words=unsupported,
        cleanup_range=word_range,
        **base_context(),
    )


@app.post("/libraries/clean/confirm")
def confirm_unsupported_cleanup():
    stored_ids = {int(word_id) for word_id in session.get("unsupported_cleanup_ids", [])}
    if not stored_ids:
        flash("Run a cleanup preview first.", "error")
        return redirect(url_for("index", edit=1))
    selected_ids = {int(word_id) for word_id in request.form.getlist("word_ids") if word_id.isdigit()}
    selected_ids = selected_ids & stored_ids
    if not selected_ids:
        flash("Select at least one unsupported entry to delete.", "error")
        return redirect(url_for("index", edit=1))

    placeholders = ",".join("?" for _ in selected_ids)
    rows = get_db().execute(
        f"""
        SELECT id, word, part_of_speech
        FROM words
        WHERE library_id = ?
          AND id IN ({placeholders})
        """,
        [get_active_library_id(), *sorted(selected_ids)],
    ).fetchall()
    if wiktionary_jsonl_path():
        ensure_wiktionary_lookup_index({str(row["word"]).strip().lower() for row in rows})
    still_unsupported = {
        int(row["id"]) for row in rows
        if not has_dictionary_example_support(str(row["word"]), str(row["part_of_speech"]))
    }
    deleted = delete_word_ids(still_unsupported, get_active_library_id()) if still_unsupported else 0
    start = int(session.get("unsupported_cleanup_start", 1))
    end = int(session.get("unsupported_cleanup_end", 100))
    session.pop("unsupported_cleanup_ids", None)
    session.pop("unsupported_cleanup_start", None)
    session.pop("unsupported_cleanup_end", None)
    flash(f"Removed {deleted} entries without Wiktionary or WordNet example support.", "success")
    unsupported, word_range = unsupported_dictionary_entries(start=start, end=end)
    session["unsupported_cleanup_ids"] = [int(row["id"]) for row in unsupported]
    session["unsupported_cleanup_start"] = word_range["start"]
    session["unsupported_cleanup_end"] = word_range["end"]
    return render_template(
        "cleanup_preview.html",
        unsupported_words=unsupported,
        cleanup_range=word_range,
        **base_context(),
    )


@app.post("/libraries/exclude")
def exclude_library_words():
    try:
        source_library_id = int(request.form.get("source_library_id", ""))
    except ValueError:
        flash("Choose a library to exclude.", "error")
        return redirect(url_for("index", edit=1))

    active_library_id = get_active_library_id()
    if source_library_id == active_library_id or not fetch_library(source_library_id):
        flash("Choose a different existing library to exclude.", "error")
        return redirect(url_for("index", edit=1))

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
        flash("No overlapping words were found.", "success")
        return redirect(url_for("index", edit=1))

    deleted = delete_word_ids(word_ids, active_library_id)
    source_library = fetch_library(source_library_id)
    scope_label = "word only" if match_scope == "word" else "word + part"
    flash(f"Excluded {deleted} words also found in {source_library['name']} ({scope_label}).", "success")
    return redirect(url_for("index", edit=1))


@app.post("/words/clear")
def clear_words():
    get_db().execute("DELETE FROM words WHERE library_id = ?", (get_active_library_id(),))
    get_db().commit()
    clear_practice_session()
    flash("All words and learning records have been cleared.", "success")
    return redirect(url_for("index"))


@app.post("/wrong/start")
def start_wrong_review():
    due_count = wrong_due_count()
    if due_count <= 0:
        flash("No wrong words are due for review today.", "error")
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
        flash("There are no wrong words to review.", "error")
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
    return redirect(url_for("practice"))


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
    app.run(host="127.0.0.1", debug=os.environ.get("TYPENG_DEBUG") == "1")
