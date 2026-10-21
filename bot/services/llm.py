"""Async Google GenAI client wrapper with bounded retries and request timeout."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Sequence
from typing import Any

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class TutorLLM:
    """Generate tutor responses using the official Google GenAI async client."""

    def __init__(
        self, api_key: str, model: str, timeout_seconds: float = 30.0,
        client: Any | None = None,
    ) -> None:
        """Initialize the Gemini client or accept a test double."""
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.client = client or genai.Client(api_key=api_key)

    async def respond(self, system_prompt: str, history: Sequence[dict[str, str]]) -> str:
        """Generate a text response, retrying transient HTTP 429 and 5xx failures."""
        contents = [
            types.Content(
                role="user" if item["role"] == "user" else "model",
                parts=[types.Part(text=item["content"])],
            )
            for item in history
        ]
        for attempt in range(3):
            try:
                response = await asyncio.wait_for(
                    self.client.aio.models.generate_content(
                        model=self.model,
                        contents=contents,
                        config=types.GenerateContentConfig(system_instruction=system_prompt),
                    ),
                    timeout=self.timeout_seconds,
                )
                text = getattr(response, "text", None)
                if not text:
                    raise RuntimeError("Gemini returned an empty response")
                return str(text).strip()
            except asyncio.TimeoutError:
                raise
            except Exception as exc:
                status = self._status_code(exc)
                if status != 429 and not (status is not None and 500 <= status <= 599):
                    raise
                if attempt == 2:
                    raise
                delay = 0.5 * (2 ** attempt) + random.uniform(0, 0.2)
                logger.warning("Gemini transient HTTP %s; retrying in %.1fs", status, delay)
                await asyncio.sleep(delay)
        raise RuntimeError("Gemini request attempts exhausted")

    @staticmethod
    def _status_code(error: Exception) -> int | None:
        """Read an HTTP status from GenAI or HTTP client exceptions."""
        for attribute in ("code", "status_code"):
            status = getattr(error, attribute, None)
            if isinstance(status, int):
                return status
        response = getattr(error, "response", None)
        status = getattr(response, "status_code", None)
        return status if isinstance(status, int) else None

    async def close(self) -> None:
        """Close the async GenAI client and release its HTTP resources."""
        await self.client.aio.aclose()
