"""Start command and FSM-based onboarding."""

from __future__ import annotations

import logging
from typing import Any

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot import texts
from bot.db.repository import Repository
from bot.keyboards import (
    goal_keyboard,
    level_keyboard,
    main_menu_keyboard,
    native_language_keyboard,
    reminder_keyboard,
    target_language_keyboard,
)
from bot.services.conversation import tutor_turn
from bot.services.llm import TutorLLM
from bot.utils import split_message, validate_timezone

logger = logging.getLogger(__name__)
router = Router(name="start")


class Onboarding(StatesGroup):
    """States for the six onboarding questions."""

    native = State()
    native_custom = State()
    target = State()
    target_custom = State()
    level = State()
    goal = State()
    interests = State()
    reminder = State()
    timezone = State()


async def _ask_target(message: Message, state: FSMContext) -> None:
    """Prompt for the learning language."""
    await state.set_state(Onboarding.target)
    await message.answer(texts.ONBOARDING_TARGET, reply_markup=target_language_keyboard())


async def _ask_level(message: Message, state: FSMContext) -> None:
    """Prompt for the learner's CEFR level."""
    await state.set_state(Onboarding.level)
    await message.answer(texts.ONBOARDING_LEVEL, reply_markup=level_keyboard())


async def _ask_goal(message: Message, state: FSMContext) -> None:
    """Prompt for the learner's goal."""
    await state.set_state(Onboarding.goal)
    await message.answer(texts.ONBOARDING_GOAL, reply_markup=goal_keyboard())


async def _ask_interests(message: Message, state: FSMContext) -> None:
    """Prompt for a short free-text description of interests."""
    await state.set_state(Onboarding.interests)
    await message.answer(texts.ONBOARDING_INTERESTS)


async def _ask_reminder(message: Message, state: FSMContext) -> None:
    """Prompt for daily reminder time."""
    await state.set_state(Onboarding.reminder)
    await message.answer(texts.ONBOARDING_REMINDER, reply_markup=reminder_keyboard())


@router.message(CommandStart())
async def start_onboarding(message: Message, state: FSMContext) -> None:
    """Begin or restart onboarding."""
    await state.clear()
    await state.set_state(Onboarding.native)
    await message.answer(texts.ONBOARDING_NATIVE, reply_markup=native_language_keyboard())


@router.callback_query(F.data.startswith("onboard:"))
async def handle_onboarding_choice(
    callback: CallbackQuery,
    state: FSMContext,
    repository: Repository,
    llm: TutorLLM,
    prompt_template: str,
    reminder_scheduler: Any,
) -> None:
    """Apply an inline onboarding choice and advance the wizard."""
    await callback.answer()
    if not isinstance(callback.message, Message) or callback.from_user is None:
        return
    message = callback.message
    parts = (callback.data or "").split(":", 2)
    if len(parts) != 3:
        return
    section, value = parts[1], parts[2]
    current_state = await state.get_state()

    if section == "native" and current_state == Onboarding.native.state:
        if value == "other":
            await state.set_state(Onboarding.native_custom)
            await message.answer(texts.ONBOARDING_NATIVE_OTHER)
        elif value in {"Русский", "English"}:
            await state.update_data(native_lang=value)
            await _ask_target(message, state)
        else:
            await message.answer(texts.INVALID_CHOICE)
    elif section == "target" and current_state == Onboarding.target.state:
        if value == "other":
            await state.set_state(Onboarding.target_custom)
            await message.answer(texts.ONBOARDING_TARGET_OTHER)
        elif value in {"English", "Spanish", "German", "French", "Italian", "Chinese"}:
            await state.update_data(target_lang=value)
            await _ask_level(message, state)
        else:
            await message.answer(texts.INVALID_CHOICE)
    elif section == "level" and current_state == Onboarding.level.state:
        if value == "placement" or value in texts.CEFR_LEVELS:
            await state.update_data(level="Определить тестом" if value == "placement" else value)
            await _ask_goal(message, state)
        else:
            await message.answer(texts.INVALID_CHOICE)
    elif section == "goal" and current_state == Onboarding.goal.state and value in texts.GOALS:
        await state.update_data(goal=value)
        await _ask_interests(message, state)
    elif section == "reminder" and current_state == Onboarding.reminder.state:
        allowed_times = {time for _, time in texts.REMINDER_OPTIONS}
        if value not in allowed_times:
            await message.answer(texts.INVALID_CHOICE)
            return
        await state.update_data(reminder_time="" if value == "off" else value)
        if value == "off":
            await state.update_data(timezone="UTC")
            await _complete_onboarding(
                callback.from_user.id, message, state, repository, llm,
                prompt_template, reminder_scheduler,
            )
        else:
            await state.set_state(Onboarding.timezone)
            await message.answer(texts.ONBOARDING_TIMEZONE)
    else:
        await message.answer(texts.INVALID_CHOICE)


@router.message(Onboarding.native_custom)
async def receive_native_language(message: Message, state: FSMContext) -> None:
    """Save a custom native language."""
    value = (message.text or "").strip()
    if value:
        await state.update_data(native_lang=value[:80])
        await _ask_target(message, state)


@router.message(Onboarding.target_custom)
async def receive_target_language(message: Message, state: FSMContext) -> None:
    """Save a custom learning language."""
    value = (message.text or "").strip()
    if value:
        await state.update_data(target_lang=value[:80])
        await _ask_level(message, state)


@router.message(Onboarding.interests)
async def receive_interests(message: Message, state: FSMContext) -> None:
    """Validate and save the learner's interests."""
    value = (message.text or "").strip()
    if len(value) > 200:
        await message.answer(texts.INVALID_INTERESTS)
        return
    await state.update_data(interests=value)
    await _ask_reminder(message, state)


@router.message(Onboarding.timezone)
async def receive_timezone(
    message: Message,
    state: FSMContext,
    repository: Repository,
    llm: TutorLLM,
    prompt_template: str,
    reminder_scheduler: Any,
) -> None:
    """Validate the IANA timezone and finish onboarding."""
    timezone = validate_timezone((message.text or "").strip())
    if timezone is None:
        await message.answer(texts.INVALID_TIMEZONE)
        return
    if not message.from_user:
        return
    await state.update_data(timezone=timezone)
    await _complete_onboarding(
        message.from_user.id, message, state, repository, llm,
        prompt_template, reminder_scheduler,
    )


async def _complete_onboarding(
    user_id: int,
    message: Message,
    state: FSMContext,
    repository: Repository,
    llm: TutorLLM,
    prompt_template: str,
    reminder_scheduler: Any,
) -> None:
    """Persist the profile, configure reminders, and send the first tutor turn."""
    data = await state.get_data()
    required = ("native_lang", "target_lang", "level", "goal")
    if any(not data.get(key) for key in required):
        await message.answer(texts.UNKNOWN_ERROR)
        return
    profile = {
        "native_lang": str(data["native_lang"]),
        "target_lang": str(data["target_lang"]),
        "level": str(data["level"]),
        "goal": str(data["goal"]),
        "interests": str(data.get("interests", "")),
        "timezone": str(data.get("timezone", "UTC")),
        "reminder_time": str(data.get("reminder_time", "")),
    }
    await repository.create_user(user_id, profile)
    await state.clear()
    await reminder_scheduler.refresh()
    await message.answer(texts.ONBOARDING_DONE, reply_markup=main_menu_keyboard())
    try:
        await message.bot.send_chat_action(message.chat.id, "typing")
        reply = await tutor_turn(
            user_id,
            "Introduce yourself warmly and ask me one short first question. "
            "If my level is 'Определить тестом', begin with an easy placement question.",
            repository,
            llm,
            prompt_template,
            save_user_message=False,
        )
        for chunk in split_message(reply.text):
            await message.answer(chunk)
    except Exception:
        logger.exception("Failed to generate onboarding welcome for user %s", user_id)
        await message.answer(texts.LLM_ERROR)
