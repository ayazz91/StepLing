"""In-memory per-user request rate limiter."""

from __future__ import annotations

import time
from collections import defaultdict, deque


class RateLimiter:
    """Allow a configured number of actions per user in a rolling minute."""

    def __init__(self, limit: int, period_seconds: float = 60.0) -> None:
        """Create a limiter for the specified rolling time window."""
        self.limit = limit
        self.period_seconds = period_seconds
        self._requests: dict[int, deque[float]] = defaultdict(deque)

    def allow(self, user_id: int, now: float | None = None) -> bool:
        """Return whether this request fits the user's configured quota."""
        moment = now if now is not None else time.monotonic()
        queue = self._requests[user_id]
        while queue and moment - queue[0] >= self.period_seconds:
            queue.popleft()
        if len(queue) >= self.limit:
            return False
        queue.append(moment)
        return True
