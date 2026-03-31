"""Per-user TTL cache for get_run_insight JSON (Topic 5)."""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional

from src.smartcoach_mobile_coach.config import SMARTCOACH_MOBILE_INSIGHT_CACHE_TTL

_lock = threading.Lock()
_store: Dict[str, tuple[float, Dict[str, Any]]] = {}


def cache_key(user_id: str, activity_id: int, schema_version: str) -> str:
    return f"{user_id}:{activity_id}:insight:{schema_version}"


def get_cached(key: str) -> Optional[Dict[str, Any]]:
    now = time.time()
    with _lock:
        hit = _store.get(key)
        if not hit:
            return None
        exp, val = hit
        if now > exp:
            del _store[key]
            return None
        return val


def set_cached(
    key: str, payload: Dict[str, Any], ttl_sec: Optional[int] = None
) -> None:
    ttl = ttl_sec if ttl_sec is not None else SMARTCOACH_MOBILE_INSIGHT_CACHE_TTL
    with _lock:
        _store[key] = (time.time() + ttl, payload)


def invalidate_user_activity(
    user_id: str, activity_id: int, schema_version: str
) -> None:
    k = cache_key(user_id, activity_id, schema_version)
    with _lock:
        _store.pop(k, None)
