"""Application entry point for Telegram long polling."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand, Message, TelegramObject

from bot import texts
from bot.config import PROJECT_ROOT, Settings, load_settings
from bot.db.database import Database
from bot.db.repository import Repository
from bot.handlers import chat, modes, settings, start, stats, vocab
from bot.services.llm import TutorLLM
from bot.services.prompts import load_prompt
from bot.services.rate_limit import RateLimiter
from bot.services.scheduler import ReminderScheduler

logger = logging.getLogger(__name__)


class AllowlistMiddleware(BaseMiddleware):
    """Silently ignore users outside an optional Telegram ID allowlist."""

    def __init__(self, allowed_user_ids: frozenset[int] | None) -> None:
        """Initialize the middleware with the optional list of permitted users."""
        self.allowed_user_ids = allowed_user_ids

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Allow update processing only for configured Telegram users."""
        if self.allowed_user_ids is None:
            return await handler(event, data)
        from_user = getattr(event, "from_user", None)
        if from_user is None or from_user.id not in self.allowed_user_ids:
            return None
        return await handler(event, data)


class RateLimitMiddleware(BaseMiddleware):
    """Enforce the configured per-user limit on all incoming messages."""

    def __init__(self, limiter: RateLimiter) -> None:
        """Initialize the middleware with the application rate limiter."""
        self.limiter = limiter

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Reject messages that exceed the user's rolling-minute quota."""
        if isinstance(event, Message) and event.from_user is not None:
            if not self.limiter.allow(event.from_user.id):
                await event.answer(texts.RATE_LIMITED)
                return None
            if event.text is not None and len(event.text) > 1500:
                await event.answer(texts.MESSAGE_TOO_LONG)
                return None
        return await handler(event, data)


def create_dispatcher(settings_value: Settings, rate_limiter: RateLimiter) -> Dispatcher:
    """Create a dispatcher and register the bot's routers and access policy."""
    storage = (
        RedisStorage.from_url(settings_value.redis_url)
        if settings_value.redis_url else MemoryStorage()
    )
    dispatcher = Dispatcher(storage=storage)
    dispatcher.message.outer_middleware(AllowlistMiddleware(settings_value.allowed_user_ids))
    dispatcher.message.outer_middleware(RateLimitMiddleware(rate_limiter))
    dispatcher.callback_query.outer_middleware(AllowlistMiddleware(settings_value.allowed_user_ids))
    for router in (start.router, settings.router, vocab.router, stats.router, modes.router, chat.router):
        dispatcher.include_router(router)
    return dispatcher


async def _set_bot_commands(bot: Bot) -> None:
    """Publish supported slash commands in Telegram's command menu."""
    await bot.set_my_commands([
        BotCommand(command=name, description=description)
        for name, description in texts.COMMAND_DESCRIPTIONS
    ])


async def run(settings_value: Settings) -> None:
    """Initialize services and run the bot until a graceful shutdown."""
    prompt_template = load_prompt(settings_value.prompt_path)
    database_path = settings_value.database_path
    if not database_path.is_absolute():
        database_path = PROJECT_ROOT / database_path
    database = Database(database_path)
    llm: TutorLLM | None = None
    bot: Bot | None = None
    reminder_scheduler: ReminderScheduler | None = None
    dispatcher: Dispatcher | None = None
    try:
        connection = await database.connect()
        repository = Repository(connection, settings_value.gemini_daily_request_limit)
        llm = TutorLLM(settings_value.gemini_api_key, settings_value.gemini_model)
        bot = Bot(token=settings_value.telegram_bot_token)
        rate_limiter = RateLimiter(settings_value.rate_limit_per_minute)
        dispatcher = create_dispatcher(settings_value, rate_limiter)
        reminder_scheduler = ReminderScheduler(bot, repository)
        await reminder_scheduler.start()
        await _set_bot_commands(bot)
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Starting Telegram long polling with Gemini model %s", settings_value.gemini_model)
        await dispatcher.start_polling(
            bot,
            close_bot_session=False,
            repository=repository,
            llm=llm,
            prompt_template=prompt_template,
            reminder_scheduler=reminder_scheduler,
            admin_ids=settings_value.admin_ids,
        )
    finally:
        try:
            if reminder_scheduler is not None:
                await reminder_scheduler.shutdown()
        finally:
            try:
                if llm is not None:
                    await llm.close()
            finally:
                try:
                    if bot is not None:
                        await bot.session.close()
                finally:
                    try:
                        if dispatcher is not None:
                            await dispatcher.storage.close()
                    finally:
                        await database.close()


async def main() -> None:
    """Load configuration and run the long-polling process."""
    settings_value = load_settings()
    logging.basicConfig(
        level=settings_value.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    await run(settings_value)


if __name__ == "__main__":
    asyncio.run(main())
