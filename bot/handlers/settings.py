"""Profile settings, history controls, and user-data deletion."""

from __future__ import annotations

from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot import texts
from bot.db.repository import Repository
from bot.keyboards import (
    confirm_keyboard,
    goal_keyboard,
    level_keyboard,
    native_language_keyboard,
    reminder_keyboard,
    settings_keyboard,
    target_language_keyboard,
)
from bot.utils import validate_timezone

router = Router(name="settings")


class SettingsInput(StatesGroup):
    """Free-text fields editable through settings."""

    interests = State()
    timezone = State()
    target_custom = State()
    native_custom = State()


@router.message(Command("settings"))
async def show_settings(
    message: Message, state: FSMContext, repository: Repository,
) -> None:
    """Display current profile settings and available actions."""
    if not message.from_user:
        return
    await state.clear()
    user = await repository.get_user(message.from_user.id)
    if user is None:
        await message.answer(texts.NOT_REGISTERED)
        return
    if user["mode"] == "quiz":
        await repository.update_user(message.from_user.id, mode="dialogue")
    reminder = user["reminder_time"] or texts.REMINDER_NONE
    await message.answer(
        texts.SETTINGS_CURRENT.format(
            level=user["level"], goal=user["goal"], interests=user["interests"] or "—",
            target_language=user["target_lang"], native_language=user["native_lang"],
            reminder=reminder, timezone=user["timezone"],
        ),
        reply_markup=settings_keyboard(),
    )


@router.callback_query(F.data.startswith("settings:"))
async def handle_settings_callback(
    callback: CallbackQuery,
    state: FSMContext,
    repository: Repository,
    reminder_scheduler: Any,
) -> None:
    """Handle settings menus, confirmation prompts, and inline profile choices."""
    await callback.answer()
    if not isinstance(callback.message, Message) or callback.from_user is None:
        return
    message = callback.message
    user_id = callback.from_user.id
    parts = (callback.data or "").split(":", 2)
    action = parts[1] if len(parts) > 1 else ""
    value = parts[2] if len(parts) > 2 else ""
    user = await repository.get_user(user_id)
    if user is None:
        await message.answer(texts.NOT_REGISTERED)
        return
    await state.clear()
    if user["mode"] == "quiz":
        await repository.update_user(user_id, mode="dialogue")

    if action == "level":
        if value in (*texts.CEFR_LEVELS, "placement"):
            await repository.update_user(
                user_id, level="Определить тестом" if value == "placement" else value
            )
            await message.answer(texts.SETTINGS_SAVED)
        else:
            await message.answer(texts.ONBOARDING_LEVEL, reply_markup=level_keyboard("settings:level"))
    elif action == "target":
        if value == "other":
            await state.set_state(SettingsInput.target_custom)
            await message.answer(texts.ONBOARDING_TARGET_OTHER)
        elif value in {"English", "Spanish", "German", "French", "Italian", "Chinese"}:
            await repository.update_user(user_id, target_lang=value)
            await message.answer(texts.SETTINGS_SAVED)
        else:
            await message.answer(texts.ONBOARDING_TARGET, reply_markup=target_language_keyboard("settings:target"))
    elif action == "native":
        if value == "other":
            await state.set_state(SettingsInput.native_custom)
            await message.answer(texts.ONBOARDING_NATIVE_OTHER)
        elif value in {"Русский", "English"}:
            await repository.update_user(user_id, native_lang=value)
            await message.answer(texts.SETTINGS_SAVED)
        else:
            await message.answer(texts.ONBOARDING_NATIVE, reply_markup=native_language_keyboard("settings:native"))
    elif action == "goal":
        if value in texts.GOALS:
            await repository.update_user(user_id, goal=value)
            await message.answer(texts.SETTINGS_SAVED)
        else:
            await message.answer(texts.ONBOARDING_GOAL, reply_markup=goal_keyboard("settings:goal"))
    elif action == "interests":
        await state.set_state(SettingsInput.interests)
        await message.answer(texts.SETTINGS_INTERESTS)
    elif action == "reminder":
        if value in {"09:00", "13:00", "19:00", "off"}:
            await repository.update_user(user_id, reminder_time=None if value == "off" else value)
            await reminder_scheduler.refresh()
            await message.answer(texts.SETTINGS_SAVED)
        else:
            await message.answer(texts.ONBOARDING_REMINDER, reply_markup=reminder_keyboard("settings:reminder"))
    elif action == "timezone":
        await state.set_state(SettingsInput.timezone)
        await message.answer(texts.SETTINGS_TIMEZONE)
    elif action == "clear":
        await message.answer(texts.SETTINGS_CLEAR_CONFIRM, reply_markup=confirm_keyboard("clear"))
    elif action == "delete":
        await message.answer(texts.SETTINGS_DELETE_CONFIRM, reply_markup=confirm_keyboard("delete"))
    elif action == "cancel":
        await state.clear()
        await message.answer(texts.SETTINGS_CANCELLED)
    elif action == "confirm" and value == "clear":
        await repository.clear_history(user_id)
        await message.answer(texts.SETTINGS_CLEARED)
    elif action == "confirm" and value == "delete":
        await repository.delete_user(user_id)
        await state.clear()
        await reminder_scheduler.refresh()
        await message.answer(texts.SETTINGS_DELETED)
    else:
        await message.answer(texts.SETTINGS_INVALID)


@router.message(SettingsInput.interests)
async def update_interests(message: Message, state: FSMContext, repository: Repository) -> None:
    """Save validated interests."""
    value = (message.text or "").strip()
    if not message.from_user:
        return
    if len(value) > 200:
        await message.answer(texts.INVALID_INTERESTS)
        return
    await repository.update_user(message.from_user.id, interests=value)
    await state.clear()
    await message.answer(texts.SETTINGS_SAVED)


@router.message(SettingsInput.timezone)
async def update_timezone(
    message: Message, state: FSMContext, repository: Repository, reminder_scheduler: Any,
) -> None:
    """Save a valid IANA timezone."""
    timezone = validate_timezone((message.text or "").strip())
    if timezone is None:
        await message.answer(texts.INVALID_TIMEZONE)
        return
    if not message.from_user:
        return
    await repository.update_user(message.from_user.id, timezone=timezone)
    await state.clear()
    await reminder_scheduler.refresh()
    await message.answer(texts.SETTINGS_SAVED)


@router.message(SettingsInput.target_custom)
async def update_custom_target_language(
    message: Message, state: FSMContext, repository: Repository,
) -> None:
    """Save a custom learning language."""
    value = (message.text or "").strip()
    if not value or len(value) > 80:
        await message.answer(texts.ONBOARDING_TARGET_OTHER)
        return
    if not message.from_user:
        return
    await repository.update_user(message.from_user.id, target_lang=value)
    await state.clear()
    await message.answer(texts.SETTINGS_SAVED)


@router.message(SettingsInput.native_custom)
async def update_custom_native_language(
    message: Message, state: FSMContext, repository: Repository,
) -> None:
    """Save a custom explanation language."""
    value = (message.text or "").strip()
    if not value or len(value) > 80:
        await message.answer(texts.ONBOARDING_NATIVE_OTHER)
        return
    if not message.from_user:
        return
    await repository.update_user(message.from_user.id, native_lang=value)
    await state.clear()
    await message.answer(texts.SETTINGS_SAVED)
