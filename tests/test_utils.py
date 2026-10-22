import pytest

from bot.handlers.vocab import _matches_review_answer
from bot.utils import parse_vocab_marker, split_message, validate_timezone


@pytest.mark.parametrize("text,limit", [
    ("word " * 20, 13),
    ("x" * 100, 9),
    ("one\ntwo\nthree\nfour", 7),
    ("", 10),
])
def test_split_message_respects_limit_and_preserves_exact_text(text: str, limit: int) -> None:
    chunks = split_message(text, limit)
    assert "".join(chunks) == text
    assert all(len(chunk) <= limit for chunk in chunks)


def test_vocab_marker_is_removed_and_parsed() -> None:
    text, words = parse_vocab_marker(
        'Hello!\n[[VOCAB_JSON]]{"items":[{"word":"casa","translation":"house",'
        '"example":"Mi casa."}]}[[/VOCAB_JSON]]'
    )
    assert text == "Hello!"
    assert words == [{"word": "casa", "translation": "house", "example": "Mi casa."}]


def test_vocab_marker_parses_distinct_alternative_translations() -> None:
    _, words = parse_vocab_marker(
        '[[VOCAB_JSON]]{"items":[{"word":"casa","translation":"house",'
        '"alternatives":["home","HOUSE",""],"example":"Mi casa."}]}[[/VOCAB_JSON]]'
    )

    assert words == [{
        "word": "casa",
        "translation": "house",
        "example": "Mi casa.",
        "alternatives": ["home"],
    }]


@pytest.mark.parametrize("answer", [" HOME ", "home!", "Home.", "home"])
def test_review_accepts_normalized_alternative_translations(answer: str) -> None:
    assert _matches_review_answer(answer, ["house", "home"])


def test_review_answer_matching_preserves_meaningful_accents() -> None:
    assert not _matches_review_answer("si", ["sí"])


def test_invalid_vocab_marker_is_hidden_without_failing_the_turn() -> None:
    text, words = parse_vocab_marker("Hello [[VOCAB_JSON]]not json[[/VOCAB_JSON]]")
    assert text == "Hello"
    assert words == []


def test_split_message_counts_telegram_utf16_units() -> None:
    text = "🙂" * 12
    chunks = split_message(text, limit=5)
    assert "".join(chunks) == text
    assert all(len(chunk.encode("utf-16-le")) // 2 <= 5 for chunk in chunks)


def test_timezone_validation() -> None:
    assert validate_timezone("Europe/Moscow") == "Europe/Moscow"
    assert validate_timezone("invalid/timezone") is None
