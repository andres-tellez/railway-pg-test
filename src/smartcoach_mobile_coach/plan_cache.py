"""
Per-user in-memory cache for plan-aware LLM tools (V1.6 Phase B 3B.8 / Topic 5).

Scope
-----
Backs three plan-aware tools whose payloads are expensive to rebuild
yet change rarely:

* :func:`tool_get_weekly_plan` — keyed on
  ``(user_id, week_start_iso, tz, today_iso)``.
* :func:`tool_get_plan_overview` — keyed on ``(user_id, tz, today_iso)``.
* :func:`tool_get_phase_analysis` — keyed on
  ``(user_id, phase_id, tz, today_iso)``.

Topic 5 says "past-week cache-friendly, future-week invalidates on
adaptation rewrite". We achieve both properties with a **single TTL**
cache plus **explicit invalidation on write**:

* The cache key embeds ``today_iso`` so a day-rollover is a natural
  miss. Past-week payloads are byte-identical day over day (nothing
  mutates them), so the first-of-day rebuild is cheap and every other
  request in the day is a hit.
* Current-week payloads DO change when a new activity lands; the TTL
  (configurable via ``SMARTCOACH_MOBILE_PLAN_CACHE_TTL``, default 300s)
  bounds staleness without requiring an invalidation hook on every
  activity upload.
* Future-week payloads only change when the plan is rewritten.
  :func:`tool_generate_training_plan` already invalidates
  ``user_context_cache``; the V1.6 hook in this module lets it
  invalidate plan-tool entries in the same post-commit step, so a
  rewrite heals instantly instead of waiting on TTL.

Design notes
------------
* Module-global dict guarded by a ``threading.Lock`` — same pattern as
  ``user_context_cache`` and ``insight_cache``. Multi-worker gunicorn
  processes each keep their own copy; writes invalidate the **same**
  process that served the read and the TTL caps staleness.
* Error envelopes (``{"error": ...}``) are **not** cached — a transient
  ``no_plan`` / ``invalid_user_id`` is cheap to recompute and caching
  would mask a race-after-signup edge case.
* The cached payload is **stored by reference**; callers must treat
  it as read-only (the LLM tool boundary serializes with
  ``json.dumps`` before sending to OpenAI, so mutation there is
  structurally impossible).
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, Optional

_DEFAULT_TTL_SEC = 300

# Cache-version suffix embedded in every key. Bump when the shape of
# any plan-tool payload changes in a way that would make a cached
# entry from a previous deployment unsafe to serve — a deployed rev
# that bumps this cannot serve stale shapes from a long-running
# worker's cache.
PLAN_CACHE_SCHEMA_VERSION = 1


def _cache_ttl_sec() -> int:
    """Read TTL from env on each set — lets tests bump TTL without reloading the module."""
    raw = (os.getenv("SMARTCOACH_MOBILE_PLAN_CACHE_TTL") or "").strip()
    if not raw:
        return _DEFAULT_TTL_SEC
    try:
        return max(0, int(raw))
    except ValueError:
        return _DEFAULT_TTL_SEC


_lock = threading.Lock()
_store: Dict[str, tuple[float, Dict[str, Any]]] = {}


def _key(
    kind: str,
    user_id: str,
    *,
    tz: str,
    today_iso: str,
    extra: str = "",
) -> str:
    """
    Build the cache key. ``kind`` is the tool name so different tools
    never collide; ``extra`` carries tool-specific keying (week_start_iso
    for weekly_plan, phase_id for phase_analysis). ``user_id`` is the
    prefix so :func:`invalidate_user_plan_cache` can sweep all of a
    user's entries without iterating every key kind.
    """
    return f"{user_id}:{kind}:{tz}:{today_iso}:{extra}:v{PLAN_CACHE_SCHEMA_VERSION}"


def get_cached(
    kind: str,
    user_id: str,
    *,
    tz: str,
    today_iso: str,
    extra: str = "",
) -> Optional[Dict[str, Any]]:
    """Return a cached payload if present AND unexpired."""
    key = _key(kind, user_id, tz=tz, today_iso=today_iso, extra=extra)
    now = time.time()
    with _lock:
        hit = _store.get(key)
        if not hit:
            return None
        expires_at, payload = hit
        if now > expires_at:
            _store.pop(key, None)
            return None
        return payload


def set_cached(
    kind: str,
    user_id: str,
    payload: Dict[str, Any],
    *,
    tz: str,
    today_iso: str,
    extra: str = "",
    ttl_sec: Optional[int] = None,
) -> None:
    """Cache a successful plan-tool payload.

    Error envelopes (dicts with an ``error`` key) are NOT cached — see
    module docstring. TTL defaults to
    ``SMARTCOACH_MOBILE_PLAN_CACHE_TTL`` (5 minutes).
    """
    if not isinstance(payload, dict) or "error" in payload:
        return
    ttl = ttl_sec if ttl_sec is not None else _cache_ttl_sec()
    if ttl <= 0:
        return
    key = _key(kind, user_id, tz=tz, today_iso=today_iso, extra=extra)
    with _lock:
        _store[key] = (time.time() + ttl, payload)


def invalidate_user_plan_cache(user_id: str) -> int:
    """Drop every cached plan-tool entry for a single user.

    Call from any write path that mutates a plan input (regenerate
    plan, rewrite weekly template, edit a single workout). Returns
    the number of entries cleared (mostly for tests / logging).
    """
    if not user_id:
        return 0
    prefix = f"{user_id}:"
    with _lock:
        keys = [k for k in _store if k.startswith(prefix)]
        for k in keys:
            _store.pop(k, None)
    return len(keys)


def clear_all() -> None:
    """Wipe the cache entirely — test hook."""
    with _lock:
        _store.clear()
