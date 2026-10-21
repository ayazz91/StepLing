from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.services.llm import TutorLLM
from bot.services.rate_limit import RateLimiter


@pytest.mark.asyncio
async def test_llm_uses_mocked_official_async_generate_content_api() -> None:
    generate_content = AsyncMock(return_value=SimpleNamespace(text="Hola"))
    client = SimpleNamespace(
        aio=SimpleNamespace(
            models=SimpleNamespace(generate_content=generate_content),
            aclose=AsyncMock(),
        )
    )
    llm = TutorLLM("not-a-real-key", "gemini-test", client=client)

    result = await llm.respond(
        "System prompt",
        [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi"}],
    )

    assert result == "Hola"
    assert generate_content.await_args.kwargs["model"] == "gemini-test"
    assert [item.role for item in generate_content.await_args.kwargs["contents"]] == ["user", "model"]
    await llm.close()
    client.aio.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_llm_retries_two_transient_server_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class ServerError(Exception):
        status_code = 503

    generate_content = AsyncMock(side_effect=[
        ServerError("temporary"),
        ServerError("temporary"),
        SimpleNamespace(text="Recovered"),
    ])
    sleep = AsyncMock()
    monkeypatch.setattr("bot.services.llm.asyncio.sleep", sleep)
    monkeypatch.setattr("bot.services.llm.random.uniform", lambda _low, _high: 0)
    client = SimpleNamespace(
        aio=SimpleNamespace(
            models=SimpleNamespace(generate_content=generate_content),
            aclose=AsyncMock(),
        )
    )
    llm = TutorLLM("not-a-real-key", "gemini-test", client=client)

    assert await llm.respond("prompt", [{"role": "user", "content": "hello"}]) == "Recovered"
    assert generate_content.await_count == 3
    assert [call.args[0] for call in sleep.await_args_list] == [0.5, 1.0]


def test_rate_limiter_uses_a_rolling_window() -> None:
    limiter = RateLimiter(limit=2, period_seconds=60)
    assert limiter.allow(1, now=100)
    assert limiter.allow(1, now=110)
    assert not limiter.allow(1, now=120)
    assert limiter.allow(1, now=160)
    assert limiter.allow(2, now=120)
