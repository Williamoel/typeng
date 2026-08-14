"""Shared application and lexical constants."""

import re

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
    ("n", "n."),
    ("v", "v."),
    ("adj", "adj."),
    ("adv", "adv."),
    ("pron", "pron."),
    ("prep", "prep."),
    ("conj", "conj."),
    ("interj", "interj."),
    ("det", "det."),
    ("num", "num."),
    ("abbr", "abbr."),
    ("pref", "pref."),
    ("suf", "suf."),
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
