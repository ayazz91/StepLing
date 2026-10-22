"""SQLite connection lifecycle and schema initialization."""

from __future__ import annotations

from pathlib import Path

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    native_lang TEXT NOT NULL,
    target_lang TEXT NOT NULL,
    level TEXT NOT NULL,
    goal TEXT NOT NULL,
    interests TEXT NOT NULL DEFAULT '',
    mode TEXT NOT NULL DEFAULT 'dialogue',
    timezone TEXT NOT NULL DEFAULT 'UTC',
    reminder_time TEXT,
    streak INTEGER NOT NULL DEFAULT 0,
    last_active TEXT,
    placement_started_at TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS vocabulary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    word TEXT NOT NULL,
    translation TEXT NOT NULL,
    example TEXT NOT NULL DEFAULT '',
    box INTEGER NOT NULL DEFAULT 1 CHECK (box BETWEEN 1 AND 5),
    next_review TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(user_id, word)
);
CREATE TABLE IF NOT EXISTS mistakes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    example TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 1,
    last_seen TEXT NOT NULL,
    UNIQUE(user_id, category)
);
CREATE TABLE IF NOT EXISTS gemini_daily_usage (
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    usage_date TEXT NOT NULL,
    requests INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, usage_date)
);
CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id, id);
CREATE INDEX IF NOT EXISTS idx_vocabulary_user_id ON vocabulary(user_id);
CREATE INDEX IF NOT EXISTS idx_vocabulary_next_review ON vocabulary(user_id, next_review);
CREATE INDEX IF NOT EXISTS idx_mistakes_user_id ON mistakes(user_id);
CREATE INDEX IF NOT EXISTS idx_users_last_active ON users(last_active);
"""


class Database:
    """Own an aiosqlite connection and initialize the application schema."""

    def __init__(self, path: Path) -> None:
        """Create a database manager for the given file path."""
        self.path = path
        self.connection: aiosqlite.Connection | None = None

    async def connect(self) -> aiosqlite.Connection:
        """Open the database connection and initialize its schema."""
        if self.connection is not None:
            return self.connection
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = await aiosqlite.connect(str(self.path))
        self.connection.row_factory = aiosqlite.Row
        await self.connection.execute("PRAGMA foreign_keys = ON")
        await self.connection.executescript(SCHEMA)
        cursor = await self.connection.execute("PRAGMA table_info(users)")
        columns = {row["name"] for row in await cursor.fetchall()}
        if "placement_started_at" not in columns:
            await self.connection.execute(
                "ALTER TABLE users ADD COLUMN placement_started_at TEXT"
            )
        await self.connection.commit()
        return self.connection

    async def close(self) -> None:
        """Close the connection if it is open."""
        if self.connection is not None:
            await self.connection.close()
            self.connection = None
