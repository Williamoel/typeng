"""Domain entities for the source-neutral lexical model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Word:
    id: int
    lemma: str
    normalized_lemma: str
    language: str = "en"


@dataclass(frozen=True, slots=True)
class Sense:
    id: int
    word_id: int
    part_of_speech: str
    chinese_gloss: str = ""
    english_definition: str = ""
    phonetic: str | None = None
    frequency: int | None = None
    source: str | None = None
    source_ref: str | None = None
    source_tags: str | None = None


@dataclass(frozen=True, slots=True)
class Example:
    id: int
    sense_id: int
    sentence: str
    translation: str | None = None
    note: str | None = None
    source: str | None = None
    source_ref: str | None = None
    rank: int = 0
