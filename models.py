"""Pure domain logic and constants for TypEng.

This module contains functions that do not depend on Flask (request, session,
g), the database connection (get_db), or the app configuration (APP_ROOT,
DATA_DIR, etc.). They operate only on their arguments and module-level
constants, making them trivially testable and reusable.

Extracted from app.py as the first step of the architecture cleanup described
in feedback.md.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timedelta
from math import ceil
from pathlib import Path

try:
    from opencc import OpenCC
except ImportError:
    OpenCC = None  # type: ignore[assignment]

OPENCC_T2S = OpenCC("t2s") if OpenCC is not None else None

# ---------------------------------------------------------------------------
# Application constants
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Cloze / irregular forms
# ---------------------------------------------------------------------------

CLOZE_IRREGULAR_FORMS: dict[str, set[str]] = {
    "be": {"am", "is", "are", "was", "were", "been", "being"},
    "have": {"has", "had", "having"},
    "do": {"does", "did", "done", "doing"},
    "go": {"goes", "went", "gone", "going"},
    "say": {"says", "said", "saying"},
    "get": {"gets", "got", "gotten", "getting"},
    "make": {"makes", "made", "making"},
    "know": {"knows", "knew", "known", "knowing"},
    "think": {"thinks", "thought", "thinking"},
    "take": {"takes", "took", "taken", "taking"},
    "see": {"sees", "saw", "seen", "seeing"},
    "come": {"comes", "came", "come", "coming"},
    "want": {"wants", "wanted", "wanting"},
    "use": {"uses", "used", "using"},
    "find": {"finds", "found", "finding"},
    "give": {"gives", "gave", "given", "giving"},
    "tell": {"tells", "told", "telling"},
    "work": {"works", "worked", "working"},
    "call": {"calls", "called", "calling"},
    "try": {"tries", "tried", "trying"},
    "ask": {"asks", "asked", "asking"},
    "need": {"needs", "needed", "needing"},
    "feel": {"feels", "felt", "feeling"},
    "become": {"becomes", "became", "become", "becoming"},
    "leave": {"leaves", "left", "leaving"},
    "put": {"puts", "put", "putting"},
    "mean": {"means", "meant", "meaning"},
    "keep": {"keeps", "kept", "keeping"},
    "let": {"lets", "let", "letting"},
    "begin": {"begins", "began", "begun", "beginning"},
    "seem": {"seems", "seemed", "seeming"},
    "help": {"helps", "helped", "helping"},
    "show": {"shows", "showed", "shown", "showing"},
    "hear": {"hears", "heard", "hearing"},
    "play": {"plays", "played", "playing"},
    "run": {"runs", "ran", "run", "running"},
    "move": {"moves", "moved", "moving"},
    "live": {"lives", "lived", "living"},
    "believe": {"believes", "believed", "believing"},
    "hold": {"holds", "held", "holding"},
    "bring": {"brings", "brought", "bringing"},
    "happen": {"happens", "happened", "happening"},
    "write": {"writes", "wrote", "written", "writing"},
    "provide": {"provides", "provided", "providing"},
    "sit": {"sits", "sat", "sitting"},
    "stand": {"stands", "stood", "standing"},
    "lose": {"loses", "lost", "losing"},
    "pay": {"pays", "paid", "paying"},
    "meet": {"meets", "met", "meeting"},
    "include": {"includes", "included", "including"},
    "continue": {"continues", "continued", "continuing"},
    "set": {"sets", "set", "setting"},
    "learn": {"learns", "learned", "learnt", "learning"},
    "change": {"changes", "changed", "changing"},
    "lead": {"leads", "led", "leading"},
    "understand": {"understands", "understood", "understanding"},
    "watch": {"watches", "watched", "watching"},
    "follow": {"follows", "followed", "following"},
    "stop": {"stops", "stopped", "stopping"},
    "create": {"creates", "created", "creating"},
    "speak": {"speaks", "spoke", "spoken", "speaking"},
    "read": {"reads", "read", "reading"},
    "allow": {"allows", "allowed", "allowing"},
    "add": {"adds", "added", "adding"},
    "spend": {"spends", "spent", "spending"},
    "grow": {"grows", "grew", "grown", "growing"},
    "open": {"opens", "opened", "opening"},
    "walk": {"walks", "walked", "walking"},
    "win": {"wins", "won", "winning"},
    "offer": {"offers", "offered", "offering"},
    "remember": {"remembers", "remembered", "remembering"},
    "love": {"loves", "loved", "loving"},
    "consider": {"considers", "considered", "considering"},
    "appear": {"appears", "appeared", "appearing"},
    "buy": {"buys", "bought", "buying"},
    "wait": {"waits", "waited", "waiting"},
    "serve": {"serves", "served", "serving"},
    "die": {"dies", "died", "dying"},
    "send": {"sends", "sent", "sending"},
    "expect": {"expects", "expected", "expecting"},
    "build": {"builds", "built", "building"},
    "stay": {"stays", "stayed", "staying"},
    "fall": {"falls", "fell", "fallen", "falling"},
    "cut": {"cuts", "cut", "cutting"},
    "reach": {"reaches", "reached", "reaching"},
    "kill": {"kills", "killed", "killing"},
    "remain": {"remains", "remained", "remaining"},
    "suggest": {"suggests", "suggested", "suggesting"},
    "raise": {"raises", "raised", "raising"},
    "pass": {"passes", "passed", "passing"},
    "sell": {"sells", "sold", "selling"},
    "require": {"requires", "required", "requiring"},
    "report": {"reports", "reported", "reporting"},
    "decide": {"decides", "decided", "deciding"},
    "pull": {"pulls", "pulled", "pulling"},
    "break": {"breaks", "broke", "broken", "breaking"},
    "receive": {"receives", "received", "receiving"},
    "agree": {"agrees", "agreed", "agreeing"},
    "hit": {"hits", "hit", "hitting"},
    "produce": {"produces", "produced", "producing"},
    "eat": {"eats", "ate", "eaten", "eating"},
    "cover": {"covers", "covered", "covering"},
    "catch": {"catches", "caught", "catching"},
    "draw": {"draws", "drew", "drawn", "drawing"},
    "choose": {"chooses", "chose", "chosen", "choosing"},
    "fight": {"fights", "fought", "fighting"},
    "drink": {"drinks", "drank", "drunk", "drinking"},
    "drive": {"drives", "drove", "driven", "driving"},
    "fly": {"flies", "flew", "flown", "flying"},
    "ride": {"rides", "rode", "ridden", "riding"},
    "sing": {"sings", "sang", "sung", "singing"},
    "sleep": {"sleeps", "slept", "sleeping"},
    "swim": {"swims", "swam", "swum", "swimming"},
    "teach": {"teaches", "taught", "teaching"},
    "throw": {"throws", "threw", "thrown", "throwing"},
    "wear": {"wears", "wore", "worn", "wearing"},
    "lie": {"lies", "lay", "lain", "lying"},
    "lay": {"lays", "laid", "laying"},
    "rise": {"rises", "rose", "risen", "rising"},
    "shake": {"shakes", "shook", "shaken", "shaking"},
    "shoot": {"shoots", "shot", "shooting"},
    "steal": {"steals", "stole", "stolen", "stealing"},
    "stick": {"sticks", "stuck", "sticking"},
    "strike": {"strikes", "struck", "stricken", "striking"},
    "swear": {"swears", "swore", "sworn", "swearing"},
    "sweep": {"sweeps", "swept", "sweeping"},
    "tear": {"tears", "tore", "torn", "tearing"},
    "wake": {"wakes", "woke", "woken", "waking"},
    "freeze": {"freezes", "froze", "frozen", "freezing"},
    "hide": {"hides", "hid", "hidden", "hiding"},
    "ring": {"rings", "rang", "rung", "ringing"},
    "sink": {"sinks", "sank", "sunk", "sinking"},
    "spin": {"spins", "spun", "spinning"},
    "spread": {"spreads", "spread", "spreading"},
    "spring": {"springs", "sprang", "sprung", "springing"},
    "wind": {"winds", "wound", "winding"},
}

# ---------------------------------------------------------------------------
# POS / display helpers
# ---------------------------------------------------------------------------

PART_OF_SPEECH_OPTIONS: list[tuple[str, str]] = [
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
    ("phrase", "phrase"),
]

ECDICT_POS_MAP: dict[str, str] = {
    "n": "n", "noun": "n", "pl": "n", "plural": "n",
    "v": "v", "vi": "v", "vt": "v", "verb": "v",
    "a": "adj", "adj": "adj", "adjective": "adj", "s": "adj",
    "ad": "adv", "adv": "adv", "adverb": "adv",
    "pron": "pron", "pronoun": "pron",
    "prep": "prep", "preposition": "prep",
    "conj": "conj", "conjunction": "conj",
    "int": "interj", "interj": "interj", "interjection": "interj",
    "abbr": "abbr",
    "num": "num",
    "aux": "aux",
    "pref": "pref", "prefix": "pref",
}

ECDICT_PRESET_LIBRARIES: dict[str, dict[str, object]] = {
    "zk": {"name": "中考", "tags": {"zk"}},
    "gk": {"name": "高考", "tags": {"gk"}},
    "cet4": {"name": "CET4", "tags": {"cet4"}},
    "cet6": {"name": "CET6", "tags": {"cet6"}},
    "kaoyan": {"name": "考研", "tags": {"ky", "kaoyan"}},
    "ielts": {"name": "IELTS", "tags": {"ielts"}},
    "toefl": {"name": "TOEFL", "tags": {"toefl"}},
    "gre": {"name": "GRE", "tags": {"gre"}},
}

ECDICT_POS_PREFIX_RE = re.compile(r"^\s*([A-Za-z][A-Za-z-]*)\.\s*(.*)$")
ECDICT_DEFINITION_SPLIT_RE = re.compile(r"\s+(?=(?:n|v|s|a|r|adj|adv)\.\s)")
ECDICT_DEFINITION_POS_RE = re.compile(
    r"\s*[;；]\s*(?=(?:n|v|adj|adv|pron|prep|conj|interj|abbr|num|phrase)\.\s)",
    re.IGNORECASE,
)

BLOCKED_EXAMPLE_WORDS: set[str] = {
    "gonna", "wanna", "ain't", "y'all", "dunno", "gimme", "lemme",
    "kinda", "sorta", "outta", "hafta", "woulda", "coulda", "shoulda",
    "musta", "mighta", "lotta", "lotsa",
}

NOTABLE_EXAMPLE_TAGS: dict[str, str] = {
    "archaic": "archaic usage",
    "obsolete": "obsolete usage",
    "dated": "dated usage",
    "rare": "rare usage",
}

DEFINITION_DISPLAY_POS_RE = re.compile(
    r"\s*[;；]\s*(?=(?:n|v|adj|adv|pron|prep|conj|interj|abbr|num|aux|phrase)\.\s)",
    re.IGNORECASE,
)

TRADITIONAL_TO_SIMPLIFIED = str.maketrans(
    {
        "國": "国", "發": "发", "線": "线",
        "戲": "戏", "遊": "游", "讓": "让",
        "紅": "红", "約": "约", "買": "买",
        "罐": "罐", "藥": "药", "電": "电",
        "標": "标", "記": "记", "訂": "订",
        "語": "语", "說": "说", "讀": "读",
        "訓": "训", "練": "练", "測": "测",
        "試": "试", "錢": "钱", "鍥": "锥",
        "銘": "铭", "鎖": "锁", "鍋": "锅",
        "鐵": "铁", "銀": "银", "銃": "铨",
        "銅": "铜", "鐘": "钟", "鈍": "钓",
        "鈴": "铃", "鐐": "镐", "錦": "锦",
        "錫": "锡", "鏡": "镜", "鎧": "埠",
        "鏟": "锤", "鑼": "镭", "金": "金",
        "鞋": "鞋", "靴": "靴", "靶": "靶",
        "鞭": "鞭", "韓": "韩", "韌": "韦",
        "靜": "静", "非": "非", "面": "面",
        "革": "革", "響": "响", "頁": "页",
        "順": "顺", "須": "须", "頌": "颁",
        "頏": "顿", "預": "预", "頑": "顽",
        "頒": "颂", "頓": "顿", "頗": "颇",
        "領": "领", "頰": "颊", "頲": "颌",
        "頴": "颍", "頷": "颉", "頸": "颈",
        "頻": "频", "頹": "颏", "顆": "题",
        "題": "题", "額": "额", "顎": "颜",
        "顏": "颜", "顓": "颔", "顔": "颜",
        "願": "愿", "顛": "颠", "類": "类",
        "顥": "颢", "顧": "顾", "顫": "颤",
        "顯": '显', "顰": "颦", "顱": "風",
        "顳": "颮",
    },
)


# ===================================================================
# Pure domain functions
# ===================================================================


# -- spelling / word forms --------------------------------------------------

def spelling_variants(word: str) -> set[str]:
    """Return British/American spelling variants of a word (including itself)."""
    base = word.strip().lower()
    if not base or not re.fullmatch(r"[a-z]+", base):
        return {base} if base else set()

    variants = {base}
    rules = [
        (r"our\b", "or"), (r"or\b", "our"),
        (r"is(e|ed|es|ing|ation)\b", r"iz\1"),
        (r"iz(e|ed|es|ing|ation)\b", r"is\1"),
        (r"yse\b", "yze"), (r"yze\b", "yse"),
        (r"([bcdfgtv])re\b", r"\1er"),
        (r"([bcdfgt])er\b", r"\1re"),
        (r"ence\b", "ense"), (r"ense\b", "ence"),
        (r"dgement\b", "dgment"), (r"dgment\b", "dgement"),
        (r"ageing\b", "aging"), (r"aging\b", "ageing"),
        (r"ll(ed|ing|er|or)\b", r"l\1"),
        (r"ogue\b", "og"), (r"og\b", "ogue"),
    ]
    for pattern, repl in rules:
        for existing in list(variants):
            transformed = re.sub(pattern, repl, existing)
            if transformed != existing and re.fullmatch(r"[a-z]+", transformed):
                variants.add(transformed)
    return variants


def cloze_forms(word: str) -> set[str]:
    base = word.strip().lower()
    if not base or not re.fullmatch(r"[a-z]+", base):
        return {base} if base else set()
    forms: set[str] = set()
    for variant in spelling_variants(base):
        forms |= cloze_inflections(variant)
    return {form for form in forms if form}


def cloze_inflections(word: str) -> set[str]:
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


def truncate_cloze_prompt(prompt: str, max_chars: int = 240) -> str:
    """Keep ~max_chars of a long cloze prompt centered on the ____ marker."""
    if len(prompt) <= max_chars:
        return prompt
    marker = "____"
    pos = prompt.find(marker)
    if pos == -1:
        return prompt[: max_chars - 1] + "…"
    half = (max_chars - len(marker)) // 2
    start = max(0, pos - half)
    if start > 0:
        space = prompt.find(" ", start)
        if space != -1 and space < pos:
            start = space + 1
    end = min(len(prompt), pos + len(marker) + half)
    if end < len(prompt):
        space = prompt.rfind(" ", 0, end)
        if space != -1 and space > pos + len(marker):
            end = space
    result = prompt[start:end].strip()
    if start > 0:
        result = "…" + result
    if end < len(prompt):
        result = result + "…"
    return result


def valid_example_sentence(sentence: str | None, word: str) -> bool:
    return bool(cloze_prompt(sentence, word))


def english_word_count(sentence: str) -> int:
    return len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", sentence))


def contains_blocked_example_word(sentence: str) -> bool:
    words = {word.lower() for word in re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", sentence)}
    return bool(words & BLOCKED_EXAMPLE_WORDS)


def normalize_answer(value: str) -> str:
    return value.strip()


# -- POS normalization ------------------------------------------------------

def normalize_ecdict_pos(raw_pos: str) -> str:
    first = re.split(r"[\s,/;|.]+", raw_pos.strip().lower())[0] if raw_pos else ""
    return ECDICT_POS_MAP.get(first, "phrase")


def normalize_user_pos(raw_pos: str) -> str:
    normalized = normalize_ecdict_pos(raw_pos)
    return "v" if normalized in {"vi", "vt", "verb"} else normalized


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


def normalize_wiktionary_pos(pos: str) -> str:
    mapping = {
        "noun": "n", "proper noun": "n",
        "verb": "v",
        "adj": "adj", "adjective": "adj",
        "adv": "adv", "adverb": "adv",
        "pron": "pron", "pronoun": "pron",
        "prep": "prep", "preposition": "prep",
        "conj": "conj", "conjunction": "conj",
        "interj": "interj", "intj": "interj", "interjection": "interj",
        "num": "num", "numeral": "num",
        "det": "det", "determiner": "det",
        "phrase": "phrase",
    }
    return mapping.get(pos.strip().lower(), pos.strip().lower())


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


def display_pos_label(part_of_speech: str | None) -> str:
    part = normalize_part_group(str(part_of_speech or ""))
    return {
        "n": "n.", "v": "v.", "adj": "adj.", "adv": "adv.",
        "pron": "pron.", "prep": "prep.", "conj": "conj.",
        "interj": "interj.", "abbr": "abbr.", "num": "num.",
        "aux": "aux.", "phrase": "",
    }.get(part, str(part_of_speech or ""))


def definition_lines(value: str | None, part_of_speech: str | None = None) -> str:
    if not value:
        return ""
    if part_of_speech:
        part = normalize_part_group(part_of_speech)
        parts = DEFINITION_DISPLAY_POS_RE.split(str(value))
        filtered: list[str] = []
        i = 0
        while i < len(parts):
            segment = parts[i].strip()
            if i + 1 < len(parts) and parts[i + 1].startswith(part + "."):
                filtered.append(segment)
                i += 2
            elif i + 1 < len(parts):
                i += 2
            else:
                if segment:
                    filtered.append(segment)
                i += 1
        if filtered:
            return "\n".join(filtered)
    return str(value)


def merge_text_values(*values: str | None) -> str | None:
    non_empty = [v for v in values if v]
    return non_empty[0] if non_empty else None


# -- text cleaning & example validation -------------------------------------

def clean_wiktionary_example_text(text: str) -> str:
    text = re.sub(r"\[…\]|\[\.\.\.\]|\[sic\]|\[Sic\]", "", text)
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = cleaned.replace("　", " ")
    return cleaned


def example_note_from_tags(sense_tags: str | None) -> str | None:
    if not sense_tags:
        return None
    tags = {tag.strip().lower() for tag in str(sense_tags).split(",") if tag.strip()}
    labels = [label for tag, label in NOTABLE_EXAMPLE_TAGS.items() if tag in tags]
    return "; ".join(labels) if labels else None


def extract_example_sentence(text: str, word: str) -> str:
    """Pick the single best sentence containing the target word."""
    cleaned = clean_wiktionary_example_text(text)
    if not cleaned:
        return ""
    pattern = cloze_match_pattern(word)
    if pattern is None:
        return cleaned
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    if len(parts) <= 1:
        return cleaned
    matching = [part.strip() for part in parts if pattern.search(part)]
    if not matching:
        return cleaned
    matching.sort(key=len)
    for candidate in matching:
        if len(candidate) >= 6:
            return candidate
    return matching[0]


def usable_wiktionary_example(sentence: str, word: str) -> bool:
    stripped = clean_wiktionary_example_text(sentence)
    if not stripped or not valid_example_sentence(stripped, word):
        return False
    if contains_blocked_example_word(stripped):
        return False
    if len(stripped) < 6 or len(stripped) > 500:
        return False
    if re.search(r"https?://|www\.|[@#]|→|<|>|[_{}\[\]]", stripped):
        return False
    if stripped.startswith(("Synonyms:", "Antonyms:", "Holonyms:", "Meronyms:", "Hyponyms:", "Hypernyms:")):
        return False
    if len(re.findall(r"[A-Za-z]+", stripped)) < 2:
        return False
    return True


def usable_wordnet_example(sentence: str, word: str) -> bool:
    stripped = sentence.strip()
    if not stripped or not valid_example_sentence(stripped, word):
        return False
    if contains_blocked_example_word(stripped):
        return False
    if len(stripped) < 4 or len(stripped) > 500:
        return False
    if re.search(r"https?://|www\.|[@#]", stripped):
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


# -- sentence quality scoring -----------------------------------------------

def example_target_position_penalty(sentence: str, word: str) -> int:
    pattern = cloze_match_pattern(word)
    if pattern is None:
        return 0
    match = pattern.search(sentence)
    if not match:
        return 0
    start, end = match.span()
    word_count = english_word_count(sentence)
    if word_count <= 4:
        return 0
    word_pos = len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", sentence[:start]))
    position_ratio = word_pos / max(word_count - 1, 1)
    if position_ratio < 0.15 or position_ratio > 0.85:
        return 3
    if position_ratio >= 0.4 and position_ratio <= 0.6:
        return 0
    return 1


def matched_form_in_sentence(sentence: str, word: str) -> str:
    pattern = cloze_match_pattern(word)
    if pattern is None:
        return ""
    match = pattern.search(sentence)
    return match.group(1) if match else ""


def sentence_tokens(sentence: str) -> list[str]:
    lowered = sentence.lower()
    return re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", lowered)


def first_match_context(sentence: str, word: str) -> tuple[list[str], int]:
    tokens = sentence_tokens(sentence)
    token_index = -1
    word_lower = word.lower()
    forms = cloze_forms(word)
    for i, token in enumerate(tokens):
        if token == word_lower or token in forms:
            token_index = i
            break
    if token_index == -1:
        for i, token in enumerate(tokens):
            if token.startswith(word_lower) or word_lower.startswith(token):
                token_index = i
                break
    if token_index == -1 and tokens:
        token_index = 0
    return tokens, token_index


def token_after_adverbs(tokens: list[str], index: int) -> str:
    potential_adverbs = {"not", "also", "still", "just", "only", "even", "always",
                         "never", "often", "usually", "sometimes", "already",
                         "yet", "now", "then", "ever", "quite", "rather", "very",
                         "too", "so", "really", "almost", "nearly"}
    cursor = index + 1
    while cursor < len(tokens) and tokens[cursor] in potential_adverbs:
        cursor += 1
    return tokens[cursor] if cursor < len(tokens) else ""


def high_ambiguity_pos_allowed(sentence: str, word: str, part_of_speech: str) -> bool:
    group = normalize_part_group(part_of_speech)
    form = matched_form_in_sentence(sentence, word)
    if not form:
        return True
    lowered = sentence.lower()
    tokens, token_index = first_match_context(sentence, word)
    previous_token = tokens[token_index - 1] if token_index > 0 else ""
    next_token = tokens[token_index + 1] if 0 <= token_index < len(tokens) - 1 else ""
    next_content_token = token_after_adverbs(tokens, token_index) if token_index >= 0 else ""
    determiners = {"a", "an", "the", "this", "that", "these", "those", "my", "your", "his", "her", "our", "their"}
    copulas = {"am", "is", "are", "was", "were", "be", "been", "being", "feel", "feels", "felt", "seem", "seems", "seemed", "look", "looks", "looked"}
    possessive = {"my", "your", "his", "her", "our", "their", "its"}
    if group in {"n", "adj", "adv"} and previous_token in {"a", "an"}:
        return True
    if group in {"n", "adj"} and previous_token in copulas:
        return False
    if group == "adj" and previous_token in possessive and next_token and next_token not in copulas:
        return True
    if group == "n" and previous_token in possessive and next_token and next_token not in {"of", "for", "with", "to", "in", "on"}:
        return True
    if group == "n" and next_token in copulas:
        return False
    if group == "v" and previous_token == "to" and re.search(rf"\bto\s+{re.escape(form)}\b", lowered):
        return True
     # require at least one determiner/possessive/adjective before a noun
    if group == "n" and previous_token in {"the", "this", "that", "these", "those"} | possessive:
        return True
    if group == "adj" and next_token in {"speech", "task", "job", "work", "problem", "question", "issue", "situation", "experience", "role", "case", "idea", "project", "course", "position", "time", "thing", "things", "people", "life"}:
        return True
    if group in {"n", "adj"} and next_token in determiners:
        return False
    base_verb_list = {"be", "have", "do", "go", "get", "make", "take", "see", "come", "help", "use"}
    if group == "v" and next_content_token in base_verb_list:
        return False
    if next_content_token in base_verb_list:
        return True
    if group == "n" and next_content_token and next_content_token.endswith("ing") and next_content_token in {"being", "having", "doing", "going", "getting", "making", "taking", "coming", "using", "working", "trying", "looking", "moving", "talking", "walking", "running", "playing", "reading", "writing", "speaking", "listening", "watching", "learning", "thinking", "feeling", "living", "sitting", "standing", "waiting", "eating", "drinking", "sleeping", "driving", "flying", "swimming", "singing", "dancing", "fighting", "crying", "laughing", "smiling"}:
        return True
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
        "speech", "task", "job", "work", "problem", "question", "issue",
        "situation", "experience", "role", "case", "idea", "project", "course",
        "position", "time", "thing", "things", "people", "life",
    }
    escaped = re.escape(form)
    determiners = {"a", "an", "the", "this", "that", "these", "those", "my", "your", "his", "her", "our", "their", "another", "enough"}
    noun_preceders = determiners | {"real", "great", "big", "new", "major", "serious", "important", "difficult"}
    before = previous_token in noun_preceders or re.search(rf"\b(?:a|an|the|this|that|these|those|my|your|his|her|our|their|another|enough|real|great|big|new|major|serious|important|difficult)\s+{escaped}\b", lowered)
    after = re.search(rf"\b{escaped}\s+(?:of|for|from|with|in|on|to|that|which)\b", lowered)
    base_verbs = {
        "be", "have", "do", "go", "get", "make", "take", "see", "come",
        "help", "use", "work", "find", "learn", "speak", "read", "write",
        "play", "change", "become", "move", "show", "tell", "give", "keep",
        "try", "start", "stop", "leave", "bring", "put", "let", "say", "wonder", "phrase",
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


# -- parsing / entry normalization ------------------------------------------

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
    entry: dict[str, str] = {"word": word, "part_of_speech": part_of_speech, "meaning": meaning}
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
        example_index: int | None = first.index("example_sentence") if "example_sentence" in first else None
        example_translation_index: int | None = first.index("example_translation") if "example_translation" in first else None
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
        elif "," in stripped:
            row = stripped.split(",", 4)
        else:
            errors.append(f"Line {index}: no recognised separator.")
            continue
        entry, error = normalize_entry(row, index)
        if entry:
            entries.append(entry)
        if error:
            errors.append(error)
    return entries, errors


# -- review scheduling ------------------------------------------------------

def next_review_date(stage: int) -> str:
    index = max(0, min(stage, len(REVIEW_INTERVAL_DAYS) - 1))
    return (datetime.now().date() + timedelta(days=REVIEW_INTERVAL_DAYS[index])).isoformat()
