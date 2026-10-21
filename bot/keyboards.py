"""Inline and reply keyboard factories."""

from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from bot import texts


def _inline(options: list[tuple[str, str]], columns: int = 2) -> InlineKeyboardMarkup:
    """Build an inline keyboard from labels and callback data."""
    rows = [
        [
            InlineKeyboardButton(text=label, callback_data=data)
            for label, data in options[index:index + columns]
        ]
        for index in range(0, len(options), columns)
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def native_language_keyboard(prefix: str = "onboard:native") -> InlineKeyboardMarkup:
    """Return choices for the learner's explanation language."""
    return _inline([(label, f"{prefix}:{value}") for label, value in
                    zip(texts.NATIVE_LANGUAGES, ("Русский", "English", "other"))])


def target_language_keyboard(prefix: str = "onboard:target") -> InlineKeyboardMarkup:
    """Return the supported learning-language choices."""
    values = ("English", "Spanish", "German", "French", "Italian", "Chinese", "other")
    return _inline([(label, f"{prefix}:{value}")
                    for label, value in zip(texts.TARGET_LANGUAGES, values)])


def level_keyboard(prefix: str = "onboard:level") -> InlineKeyboardMarkup:
    """Return CEFR choices, including test-based placement."""
    options = [(level, f"{prefix}:{level}") for level in texts.CEFR_LEVELS]
    options.append((texts.LEVEL_TEST_BUTTON, f"{prefix}:placement"))
    return _inline(options, columns=3)


def goal_keyboard(prefix: str = "onboard:goal") -> InlineKeyboardMarkup:
    """Return learning-goal choices."""
    return _inline([(goal, f"{prefix}:{goal}") for goal in texts.GOALS])


def reminder_keyboard(prefix: str = "onboard:reminder") -> InlineKeyboardMarkup:
    """Return reminder-time choices."""
    return _inline([(label, f"{prefix}:{value}") for label, value in texts.REMINDER_OPTIONS], 2)


def settings_keyboard() -> InlineKeyboardMarkup:
    """Return profile settings actions."""
    options = [
        (texts.SETTINGS_LEVEL_BUTTON, "settings:level"),
        (texts.SETTINGS_TARGET_BUTTON, "settings:target"),
        (texts.SETTINGS_GOAL_BUTTON, "settings:goal"),
        (texts.SETTINGS_NATIVE_BUTTON, "settings:native"),
        (texts.SETTINGS_INTERESTS_BUTTON, "settings:interests"),
        (texts.SETTINGS_REMINDER_BUTTON, "settings:reminder"),
        (texts.SETTINGS_TIMEZONE_BUTTON, "settings:timezone"),
        (texts.SETTINGS_CLEAR_BUTTON, "settings:clear"),
        (texts.SETTINGS_DELETE_BUTTON, "settings:delete"),
    ]
    return _inline(options, columns=1)


def confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    """Return confirmation and cancellation actions."""
    return _inline([
        (texts.SETTINGS_CONFIRM_BUTTON, f"settings:confirm:{action}"),
        (texts.SETTINGS_CANCEL_BUTTON, "settings:cancel"),
    ])


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Return persistent command shortcuts below the message composer."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=label) for label in texts.MENU_BUTTONS[:4]],
                  [KeyboardButton(text=label) for label in texts.MENU_BUTTONS[4:]]],
        resize_keyboard=True,
    )
