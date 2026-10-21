"""Daily local-time reminder scheduling."""

from __future__ import annotations

import logging
from datetime import UTC
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.db.repository import Repository
from bot.texts import REMINDER_TEXT

logger = logging.getLogger(__name__)


class ReminderScheduler:
    """Manage timezone-aware daily reminder jobs for configured users."""

    def __init__(self, bot: Bot, repository: Repository) -> None:
        """Create the scheduler using a Telegram bot and database repository."""
        self.bot = bot
        self.repository = repository
        self.scheduler = AsyncIOScheduler(timezone=UTC)

    async def start(self) -> None:
        """Start the scheduler and restore persisted reminder jobs."""
        self.scheduler.start()
        await self.refresh()

    async def refresh(self) -> None:
        """Synchronize scheduled jobs with reminder settings in the database."""
        for job in self.scheduler.get_jobs():
            self.scheduler.remove_job(job.id)
        for user in await self.repository.all_reminders():
            try:
                hour, minute = (int(part) for part in user["reminder_time"].split(":"))
                timezone = ZoneInfo(user["timezone"])
            except (ValueError, TypeError, KeyError):
                logger.warning("Skipping invalid reminder configuration for user %s", user["telegram_id"])
                continue
            self.scheduler.add_job(
                self._send_reminder,
                CronTrigger(hour=hour, minute=minute, timezone=timezone),
                args=[int(user["telegram_id"])],
                id=f"reminder-{user['telegram_id']}",
                replace_existing=True,
                coalesce=True,
                max_instances=1,
            )

    async def _send_reminder(self, telegram_id: int) -> None:
        """Send a short daily practice task and disable unreachable accounts."""
        user = await self.repository.get_user(telegram_id)
        if user is None or not user["reminder_time"]:
            return
        try:
            await self.bot.send_message(
                telegram_id, REMINDER_TEXT.format(target_language=user["target_lang"])
            )
        except TelegramForbiddenError:
            logger.info("Disabling reminder after Telegram blocked bot for user %s", telegram_id)
            await self.repository.disable_reminder(telegram_id)
            job_id = f"reminder-{telegram_id}"
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)

    async def shutdown(self) -> None:
        """Stop the scheduler without waiting for outstanding jobs."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
