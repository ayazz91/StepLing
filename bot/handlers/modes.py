"""Commands for switching tutoring modes."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from bot import texts
from bot.db.repository import Repository
from bot.keyboards import main_menu_keyboard
from bot.services.conversation import tutor_turn
from bot.services.llm import TutorLLM
from bot.utils import split_message

logger = logging.getLogger(__name__)
router = Router(name="modes")


class Quiz(StatesGroup):
    """Track quiz count and score for the current conversation."""

    active = State()


async def _switch_mode(
    message: Message,
    mode: str,
    repository: Repository,
    llm: TutorLLM,
    prompt_template: str,
    state: FSMContext,
) -> None:
    """Change profile mode and optionally start a mode-specific activity."""
    if not message.from_user:
        return
    user_id = message.from_user.id
    user = await repository.get_user(user_id)
    if user is None:
        await message.answer(texts.NOT_REGISTERED)
        return
    await state.clear()
    await repository.update_user(user_id, mode=mode)
    await message.answer(
        texts.MODE_SET.format(mode=texts.MODE_LABELS[mode]),
        reply_markup=main_menu_keyboard(),
    )
    kickoff = texts.MODE_KICKOFF.get(mode)
    if mode == "quiz":
        kickoff = texts.QUIZ_FIRST
        await state.set_state(Quiz.active)
        await state.update_data(quiz_question=1, quiz_score=0)
    if not kickoff:
        return
    try:
        await message.bot.send_chat_action(message.chat.id, "typing")
        reply = await tutor_turn(
            user_id,
            kickoff,
            repository,
            llm,
            prompt_template,
            save_user_message=False,
            extra_system_instruction=(
                "This is the start of a new five-question quiz. Ask only question 1."
                if mode == "quiz" else ""
            ),
        )
        for chunk in split_message(reply.text):
            await message.answer(chunk)
    except Exception as exc:
        logger.exception("Mode kickoff failed for user %s (%s)", user_id, type(exc).__name__)
        await message.answer(texts.LLM_ERROR)
        if mode == "quiz":
            await state.clear()
            await repository.update_user(user_id, mode="dialogue")


@router.message(Command("dialogue"))
async def dialogue_mode(
    message: Message, repository: Repository, llm: TutorLLM, prompt_template: str,
    state: FSMContext,
) -> None:
    """Switch to free conversation."""
    await _switch_mode(message, "dialogue", repository, llm, prompt_template, state)


@router.message(Command("lesson"))
async def lesson_mode(
    message: Message, repository: Repository, llm: TutorLLM, prompt_template: str,
    state: FSMContext,
) -> None:
    """Switch to guided mini-lesson mode."""
    await _switch_mode(message, "lesson", repository, llm, prompt_template, state)


@router.message(Command("quiz"))
async def quiz_mode(
    message: Message, repository: Repository, llm: TutorLLM, prompt_template: str,
    state: FSMContext,
) -> None:
    """Start a five-question quiz."""
    await _switch_mode(message, "quiz", repository, llm, prompt_template, state)


@router.message(Command("translate"))
async def translate_mode(
    message: Message, repository: Repository, llm: TutorLLM, prompt_template: str,
    state: FSMContext,
) -> None:
    """Switch to translation practice."""
    await _switch_mode(message, "translate", repository, llm, prompt_template, state)
