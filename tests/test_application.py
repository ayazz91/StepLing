from pathlib import Path

import pytest

from bot.config import Settings, _parse_review_intervals
from bot.main import create_dispatcher
from bot.services.rate_limit import RateLimiter


def test_dispatcher_registers_all_feature_routers_and_middleware() -> None:
    settings = Settings(
        telegram_bot_token="test-token",
        gemini_api_key="test-key",
        gemini_model="gemini-test",
        database_path=Path(":memory:"),
        redis_url=None,
        gemini_daily_request_limit=100,
        log_level=20,
        rate_limit_per_minute=10,
        admin_ids=frozenset(),
        allowed_user_ids=frozenset({123}),
        prompt_path=Path("prompts/tutor_system.md"),
    )

    dispatcher = create_dispatcher(settings, RateLimiter(10))

    assert [router.name for router in dispatcher.sub_routers] == [
        "start", "settings", "vocabulary", "stats", "modes", "chat",
    ]
    assert len(dispatcher.message.outer_middleware) == 2
    assert len(dispatcher.callback_query.outer_middleware) == 1


def test_review_interval_configuration_requires_five_increasing_positive_days() -> None:
    assert _parse_review_intervals("1, 2, 5, 10, 21") == (1, 2, 5, 10, 21)
    for invalid in ("1,2,3", "1,2,0,10,20", "1,2,2,10,20", "1,2,x,10,20"):
        with pytest.raises(ValueError):
            _parse_review_intervals(invalid)
