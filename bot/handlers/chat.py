"""Free-text learner conversation handler."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot import texts
from bot.db.repository import Repository
from bot.handlers.modes import Quiz
from bot.services.conversation import tutor_turn
from bot.services.llm import TutorLLM
from bot.utils import split_message

logger = logging.getLogger(__name__)
router = Router(name="chat")


@router.message(F.text & ~F.text.startswith("/"))
async def chat(
    message: Message,
    state: FSMContext,
    repository: Repository,
    llm: TutorLLM,
    prompt_template: str,
) -> None:
    """Send an ordinary text message to the tutor and persist the response."""
    if not message.from_user:
        return
    current_state = await state.get_state()
    in_quiz = current_state == Quiz.active.state
    if current_state is not None and not in_quiz:
        return
    content = message.text or ""
    if len(content) > 1500:
        await message.answer(texts.MESSAGE_TOO_LONG)
        return
    user = await repository.get_user(message.from_user.id)
    if user is None:
        await message.answer(texts.NOT_REGISTERED)
        return
    if user["mode"] == "quiz" and not in_quiz:
        await repository.update_user(message.from_user.id, mode="dialogue")

    quiz_data = await state.get_data() if in_quiz else {}
    question_number = int(quiz_data.get("quiz_question", 0))
    extra_instruction = (
        texts.QUIZ_NEXT.format(question=question_number) if in_quiz else ""
    )
    try:
        await message.bot.send_chat_action(message.chat.id, "typing")
        response = await tutor_turn(
            message.from_user.id,
            content,
            repository,
            llm,
            prompt_template,
            extra_system_instruction=extra_instruction,
        )
    except Exception as exc:
        logger.exception(
            "Tutor request failed for user %s (%s)",
            message.from_user.id,
            type(exc).__name__,
        )
        await message.answer(texts.LLM_ERROR)
        return

    for chunk in split_message(response.text):
        await message.answer(chunk)
    if in_quiz:
        score = int(quiz_data.get("quiz_score", 0)) + int(response.quiz_correct is True)
        if question_number >= 5:
            await repository.update_user(message.from_user.id, mode="dialogue")
            await state.clear()
            await message.answer(texts.QUIZ_FINISHED.format(score=score))
        else:
            await state.update_data(quiz_question=question_number + 1, quiz_score=score)
