from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.db.database import Database
from bot.db.repository import Repository
from bot.handlers import start
from bot.services.conversation import TutorResponse


class FakeState:
    def __init__(self) -> None:
        self.cleared = False

    async def get_data(self) -> dict[str, str]:
        return {
            "native_lang": "Russian",
            "target_lang": "Spanish",
            "level": "A1",
            "goal": "Travel",
            "interests": "",
            "timezone": "UTC",
            "reminder_time": "",
        }

    async def clear(self) -> None:
        self.cleared = True


class FakeMessage:
    def __init__(self) -> None:
        self.from_user = SimpleNamespace(id=999)
        self.chat = SimpleNamespace(id=42)
        self.bot = SimpleNamespace(send_chat_action=AsyncMock())
        self.sent: list[str] = []

    async def answer(self, text: str, **_kwargs: object) -> None:
        self.sent.append(text)


class FakeScheduler:
    def __init__(self) -> None:
        self.refresh = AsyncMock()


@pytest.mark.asyncio
async def test_onboarding_finishes_for_callback_user_not_bot_message_sender(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_tutor_turn(*_args: object, **_kwargs: object) -> TutorResponse:
        return TutorResponse("Welcome!")

    monkeypatch.setattr(start, "tutor_turn", fake_tutor_turn)
    database = Database(Path(":memory:"))
    repository = Repository(await database.connect())
    state = FakeState()
    message = FakeMessage()
    scheduler = FakeScheduler()
    try:
        await start._complete_onboarding(
            42, message, state, repository, object(), "prompt", scheduler
        )

        assert await repository.get_user(42) is not None
        assert await repository.get_user(999) is None
        assert state.cleared
        scheduler.refresh.assert_awaited_once()
        assert message.sent[-1] == "Welcome!"
    finally:
        await database.close()
