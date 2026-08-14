"""Canonical part-of-speech handling shared by lexical data sources."""

from __future__ import annotations

import re

CANONICAL_PARTS = {
    "n", "v", "adj", "adv", "pron", "prep", "conj", "interj",
    "abbr", "num", "aux", "det", "pref", "suf", "phrase",
}

_ALIASES = {
    "n": "n", "noun": "n", "proper noun": "n", "name": "n",
    "pl": "n", "plural": "n",
    "v": "v", "vi": "v", "vt": "v", "verb": "v",
    "a": "adj", "s": "adj", "adj": "adj", "adjective": "adj",
    "ad": "adv", "r": "adv", "adv": "adv", "adverb": "adv",
    "pron": "pron", "pronoun": "pron",
    "prep": "prep", "preposition": "prep", "postposition": "prep",
    "conj": "conj", "conjunction": "conj",
    "int": "interj", "intj": "interj", "interj": "interj",
    "interjection": "interj",
    "abbr": "abbr", "abbrev": "abbr", "abbreviation": "abbr",
    "initialism": "abbr", "acronym": "abbr",
    "num": "num", "numeral": "num", "number": "num",
    "aux": "aux", "auxiliary": "aux", "modal": "aux",
    "det": "det", "determiner": "det", "article": "det",
    "pref": "pref", "prefix": "pref",
    "suf": "suf", "suff": "suf", "suffix": "suf",
    "phr": "phrase", "phrase": "phrase", "proverb": "phrase",
    "idiom": "phrase", "contraction": "phrase", "particle": "phrase",
}


def canonical_part(raw_part: str, *, unknown: str = "phrase") -> str:
    """Normalize source-specific labels while retaining useful fine groups."""
    cleaned = re.sub(r"\s+", " ", (raw_part or "").strip().lower().rstrip("."))
    if cleaned in _ALIASES:
        return _ALIASES[cleaned]
    first = re.split(r"[\s,/;|.]+", cleaned)[0] if cleaned else ""
    return _ALIASES.get(first, unknown)


def lexical_part(raw_part: str, *, unknown: str = "phrase") -> str:
    """Return the cross-dictionary comparison group for a normalized POS."""
    part = canonical_part(raw_part, unknown=unknown)
    return "v" if part == "aux" else part


def compatible_parts(raw_part: str, word: str) -> set[str]:
    """Return Wiktionary groups compatible with an ECDICT/EFLLex entry."""
    primary = lexical_part(raw_part)
    if primary == "phrase" and re.search(r"[\s-]", word.strip()):
        return {"phrase", "n", "v", "adj", "adv", "prep", "conj", "interj"}
    return {primary}
