"""Orchestrate profile-aware tutoring turns and persist extracted learning data."""

from __future__ import annotations

import re
from dataclasses import dataclass

from bot.db.repository import Repository
from bot.services.llm import TutorLLM
from bot.services.prompts import build_system_prompt
from bot.utils import extract_corrections, parse_vocab_marker

QUIZ_MARKER = re.compile(r"\[\[QUIZ_RESULT\]\]\s*(correct|incorrect)\s*\[\[/QUIZ_RESULT\]\]", re.I)
QUIZ_BLOCK = re.compile(r"\[\[QUIZ_RESULT\]\].*?\[\[/QUIZ_RESULT\]\]", re.I | re.S)
LEVEL_BLOCK = re.compile(r"\[\[LEVEL_ESTIMATE\]\](.*?)\[\[/LEVEL_ESTIMATE\]\]", re.I | re.S)


@dataclass(frozen=True, slots=True)
class TutorResponse:
    """Tutor text and optional quiz-evaluation signal."""

    text: str
    quiz_correct: bool | None = None


async def tutor_turn(
    telegram_id: int,
    content: str,
    repository: Repository,
    llm: TutorLLM,
    prompt_template: str,
    *,
    save_user_message: bool = True,
    extra_system_instruction: str = "",
) -> TutorResponse:
    """Generate one tutor turn, save it, and record vocabulary and corrections."""
    user = await repository.get_user(telegram_id)
    if user is None:
        raise ValueError("User profile not found")
    history = await repository.get_history(telegram_id)
    if save_user_message:
        await repository.save_message(telegram_id, "user", content)
    await repository.mark_active(telegram_id)
    history.append({"role": "user", "content": content})
    completed_answers = (
        await repository.count_placement_answers(telegram_id)
        if user["level"] == "Определить тестом" else 0
    )
    mistakes = await repository.known_mistakes(telegram_id)
    vocabulary = await repository.list_vocabulary(telegram_id, limit=10)
    prompt = build_system_prompt(prompt_template, user, mistakes, vocabulary)
    if user["level"] == "Определить тестом":
        prompt += (
            "\n\nThe learner requested level placement. Ask short adaptive diagnostic "
            "questions in separate turns. They have answered "
            f"{completed_answers} recorded questions. After at least three useful answers, "
            "estimate a CEFR level and append [[LEVEL_ESTIMATE]]B1[[/LEVEL_ESTIMATE]] "
            "using the best-fitting level from A1, A2, B1, B2, C1, C2. Do not expose this marker."
        )
    if extra_system_instruction:
        prompt = f"{prompt}\n\n{extra_system_instruction}"
    raw_response = await llm.respond(prompt, history)
    response, new_words = parse_vocab_marker(raw_response)
    if not response.strip():
        raise RuntimeError("Gemini returned no learner-visible tutor text")
    level_match = LEVEL_BLOCK.search(response)
    estimated_level = level_match.group(1).strip().upper() if level_match else ""
    if (
        level_match
        and estimated_level in {"A1", "A2", "B1", "B2", "C1", "C2"}
        and user["level"] == "Определить тестом"
        and completed_answers >= 3
    ):
        await repository.update_user(telegram_id, level=estimated_level)
    if level_match:
        response = LEVEL_BLOCK.sub("", response).strip()
    quiz_match = QUIZ_MARKER.search(response)
    quiz_correct = (
        quiz_match.group(1).casefold() == "correct" if quiz_match else None
    )
    if QUIZ_BLOCK.search(response):
        response = QUIZ_BLOCK.sub("", response).strip()
    await repository.save_message(telegram_id, "assistant", response)
    for item in new_words:
        await repository.add_vocabulary(
            telegram_id, item["word"], item["translation"], item["example"]
        )
    for incorrect, corrected in extract_corrections(response):
        await repository.record_mistake(
            telegram_id, incorrect[:80].casefold(), f"{incorrect} → {corrected}"
        )
    return TutorResponse(response, quiz_correct)
