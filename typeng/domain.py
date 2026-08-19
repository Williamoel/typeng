"""Pure vocabulary, cloze, parsing, and example-ranking domain logic."""

from __future__ import annotations

import csv
import io
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from .chinese_fallback import TRADITIONAL_TO_SIMPLIFIED
from .constants import *  # shared closed set of domain constants
from .parts import canonical_part, compatible_parts, lexical_part

__all__ = "display_pos_label definition_items definition_lines normalize_user_pos merge_text_values next_review_date spelling_variants cloze_forms cloze_inflections cloze_match_pattern cloze_answer cloze_prompt truncate_cloze_prompt valid_example_sentence english_word_count contains_blocked_example_word example_target_position_penalty normalize_answer answer_matches answer_feedback cloze_form_hint_feedback normalize_part_group matched_form_in_sentence sentence_tokens first_match_context token_after_adverbs high_ambiguity_pos_allowed part_of_speech_penalty sentence_quality_score wiktionary_part_group wiktionary_lookup_groups normalize_wiktionary_pos clean_wiktionary_example_text contains_archaic_english extract_example_sentence usable_wiktionary_example wiktionary_example_rank example_note_from_tags wiktionary_usage_label wiktionary_definition_display simplify_chinese parse_word_file normalize_entry parse_csv parse_text_lines split_ecdict_tags clean_ecdict_text format_ecdict_definition normalize_ecdict_pos infer_pos_from_ecdict_definition infer_pos_from_ecdict_exchange infer_pos_from_word_shape infer_ecdict_fallback_pos split_ecdict_translation normalize_ecdict_frequency parse_ecdict_csv".split()

try:
    from opencc import OpenCC
except ImportError:
    OpenCC = None

OPENCC_T2S = OpenCC("t2s") if OpenCC is not None else None

DEFINITION_DISPLAY_POS_RE = re.compile(
    r"\s*[;；]\s*(?=(?:n|v|a|s|r|adj|adv|pron|prep|conj|interj|abbr|num|aux|det|pref|suf|phrase)\.\s)",
    re.IGNORECASE,
)
DEFINITION_LINE_POS_RE = re.compile(
    r"^(n|v|a|s|r|adj|adv|pron|prep|conj|interj|abbr|num|aux|det|pref|suf|phrase)\.\s*(.+)$",
    re.IGNORECASE,
)
NOTABLE_EXAMPLE_TAGS = {
    "archaic": "archaic usage",
    "obsolete": "obsolete usage",
    "dated": "dated usage",
    "rare": "rare usage",
}

ECDICT_MORPHOLOGY_NOTE_RE = re.compile(
    r"(?:过去式|过去分词|现在分词|第三人称单数|比较级|最高级|复数形式|的复数|原形)"
)
ECDICT_UNATTACHED_DOMAIN_RE = re.compile(r"^\[[^\]]{1,12}\]\s*")


def wiktionary_usage_label(raw_tags: str) -> str:
    """Return Wiktionary's usage/domain labels without translating them."""
    tags = [
        tag.strip().casefold()
        for tag in re.split(r"[,;|]", raw_tags or "")
        if tag.strip()
    ]
    labels: list[str] = []
    for tag in tags:
        if tag in WIKTIONARY_HIDDEN_DISPLAY_TAGS:
            continue
        label = {"us": "US", "uk": "UK"}.get(tag, tag.replace("-", " "))
        if label not in labels:
            labels.append(label)
    # Kaikki may expose one qualifier in three equivalent forms, e.g.
    # ``often``, ``with-down`` and the raw-gloss label ``often with down``.
    # Prefer the most informative combined label instead of displaying all 3.
    informative: list[str] = []
    token_sets = [set(label.casefold().split()) for label in labels]
    for index, label in enumerate(labels):
        tokens = token_sets[index]
        if any(tokens < other for other_index, other in enumerate(token_sets) if other_index != index):
            continue
        informative.append(label)
    return " · ".join(informative)


def wiktionary_definition_display(definition: str) -> str:
    """Repair lossy plain-text conversions of a few mathematical formulas."""
    value = definition.replace("\n", "; ").strip()
    permanent_formula = re.fullmatch(
        r"Given an n×n matrix a_ij,, the sum over all permutations π, of ∏ᵢ₌₁ⁿa_iπ\(i\)\.",
        value,
    )
    if permanent_formula:
        return (
            "Given an n × n matrix A = (a(i, j)), the sum over all "
            "permutations π of the product from i = 1 to n of a(i, π(i))."
        )
    return value


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


def definition_items(value: str | None, part_of_speech: str | None = None) -> list[str]:
    """Extract only definitions that belong to the requested POS."""
    lines: list[str] = []
    for raw_line in (value or "").replace("\\n", "\n").splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        parts = [part.strip() for part in DEFINITION_DISPLAY_POS_RE.split(line) if part.strip()]
        lines.extend(parts or [line])
    target = normalize_user_pos(str(part_of_speech or "")) if part_of_speech else ""
    labeled: list[tuple[str, str]] = []
    unlabeled: list[str] = []
    for line in lines:
        match = DEFINITION_LINE_POS_RE.match(line)
        if match:
            labeled.append((normalize_user_pos(match.group(1)), match.group(2).strip()))
        else:
            unlabeled.append(line)
    selected = [text for part, text in labeled if not target or part == target] if labeled else unlabeled
    return list(dict.fromkeys(text for text in selected if text))


def definition_lines(value: str | None, part_of_speech: str | None = None) -> str:
    label = display_pos_label(part_of_speech)
    return "\n".join(f"{label} {item}".strip() for item in definition_items(value, part_of_speech))


def normalize_user_pos(raw_pos: str) -> str:
    normalized = normalize_ecdict_pos(raw_pos)
    return "v" if normalized in {"vi", "vt", "verb", "aux"} else normalized


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


def next_review_date(stage: int) -> str:
    index = max(0, min(stage, len(REVIEW_INTERVAL_DAYS) - 1))
    return (datetime.now().date() + timedelta(days=REVIEW_INTERVAL_DAYS[index])).isoformat()


def spelling_variants(word: str) -> set[str]:
    """Return British/American spelling variants of a word (including itself).

    Wiktionary often keeps example sentences under only one spelling (e.g. all
    examples live under "judgment", while the "judgement" entry is an empty
    cross-reference). Generating both spellings lets example lookup find them
    and lets cloze practice accept either spelling as correct.
    """
    base = word.strip().lower()
    if not base or not re.fullmatch(r"[a-z]+", base):
        return {base} if base else set()

    variants = {base}

    # Rule-based transforms that hold across many common words. Applied in both
    # directions so either spelling maps to the other.
    rules = [
        # -our / -or : colour/color, honour/honor, favour/favor, behaviour...
        (r"our\b", "or"),
        (r"or\b", "our"),
        # -ise / -ize and -isation / -ization : organise/organize...
        (r"is(e|ed|es|ing|ation)\b", r"iz\1"),
        (r"iz(e|ed|es|ing|ation)\b", r"is\1"),
        # -yse / -yze : analyse/analyze, paralyse/paralyze
        (r"yse\b", "yze"),
        (r"yze\b", "yse"),
        # -re / -er : centre/center, theatre/theater, metre/meter, fibre...
        (r"([bcdfgtv])re\b", r"\1er"),
        (r"([bcdfgt])er\b", r"\1re"),
        # -ce / -se noun forms : defence/defense, offence/offense, licence...
        (r"ence\b", "ense"),
        (r"ense\b", "ence"),
        # judgement / judgment, acknowledgement / acknowledgment, ageing/aging
        (r"dgement\b", "dgment"),
        (r"dgment\b", "dgement"),
        (r"ageing\b", "aging"),
        (r"aging\b", "ageing"),
        # doubled-l before suffix : travelled/traveled, cancelled/canceled...
        (r"ll(ed|ing|er|or)\b", r"l\1"),
        # -ogue / -og : catalogue/catalog, dialogue/dialog
        (r"ogue\b", "og"),
        (r"og\b", "ogue"),
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

    forms = set()
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
    """Keep ~max_chars of a long cloze prompt centered on the ____ marker.

    Sentences longer than max_chars are accepted into the word bank and shown
    in full during preview; this function only affects how they appear in the
    cloze exercise, where a focused window around the target word is clearer
    than a wall of text.
    """
    if len(prompt) <= max_chars:
        return prompt

    marker = "____"
    pos = prompt.find(marker)
    if pos == -1:
        return prompt[: max_chars - 1] + "…"

    half = (max_chars - len(marker)) // 2

    start = max(0, pos - half)
    if start > 0:
        # Align to a word boundary so we don't cut mid-word.
        space = prompt.find(" ", start)
        if space != -1 and space < pos:
            start = space + 1

    end = min(len(prompt), pos + len(marker) + half)
    if end < len(prompt):
        # Back up to the previous word boundary.
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


def normalize_part_group(part_of_speech: str) -> str:
    return lexical_part(part_of_speech)


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


def wiktionary_part_group(part_of_speech: str) -> str:
    return lexical_part(part_of_speech)


def wiktionary_lookup_groups(part_of_speech: str, word: str) -> list[str]:
    return sorted(compatible_parts(part_of_speech, word))


def normalize_wiktionary_pos(pos: str) -> str:
    return lexical_part(pos, unknown="")


def clean_wiktionary_example_text(text: str) -> str:
    # Strip Wiktionary omission markers that add no value for cloze practice
    # but would otherwise fail the special-character filter (the brackets).
    text = re.sub(r"\[…\]|\[\.\.\.\]|\[sic\]|\[Sic\]", "", text)
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = cleaned.replace(" ", " ")
    return cleaned


ARCHAIC_EXAMPLE_TOKENS = {
    "art", "doth", "hast", "hath", "henceforth", "hither", "saith",
    "shalt", "thee", "thine", "thither", "thou", "thy", "unto", "wert",
    "wherefore", "whence", "wilt", "ye", "yon", "yonder",
}
MODERN_ETH_WORDS = {"teeth", "twentieth"}


def contains_archaic_english(text: str) -> bool:
    """Detect conspicuous Early Modern English that is unsuitable for learners.

    Wiktionary's register tags describe the sense, not always the quotation.
    A Bible quotation can therefore be attached to an ordinary modern sense
    without an ``archaic`` tag. This small, conservative text gate catches the
    most visible pronouns, auxiliaries, and productive ``-eth`` verb forms.
    """
    # A long s is not a rendering failure: it is historical typography copied
    # from early printed sources.  Such quotations are unsuitable as modern
    # learner examples even when Wiktionary does not tag the sense archaic.
    if "ſ" in text:
        return True
    tokens = re.findall(r"[A-Za-z]+", text)
    lowered = {token.lower() for token in tokens}
    if lowered & ARCHAIC_EXAMPLE_TOKENS:
        return True
    for token in tokens:
        lowered_token = token.lower()
        if (
            lowered_token.endswith("eth")
            and len(lowered_token) > 4
            and lowered_token not in MODERN_ETH_WORDS
            and not token[:1].isupper()
        ):
            return True
    return bool(re.search(r"(?:^|\s)['’]tis(?:\s|$)", text, re.IGNORECASE))


def extract_example_sentence(
    text: str,
    word: str,
    bold_text_offsets: object | None = None,
) -> str:
    """Pick the single best sentence containing the target word.

    Wiktionary quotations are often multi-sentence passages (well over the
    usable length limit) where only one sentence actually uses the target word,
    e.g. common nouns like "shortage" whose only examples are long book/news
    quotes. Returning that one sentence keeps such words from having no example
    at all. If the whole text is already a single short sentence, it is returned
    unchanged.
    """
    cleaned = clean_wiktionary_example_text(text)
    if not cleaned:
        return ""

    pattern = cloze_match_pattern(word)
    if pattern is None:
        return cleaned

    # Do not treat the period in common titles/abbreviations as a sentence
    # boundary (the old splitter turned "Ms. Pinal" into "Pinal) ...").
    period_marker = "\uE000"
    protected = re.sub(
        r"\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|St|vs|etc)\.",
        lambda match: match.group(0).replace(".", period_marker),
        cleaned,
        flags=re.IGNORECASE,
    )
    # Preserve initials in personal names. Without this, a quotation such as
    # ``T. E. Lawrence`` is split after ``T.`` and displayed as ``T. …``.
    protected = re.sub(
        r"\b[A-Z]\.(?=\s+(?:[A-Z]\.\s+)*[A-Z][a-z])",
        lambda match: match.group(0).replace(".", period_marker),
        protected,
    )
    parts = [
        part.replace(period_marker, ".")
        for part in re.split(r"(?<=[.!?])\s+", protected)
    ]

    highlighted = ""
    selected = ""

    # Kaikki preserves the offsets of the form highlighted by Wiktionary.
    # Prefer that evidence over a bare-headword search: an inflected form may
    # occur in one line while the headword happens to occur in another.
    if isinstance(bold_text_offsets, list):
        for offsets in bold_text_offsets:
            if not (
                isinstance(offsets, (list, tuple))
                and len(offsets) == 2
                and all(isinstance(value, int) for value in offsets)
            ):
                continue
            start, end = offsets
            if start < 0 or end <= start or end > len(text):
                continue
            highlighted = clean_wiktionary_example_text(text[start:end]).casefold()
            if not highlighted:
                continue
            highlighted_parts = [
                part.strip() for part in parts if highlighted in part.casefold()
            ]
            if highlighted_parts:
                highlighted_parts.sort(key=len)
                selected = highlighted_parts[0]
                break

    if not selected:
        matching = [part.strip() for part in parts if pattern.search(part)]
        if matching:
            # Prefer the shortest matching sentence that is long enough to be
            # a real example, so the cloze prompt stays focused.
            matching.sort(key=len)
            selected = next(
                (candidate for candidate in matching if len(candidate) >= 6),
                matching[0],
            )

    if not selected:
        # Target word only appears across a sentence boundary; leave the full
        # text so the caller's usability check can decide.
        return cleaned

    prefix_omitted = not cleaned.startswith(selected)
    suffix_omitted = not cleaned.endswith(selected)

    # Keep a readable window around the actual target.  This is stored as an
    # explicitly marked excerpt and is used only when no complete example is
    # available for the same word and part of speech.
    max_chars = 220
    if len(selected) > max_chars:
        target_match = re.search(re.escape(highlighted), selected, re.IGNORECASE) if highlighted else None
        if target_match is None:
            target_match = pattern.search(selected)
        target_start = target_match.start() if target_match else len(selected) // 2
        target_end = target_match.end() if target_match else target_start
        half = (max_chars - max(1, target_end - target_start)) // 2
        start = max(0, target_start - half)
        end = min(len(selected), target_end + half)
        if start > 0:
            boundary = selected.find(" ", start)
            if boundary != -1 and boundary < target_start:
                start = boundary + 1
        if end < len(selected):
            boundary = selected.rfind(" ", target_end, end)
            if boundary != -1:
                end = boundary
        prefix_omitted = prefix_omitted or start > 0
        suffix_omitted = suffix_omitted or end < len(selected)
        selected = selected[start:end].strip()

    if prefix_omitted:
        selected = f"… {selected}"
    if suffix_omitted:
        selected = f"{selected} …"
    return selected


def usable_wiktionary_example(sentence: str, word: str) -> bool:
    stripped = clean_wiktionary_example_text(sentence)
    if not stripped or not valid_example_sentence(stripped, word):
        return False
    if contains_blocked_example_word(stripped):
        return False
    if contains_archaic_english(stripped):
        return False
    # Quotations sometimes preserve expressive spellings such as
    # "maaaaaaaybe" without an example-level informal tag.  They are valid
    # prose but poor spelling models for learners.
    if re.search(r"([A-Za-z])\1{3,}", stripped, re.IGNORECASE):
        return False
    if re.search(r"\b(?:gonna|outta|wanna|gotta|ain['’]t)\b", stripped, re.IGNORECASE):
        return False
    if re.search(r"\b(?:he|she|it)\s+don['’]t\b", stripped, re.IGNORECASE):
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


def example_note_from_tags(sense_tags: str | None) -> str | None:
    """Expose the source's non-grammatical usage/domain labels verbatim."""
    if not sense_tags:
        return None
    return wiktionary_usage_label(str(sense_tags)) or None


def simplify_chinese(text: str | None) -> str | None:
    if text is None:
        return None
    if OPENCC_T2S is not None:
        return OPENCC_T2S.convert(text)
    return text.translate(TRADITIONAL_TO_SIMPLIFIED)


def parse_word_file(filename: str, raw: bytes) -> tuple[list[dict[str, str]], list[str]]:
    text = raw.decode("utf-8-sig")
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        return parse_csv(text)
    return parse_text_lines(text)


def normalize_entry(row: list[str], line_number: int) -> tuple[dict[str, str] | None, str | None]:
    if len(row) < 3:
        return None, f"第 {line_number} 行：需要提供单词、词性和中文释义。"

    word = row[0].strip()
    part_of_speech = normalize_user_pos(row[1].strip())
    meaning = row[2].strip()
    example_sentence = row[3].strip() if len(row) > 3 else ""
    example_translation = row[4].strip() if len(row) > 4 else ""

    if not word or not part_of_speech or not meaning:
        return None, f"第 {line_number} 行：单词、词性和中文释义不能为空。"

    entry = {"word": word, "part_of_speech": part_of_speech, "meaning": meaning}
    if example_sentence:
        if valid_example_sentence(example_sentence, word):
            entry["example_sentence"] = example_sentence
            entry["example_source"] = "user"
            if example_translation:
                entry["example_translation"] = example_translation
        else:
            return entry, f"第 {line_number} 行：例句不包含目标单词，已忽略该例句。"
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


TXT_HEADWORD_RE = re.compile(
    r"^[A-Za-z][A-Za-z'’.-]*(?:[ -][A-Za-z][A-Za-z'’.-]*)*$"
)
TXT_BLOCK_POS_RE = re.compile(
    r"(?<!\S)(proper\s+noun|adjective|adverb|preposition|conjunction|"
    r"interjection|pronoun|abbreviation|determiner|auxiliary|noun|verb|"
    r"prefix|suffix|numeral|phrase|initialism|acronym|article|modal|"
    r"abbr|abbrev|interj|intj|pron|prep|conj|adj|adv|aux|det|pref|"
    r"suff|suf|num|noun|verb|vt|vi|n|v|a|s|r)\.?(?=\s)",
    re.IGNORECASE,
)


def _dictionary_block_senses(text: str) -> list[tuple[str, str]]:
    """Split ``n. meaning adj. meaning`` into normalized POS/gloss pairs."""
    normalized = text.strip()
    matches = list(TXT_BLOCK_POS_RE.finditer(normalized))
    if not matches or matches[0].start() != 0:
        return []

    senses: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(normalized)
        meaning = normalized[match.end():end].strip(" \t;；")
        if meaning:
            senses.append((normalize_user_pos(match.group(1)), meaning))
    return senses


def _append_dictionary_senses(
    entries: list[dict[str, str]],
    errors: list[str],
    word: str,
    sense_text: str,
    line_number: int,
) -> int:
    senses = _dictionary_block_senses(sense_text)
    for part_of_speech, meaning in senses:
        entry, error = normalize_entry(
            [word, part_of_speech, meaning], line_number
        )
        if entry:
            existing = next(
                (
                    candidate
                    for candidate in reversed(entries)
                    if candidate["word"].casefold() == word.casefold()
                    and candidate["part_of_speech"] == part_of_speech
                ),
                None,
            )
            if existing:
                existing["meaning"] = merge_text_values(
                    existing["meaning"], meaning
                ) or meaning
            else:
                entries.append(entry)
        if error:
            errors.append(error)
    return len(senses)


def parse_text_lines(text: str) -> tuple[list[dict[str, str]], list[str]]:
    """Parse both column-oriented TXT and common copied dictionary blocks.

    Existing tab, pipe, and comma rows remain supported. A bare English
    headword can additionally be followed by one or more POS-prefixed lines,
    including multiple senses on one line, for example::

        accessory
            n. 同谋，帮凶 adj. 附属的
    """
    entries: list[dict[str, str]] = []
    errors: list[str] = []
    pending_word = ""
    pending_line = 0
    pending_sense_count = 0

    def finish_pending() -> None:
        nonlocal pending_word, pending_line, pending_sense_count
        if pending_word and pending_sense_count == 0:
            errors.append(f"第 {pending_line} 行：单词“{pending_word}”后没有可识别的词性和释义。")
        pending_word = ""
        pending_line = 0
        pending_sense_count = 0

    for index, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # A POS-prefixed line belongs to the most recent bare headword.
        block_senses = _dictionary_block_senses(stripped)
        if block_senses:
            if not pending_word:
                errors.append(f"第 {index} 行：词性释义前缺少对应的英文单词。")
                continue
            pending_sense_count += _append_dictionary_senses(
                entries, errors, pending_word, stripped, index
            )
            continue

        delimiter = "\t" if "\t" in stripped else "|" if "|" in stripped else ""
        if delimiter:
            row = stripped.split(delimiter, 4)
            # Also accept: accessory<TAB>n. 同谋，帮凶 adj. 附属的
            if (
                len(row) == 2
                and TXT_HEADWORD_RE.fullmatch(row[0].strip())
                and _dictionary_block_senses(row[1].strip())
            ):
                finish_pending()
                _append_dictionary_senses(
                    entries, errors, row[0].strip(), row[1].strip(), index
                )
                continue
            finish_pending()
        elif "," in stripped:
            row = re.split(r"\s*,\s*", stripped, maxsplit=4)
            finish_pending()
        else:
            # A complete copied-dictionary block may also fit on one line.
            marker = TXT_BLOCK_POS_RE.search(stripped)
            if marker and marker.start() > 0:
                word = stripped[:marker.start()].strip()
                if TXT_HEADWORD_RE.fullmatch(word):
                    finish_pending()
                    _append_dictionary_senses(
                        entries, errors, word, stripped[marker.start():], index
                    )
                    continue

            if TXT_HEADWORD_RE.fullmatch(stripped):
                finish_pending()
                pending_word = stripped
                pending_line = index
                continue

            finish_pending()
            row = [stripped]

        entry, error = normalize_entry(row, index)
        if entry:
            entries.append(entry)
        if error:
            errors.append(error)

    finish_pending()
    if not entries and not errors:
        errors.append("文件中没有可用的词条。")

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
    return canonical_part(raw_pos)


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

        # ECDICT places inflection metadata and sometimes an unscoped domain
        # gloss on a new line. Neither belongs to the preceding lexical POS.
        if ECDICT_MORPHOLOGY_NOTE_RE.search(line):
            continue
        if current_meaning and ECDICT_UNATTACHED_DOMAIN_RE.match(line):
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
