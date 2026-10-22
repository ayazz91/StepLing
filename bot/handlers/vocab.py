"""Vocabulary listing and Leitner-box review sessions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from bot import texts
from bot.db.repository import Repository
from bot.utils import matches_review_answer, split_message

router = Router(name="vocabulary")


class Review(StatesGroup):
    """State for a one-word-at-a-time review session."""

    waiting_for_answer = State()


@router.message(Command("words"))
async def show_words(message: Message, repository: Repository) -> None:
    """List the learner's most recently saved vocabulary."""
    if not message.from_user:
        return
    words = await repository.list_vocabulary(message.from_user.id)
    if not words:
        await message.answer(texts.WORDS_EMPTY)
        return
    lines = [texts.WORDS_HEADER]
    lines.extend(
        f"• {word['word']} — {word['translation']}"
        + (f" ({', '.join(word['alternatives'])})" if word["alternatives"] else "")
        for word in words
    )
    for chunk in split_message("\n".join(lines)):
        await message.answer(chunk)


@router.message(Command("review"))
async def start_review(message: Message, state: FSMContext, repository: Repository) -> None:
    """Start a review with due words ordered by their review date."""
    if not message.from_user:
        return
    words = await repository.due_vocabulary(
        message.from_user.id, datetime.now(UTC)
    )
    if not words:
        await message.answer(texts.REVIEW_EMPTY)
        return
    await state.set_state(Review.waiting_for_answer)
    await state.update_data(review_words=words, review_index=0)
    await _ask_review_word(message, words[0])


async def _ask_review_word(message: Message, word: dict[str, Any]) -> None:
    """Ask the learner to translate one due vocabulary item."""
    await message.answer(texts.REVIEW_PROMPT.format(word=word["word"]))


@router.message(Review.waiting_for_answer)
async def check_review_answer(
    message: Message, state: FSMContext, repository: Repository,
) -> None:
    """Check the learner's answer and update the current Leitner box."""
    if not message.from_user:
        return
    await repository.mark_active(message.from_user.id)
    data = await state.get_data()
    words: list[dict[str, Any]] = data.get("review_words", [])
    index = int(data.get("review_index", 0))
    if index >= len(words):
        await state.clear()
        await message.answer(texts.REVIEW_DONE)
        return
    word = words[index]
    accepted_translations = [word["translation"], *word["alternatives"]]
    correct = matches_review_answer(message.text or "", accepted_translations)
    await repository.update_review(int(word["id"]), correct)
    if correct:
        await message.answer(texts.REVIEW_CORRECT)
    else:
        await message.answer(
            texts.REVIEW_INCORRECT.format(
                translation="; ".join(accepted_translations)
            )
        )
    index += 1
    if index >= len(words):
        await state.clear()
        await message.answer(texts.REVIEW_DONE)
        return
    await state.update_data(review_index=index)
    await _ask_review_word(message, words[index])
