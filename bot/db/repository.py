"""Parameterized SQLite queries for users, conversations, vocabulary, and stats."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import aiosqlite

User = dict[str, Any]
LEITNER_DAYS: tuple[int, ...] = (1, 3, 7, 14, 30)


def utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""
    return datetime.now(UTC)


class Repository:
    """Provide typed, parameterized operations on the bot database."""

    def __init__(self, connection: aiosqlite.Connection) -> None:
        """Create a repository bound to an open SQLite connection."""
        self.connection = connection

    async def create_user(self, telegram_id: int, profile: dict[str, str]) -> None:
        """Insert or update a completed onboarding profile."""
        now = utc_now().isoformat()
        await self.connection.execute(
            """INSERT INTO users
               (telegram_id, native_lang, target_lang, level, goal, interests, mode,
                timezone, reminder_time, placement_started_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'dialogue', ?, ?, ?, ?)
               ON CONFLICT(telegram_id) DO UPDATE SET
                 native_lang=excluded.native_lang, target_lang=excluded.target_lang,
                 level=excluded.level, goal=excluded.goal, interests=excluded.interests,
                 timezone=excluded.timezone, reminder_time=excluded.reminder_time,
                 placement_started_at=excluded.placement_started_at""",
            (
                telegram_id,
                profile["native_lang"],
                profile["target_lang"],
                profile["level"],
                profile["goal"],
                profile["interests"],
                profile["timezone"],
                profile["reminder_time"] or None,
                now if profile["level"] == "Определить тестом" else None,
                now,
            ),
        )
        await self.connection.commit()

    async def get_user(self, telegram_id: int) -> User | None:
        """Return the profile for one Telegram user, if it exists."""
        cursor = await self.connection.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row is not None else None

    async def update_user(self, telegram_id: int, **values: str | int | None) -> None:
        """Update a set of known profile columns using parameterized values."""
        allowed = {"native_lang", "target_lang", "level", "goal", "interests", "mode",
                   "timezone", "reminder_time"}
        if not values or values.keys() - allowed:
            raise ValueError("Only known user profile fields can be updated")
        updates = dict(values)
        if "level" in updates:
            updates["placement_started_at"] = (
                utc_now().isoformat()
                if updates["level"] == "Определить тестом" else None
            )
        columns = ", ".join(f"{column} = ?" for column in updates)
        await self.connection.execute(
            f"UPDATE users SET {columns} WHERE telegram_id = ?",
            (*updates.values(), telegram_id),
        )
        await self.connection.commit()

    async def delete_user(self, telegram_id: int) -> None:
        """Delete a user and all related data."""
        await self.connection.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))
        await self.connection.commit()

    async def save_message(self, telegram_id: int, role: str, content: str) -> None:
        """Append a conversation message."""
        if role not in {"user", "assistant"}:
            raise ValueError("role must be user or assistant")
        await self.connection.execute(
            "INSERT INTO messages (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (telegram_id, role, content, utc_now().isoformat()),
        )
        await self.connection.commit()

    async def get_history(self, telegram_id: int, limit: int = 15) -> list[dict[str, str]]:
        """Return the most recent conversation turns in chronological order."""
        cursor = await self.connection.execute(
            """SELECT role, content FROM
               (SELECT id, role, content FROM messages WHERE user_id = ?
                ORDER BY id DESC LIMIT ?) ORDER BY id ASC""",
            (telegram_id, limit),
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def count_placement_answers(self, telegram_id: int) -> int:
        """Count learner messages sent since the current level-placement test began."""
        cursor = await self.connection.execute(
            """SELECT COUNT(messages.id) AS total
               FROM users
               LEFT JOIN messages ON messages.user_id = users.telegram_id
                 AND messages.role = 'user'
                 AND messages.created_at >= users.placement_started_at
               WHERE users.telegram_id = ? AND users.placement_started_at IS NOT NULL""",
            (telegram_id,),
        )
        row = await cursor.fetchone()
        return int(row["total"])

    async def clear_history(self, telegram_id: int) -> None:
        """Delete only the conversation history for one user."""
        await self.connection.execute("DELETE FROM messages WHERE user_id = ?", (telegram_id,))
        await self.connection.commit()

    async def mark_active(self, telegram_id: int, active_at: datetime | None = None) -> int:
        """Update activity and return the user's current consecutive-day streak."""
        current = active_at or utc_now()
        cursor = await self.connection.execute(
            "SELECT last_active, streak, timezone FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return 0
        timezone = ZoneInfo(row["timezone"])
        local_today = current.astimezone(timezone).date()
        last = (
            datetime.fromisoformat(row["last_active"]).astimezone(timezone).date()
            if row["last_active"] else None
        )
        streak = int(row["streak"])
        if last != local_today:
            streak = streak + 1 if last == local_today - timedelta(days=1) else 1
        await self.connection.execute(
            "UPDATE users SET last_active = ?, streak = ? WHERE telegram_id = ?",
            (current.isoformat(), streak, telegram_id),
        )
        await self.connection.commit()
        return streak

    async def add_vocabulary(
        self, telegram_id: int, word: str, translation: str, example: str = "",
    ) -> None:
        """Add a word unless it is already present for the user."""
        now = utc_now()
        await self.connection.execute(
            """INSERT INTO vocabulary
               (user_id, word, translation, example, box, next_review, created_at)
               VALUES (?, ?, ?, ?, 1, ?, ?)
               ON CONFLICT(user_id, word) DO NOTHING""",
            (
                telegram_id, word.strip(), translation.strip(), example.strip(),
                now.isoformat(), now.isoformat(),
            ),
        )
        await self.connection.commit()

    async def list_vocabulary(self, telegram_id: int, limit: int = 20) -> list[dict[str, Any]]:
        """Return a user's newest saved words."""
        cursor = await self.connection.execute(
            "SELECT * FROM vocabulary WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (telegram_id, limit),
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def due_vocabulary(self, telegram_id: int, now: datetime | None = None) -> list[dict[str, Any]]:
        """Return words whose scheduled review time has arrived."""
        cursor = await self.connection.execute(
            "SELECT * FROM vocabulary WHERE user_id = ? AND next_review <= ? ORDER BY next_review",
            (telegram_id, (now or utc_now()).isoformat()),
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def update_review(self, word_id: int, correct: bool, now: datetime | None = None) -> None:
        """Advance a correct word or reset a missed word to the first Leitner box."""
        current = now or utc_now()
        cursor = await self.connection.execute("SELECT box FROM vocabulary WHERE id = ?", (word_id,))
        row = await cursor.fetchone()
        if row is None:
            return
        box = min(int(row["box"]) + 1, 5) if correct else 1
        due_at = current + timedelta(days=LEITNER_DAYS[box - 1])
        await self.connection.execute(
            "UPDATE vocabulary SET box = ?, next_review = ? WHERE id = ?",
            (box, due_at.isoformat(), word_id),
        )
        await self.connection.commit()

    async def record_mistake(self, telegram_id: int, category: str, example: str) -> None:
        """Create or increment a recurring mistake category."""
        await self.connection.execute(
            """INSERT INTO mistakes (user_id, category, example, count, last_seen)
               VALUES (?, ?, ?, 1, ?)
               ON CONFLICT(user_id, category) DO UPDATE SET
                 example=excluded.example, count=count + 1, last_seen=excluded.last_seen""",
            (telegram_id, category, example, utc_now().isoformat()),
        )
        await self.connection.commit()

    async def known_mistakes(self, telegram_id: int, limit: int = 10) -> list[dict[str, Any]]:
        """Return the most frequent mistake patterns."""
        cursor = await self.connection.execute(
            "SELECT category, example, count FROM mistakes WHERE user_id = ? "
            "ORDER BY count DESC, last_seen DESC LIMIT ?",
            (telegram_id, limit),
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def stats(self, telegram_id: int) -> dict[str, Any]:
        """Return message, vocabulary, streak, and common-error statistics."""
        cursor = await self.connection.execute(
            """SELECT
                 (SELECT COUNT(*) FROM messages WHERE user_id = ?) AS messages,
                 (SELECT COUNT(*) FROM vocabulary WHERE user_id = ?) AS words,
                 (SELECT streak FROM users WHERE telegram_id = ?) AS streak""",
            (telegram_id, telegram_id, telegram_id),
        )
        row = await cursor.fetchone()
        return dict(row) if row is not None else {"messages": 0, "words": 0, "streak": 0}

    async def all_reminders(self) -> list[dict[str, Any]]:
        """Return users who have a daily reminder configured."""
        cursor = await self.connection.execute(
            "SELECT telegram_id, timezone, reminder_time FROM users WHERE reminder_time IS NOT NULL"
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def disable_reminder(self, telegram_id: int) -> None:
        """Turn off reminders for a user who cannot be reached."""
        await self.update_user(telegram_id, reminder_time=None)

    async def admin_stats(self, since: datetime | None = None) -> dict[str, int]:
        """Return total users and users active since the given UTC time."""
        moment = since or (utc_now() - timedelta(days=1))
        cursor = await self.connection.execute(
            """SELECT COUNT(*) AS users,
               SUM(CASE WHEN last_active >= ? THEN 1 ELSE 0 END) AS active
               FROM users""",
            (moment.isoformat(),),
        )
        row = await cursor.fetchone()
        return {"users": int(row["users"] or 0), "active": int(row["active"] or 0)}
