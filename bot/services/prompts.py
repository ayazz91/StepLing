"""System prompt construction from the user profile and a Markdown template."""

from __future__ import annotations

from pathlib import Path
from typing import Any

PROMPT_VARIABLES = (
    "target_language", "native_language", "level", "goal", "interests",
    "mode", "known_mistakes", "recent_vocab",
)


def build_system_prompt(
    template: str,
    user: dict[str, Any],
    known_mistakes: list[dict[str, Any]] | None = None,
    recent_vocab: list[dict[str, Any]] | None = None,
) -> str:
    """Substitute learner-specific values without interpreting braces in user data."""
    values = {
        "target_language": user.get("target_lang", "not specified"),
        "native_language": user.get("native_lang", "not specified"),
        "level": user.get("level", "A1"),
        "goal": user.get("goal", "general development"),
        "interests": user.get("interests", "not specified") or "not specified",
        "mode": user.get("mode", "dialogue"),
        "known_mistakes": "; ".join(
            f"{item['category']}: {item['example']} ({item['count']})"
            for item in (known_mistakes or [])
        ) or "none recorded",
        "recent_vocab": "; ".join(
            f"{item['word']} = {item['translation']}"
            for item in (recent_vocab or [])
        ) or "none recorded",
    }
    result = template
    for variable in PROMPT_VARIABLES:
        result = result.replace("{" + variable + "}", str(values[variable]))
    return result


def load_prompt(path: Path) -> str:
    """Read the system prompt template from disk."""
    return path.read_text(encoding="utf-8")
