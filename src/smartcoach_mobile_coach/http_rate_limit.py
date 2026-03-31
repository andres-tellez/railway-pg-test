"""Stricter per-user HTTP rate limit for agent-messages only (Topic 7)."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Tuple

from src.smartcoach_mobile_coach.config import SMARTCOACH_MOBILE_AGENT_HTTP_RPM

_window_sec = 60.0
_storage: dict[str, deque] = defaultdict(lambda: deque())


def _cleanup(user_id: str) -> None:
    now = time.time()
    cutoff = now - _window_sec
    q = _storage[user_id]
    while q and q[0] < cutoff:
        q.popleft()


def can_make_agent_http_request(user_id: str) -> Tuple[bool, float]:
    limit = max(1, SMARTCOACH_MOBILE_AGENT_HTTP_RPM)
    _cleanup(user_id)
    q = _storage[user_id]
    if len(q) >= limit:
        oldest = q[0]
        retry_after = max(0.0, (oldest + _window_sec) - time.time())
        return False, retry_after
    return True, 0.0


def record_agent_http_request(user_id: str) -> None:
    _storage[user_id].append(time.time())
