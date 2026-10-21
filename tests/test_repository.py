from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiosqlite
import pytest

from bot.db.database import Database
from bot.db.repository import Repository


@pytest.fixture
async def repository() -> AsyncIterator[Repository]:
    database = Database(Path(":memory:"))
    connection = await database.connect()
    yield Repository(connection)
    await database.close()


async def add_user(repository: Repository, user_id: int = 42) -> None:
    await repository.create_user(user_id, {
        "native_lang": "Russian",
        "target_lang": "Spanish",
        "level": "A2",
        "goal": "Travel",
        "interests": "music",
        "timezone": "UTC",
        "reminder_time": "09:00",
    })


@pytest.mark.asyncio
async def test_profile_messages_and_parameterized_updates(repository: Repository) -> None:
    await add_user(repository)
    await repository.update_user(42, interests="quotes ' and SQL-like text")
    user = await repository.get_user(42)
    assert user is not None
    assert user["interests"] == "quotes ' and SQL-like text"

    for index in range(18):
        await repository.save_message(42, "user", f"message {index}")
    history = await repository.get_history(42, limit=15)
    assert len(history) == 15
    assert history[0]["content"] == "message 3"
    assert history[-1]["content"] == "message 17"

    await repository.clear_history(42)
    assert await repository.get_history(42) == []


@pytest.mark.asyncio
async def test_vocabulary_review_intervals_and_stats(repository: Repository) -> None:
    await add_user(repository)
    await repository.add_vocabulary(42, "viaje", "trip", "Buen viaje.")
    words = await repository.due_vocabulary(42)
    assert len(words) == 1
    word_id = int(words[0]["id"])
    moment = datetime(2026, 10, 21, 12, tzinfo=UTC)

    await repository.update_review(word_id, correct=True, now=moment)
    reviewed = await repository.list_vocabulary(42)
    assert reviewed[0]["box"] == 2
    assert datetime.fromisoformat(reviewed[0]["next_review"]) == moment + timedelta(days=3)

    await repository.update_review(word_id, correct=False, now=moment)
    reviewed = await repository.list_vocabulary(42)
    assert reviewed[0]["box"] == 1
    assert datetime.fromisoformat(reviewed[0]["next_review"]) == moment + timedelta(days=1)

    await repository.record_mistake(42, "verb tense", "I go yesterday")
    await repository.record_mistake(42, "verb tense", "I goed yesterday")
    stats = await repository.stats(42)
    assert stats["words"] == 1
    mistakes = await repository.known_mistakes(42)
    assert mistakes[0]["count"] == 2


@pytest.mark.asyncio
async def test_streak_uses_consecutive_local_calendar_days(repository: Repository) -> None:
    await add_user(repository)
    first = datetime(2026, 10, 20, 23, 30, tzinfo=UTC)
    next_day = datetime(2026, 10, 21, 1, 0, tzinfo=UTC)
    assert await repository.mark_active(42, first) == 1
    assert await repository.mark_active(42, first + timedelta(minutes=5)) == 1
    assert await repository.mark_active(42, next_day) == 2


@pytest.mark.asyncio
async def test_placement_answer_count_starts_with_the_selected_test(repository: Repository) -> None:
    await add_user(repository)
    await repository.save_message(42, "user", "old conversation")
    await repository.update_user(42, level="Определить тестом")
    assert await repository.count_placement_answers(42) == 0
    await repository.save_message(42, "user", "placement answer")
    assert await repository.count_placement_answers(42) == 1


@pytest.mark.asyncio
async def test_database_adds_placement_column_to_an_existing_schema(tmp_path: Path) -> None:
    path = tmp_path / "legacy.sqlite3"
    connection = await aiosqlite.connect(path)
    await connection.execute(
        """CREATE TABLE users (
            telegram_id INTEGER PRIMARY KEY, native_lang TEXT NOT NULL,
            target_lang TEXT NOT NULL, level TEXT NOT NULL, goal TEXT NOT NULL,
            interests TEXT NOT NULL DEFAULT '', mode TEXT NOT NULL DEFAULT 'dialogue',
            timezone TEXT NOT NULL DEFAULT 'UTC', reminder_time TEXT,
            streak INTEGER NOT NULL DEFAULT 0, last_active TEXT, created_at TEXT NOT NULL
        )"""
    )
    await connection.commit()
    await connection.close()

    database = Database(path)
    migrated = await database.connect()
    cursor = await migrated.execute("PRAGMA table_info(users)")
    columns = {row["name"] for row in await cursor.fetchall()}
    assert "placement_started_at" in columns
    await database.close()
