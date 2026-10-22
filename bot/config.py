"""Application configuration loaded from environment variables."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated settings used to configure the bot."""

    telegram_bot_token: str
    gemini_api_key: str
    gemini_model: str
    database_path: Path
    redis_url: str | None
    gemini_daily_request_limit: int
    log_level: int
    rate_limit_per_minute: int
    admin_ids: frozenset[int]
    allowed_user_ids: frozenset[int] | None
    prompt_path: Path


def _parse_ids(value: str, name: str) -> frozenset[int]:
    """Parse a comma-separated list of Telegram IDs."""
    if not value.strip():
        return frozenset()
    try:
        return frozenset(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise ValueError(f"{name} must contain comma-separated integer Telegram IDs") from exc


def load_settings() -> Settings:
    """Load and validate application settings from the project .env file."""
    load_dotenv(PROJECT_ROOT / ".env")
    token = os.getenv("BOT_TOKEN", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not token:
        raise ValueError("BOT_TOKEN is required; configure it in .env")
    if not gemini_key:
        raise ValueError("GEMINI_API_KEY is required; configure it in .env")

    try:
        rate_limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
    except ValueError as exc:
        raise ValueError("RATE_LIMIT_PER_MINUTE must be a positive integer") from exc
    if rate_limit < 1:
        raise ValueError("RATE_LIMIT_PER_MINUTE must be a positive integer")

    try:
        daily_request_limit = int(os.getenv("GEMINI_DAILY_REQUEST_LIMIT", "100"))
    except ValueError as exc:
        raise ValueError("GEMINI_DAILY_REQUEST_LIMIT must be a non-negative integer") from exc
    if daily_request_limit < 0:
        raise ValueError("GEMINI_DAILY_REQUEST_LIMIT must be a non-negative integer")

    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, None)
    if not isinstance(log_level, int):
        raise ValueError(f"Unknown LOG_LEVEL: {log_level_name}")

    allowed_ids_raw = os.getenv("ALLOWED_USER_IDS", "").strip()
    allowed_ids = _parse_ids(allowed_ids_raw, "ALLOWED_USER_IDS") if allowed_ids_raw else None

    return Settings(
        telegram_bot_token=token,
        gemini_api_key=gemini_key,
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip(),
        database_path=Path(os.getenv("DATABASE_PATH", "data/tutor.sqlite3")),
        redis_url=os.getenv("REDIS_URL", "").strip() or None,
        gemini_daily_request_limit=daily_request_limit,
        log_level=log_level,
        rate_limit_per_minute=rate_limit,
        admin_ids=_parse_ids(os.getenv("ADMIN_IDS", ""), "ADMIN_IDS"),
        allowed_user_ids=allowed_ids,
        prompt_path=Path(os.getenv("PROMPT_PATH", str(PROJECT_ROOT / "prompts" / "tutor_system.md"))),
    )
