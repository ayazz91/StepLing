"""Learner and administrator statistics commands."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot import texts
from bot.db.repository import Repository
from bot.utils import split_message

router = Router(name="stats")


@router.message(Command("stats"))
async def show_stats(message: Message, repository: Repository) -> None:
    """Show the current learner's progress and common mistakes."""
    if not message.from_user:
        return
    user = await repository.get_user(message.from_user.id)
    if user is None:
        await message.answer(texts.NOT_REGISTERED)
        return
    stats = await repository.stats(message.from_user.id)
    mistakes = await repository.known_mistakes(message.from_user.id, limit=5)
    mistake_lines = [
        f"• {item['category']}: {item['example']} ({item['count']})" for item in mistakes
    ]
    response = texts.STATS.format(
        messages=stats["messages"],
        words=stats["words"],
        streak=stats["streak"],
        mistakes="\n".join(mistake_lines) if mistake_lines else texts.STATS_NO_MISTAKES,
    )
    for chunk in split_message(response):
        await message.answer(chunk)


@router.message(Command("admin_stats"))
async def show_admin_stats(
    message: Message, repository: Repository, admin_ids: frozenset[int],
) -> None:
    """Show aggregate usage only to IDs configured as administrators."""
    if not message.from_user or message.from_user.id not in admin_ids:
        return
    result = await repository.admin_stats(datetime.now(UTC) - timedelta(days=1))
    await message.answer(texts.ADMIN_STATS.format(**result))
