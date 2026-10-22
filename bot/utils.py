"""Small Telegram formatting and parsing utilities."""

from __future__ import annotations

import re
import unicodedata
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

VOCAB_MARKER = re.compile(r"\[\[VOCAB_JSON\]\](.*?)\[\[/VOCAB_JSON\]\]", re.DOTALL)
CORRECTION_PATTERN = re.compile(r"❌\s*(.*?)\s*→\s*✅\s*(.*?)(?:\s*\+|$)")


def normalize_review_answer(answer: str) -> str:
    """Normalize casing, spacing, and surrounding punctuation but preserve accents."""
    normalized = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", answer).casefold()).strip()
    while normalized and unicodedata.category(normalized[0]).startswith("P"):
        normalized = normalized[1:].lstrip()
    while normalized and unicodedata.category(normalized[-1]).startswith("P"):
        normalized = normalized[:-1].rstrip()
    return normalized


def matches_review_answer(answer: str, accepted_translations: list[str]) -> bool:
    """Check an answer against the primary translation and its accepted alternatives."""
    normalized_answer = normalize_review_answer(answer)
    return normalized_answer in {
        normalize_review_answer(translation)
        for translation in accepted_translations
    }


def split_message(text: str, limit: int = 4096) -> list[str]:
    """Split text into Telegram-sized UTF-16 chunks without dropping content."""
    if limit < 1:
        raise ValueError("limit must be positive")
    if _telegram_length(text) <= limit:
        return [text]
    chunks: list[str] = []
    remaining = text
    while _telegram_length(remaining) > limit:
        units = 0
        cutoff = 0
        for index, character in enumerate(remaining):
            character_units = 2 if ord(character) > 0xFFFF else 1
            if units + character_units > limit:
                break
            units += character_units
            cutoff = index + 1
        if cutoff == 0:
            raise ValueError("limit is too small to hold the next Unicode character")
        newline = remaining.rfind("\n", 0, cutoff)
        space = remaining.rfind(" ", 0, cutoff)
        boundary = max(newline, space)
        split_at = boundary + 1 if boundary > 0 else cutoff
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:]
    if remaining:
        chunks.append(remaining)
    return chunks


def _telegram_length(text: str) -> int:
    """Count UTF-16 code units, as used by Telegram's message length limits."""
    return len(text.encode("utf-16-le")) // 2


def validate_timezone(value: str) -> str | None:
    """Return a canonical IANA timezone or None for invalid input."""
    try:
        return ZoneInfo(value.strip()).key
    except (ZoneInfoNotFoundError, ValueError):
        return None


def parse_vocab_marker(response: str) -> tuple[str, list[dict[str, Any]]]:
    """Strip and parse an optional machine-readable vocabulary marker."""
    match = VOCAB_MARKER.search(response)
    if not match:
        return response.strip(), []
    import json

    try:
        payload: Any = json.loads(match.group(1).strip())
    except json.JSONDecodeError:
        return VOCAB_MARKER.sub("", response).strip(), []
    words = payload.get("items", []) if isinstance(payload, dict) else []
    valid: list[dict[str, Any]] = []
    for item in words:
        if not isinstance(item, dict) or not item.get("word") or not item.get("translation"):
            continue
        word = {
            key: str(item.get(key, "")).strip()
            for key in ("word", "translation", "example")
        }
        alternatives = item.get("alternatives", [])
        if isinstance(alternatives, list):
            parsed_alternatives = list(dict.fromkeys(
                value.strip()
                for value in alternatives
                if isinstance(value, str)
                and value.strip()
                and value.strip().casefold() != word["translation"].casefold()
            ))
            if parsed_alternatives:
                word["alternatives"] = parsed_alternatives
        valid.append(word)
    return VOCAB_MARKER.sub("", response).strip(), valid


def extract_corrections(response: str) -> list[tuple[str, str]]:
    """Extract learner errors and their corrections from tutor response text."""
    return [(match.group(1).strip(), match.group(2).strip())
            for match in CORRECTION_PATTERN.finditer(response)]
