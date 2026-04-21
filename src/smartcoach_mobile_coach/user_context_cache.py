"""
Per-user in-memory cache for :func:`tool_get_user_context` (V1.6 Phase B 3B.12).

The payload is a pure function of
``(user_identity × plan × plan_workouts × user_coach_preferences × user_profile
× user_athletes × last-28-days activities × today)``. In a single chat
turn the orchestrator may call ``get_user_context`` once and have its
prompt-nudge (3B.13) land — but on subsequent loops within the same
turn or adjacent requests (e.g. same-session back-to-back user
messages), the model may re-ask the tool. Repeating the DB fan-out on
every call is wasteful; the payload is tiny and bounded (3B.11 budget
<2 KB) so we cache it per ``(user_id, tz, today)``.

Invalidation
------------
The cache is invalidated:

* **On write** — when any producer input mutates. The shipped write
  paths are :func:`tool_save_coach_preference` (user_coach_preferences
  update), :func:`tool_update_plan_intake` and
  :func:`tool_generate_training_plan` (plan / plan_workouts / training
  days), and :func:`tool_link_strava_account` (user_athletes link —
  flips ``baseline_status`` from ``None`` to a real band). All of these
  call :func:`invalidate_user_context` after the DB commit so the next
  ``get_user_context`` read rebuilds from fresh state.
* **On TTL expiry** — short TTL (configurable via
  ``SMARTCOACH_MOBILE_USER_CONTEXT_CACHE_TTL``, default 600s) so that
  ambient state changes (new activity landing, day-rollover) heal
  themselves even if a write path forgot to call
  :func:`invalidate_user_context`.
* **On day rollover** — the cache key includes ``today_iso``, so a
  request on a new local calendar day is a natural cache miss and
  rebuilds ``race_goal.weeks_until_race`` / ``plan.current_week_number``
  / ``today`` correctly without an explicit invalidation.

Design notes
------------
* Module-global dict guarded by a ``threading.Lock`` — matches the
  pattern used by ``insight_cache.py`` (Topic 5 single-process cache;
  multi-worker gunicorn processes each keep their own copy, which is
  fine because writes invalidate the **same** process that served the
  read and the TTL caps staleness).
* The cached payload is **stored by reference** — callers SHOULD NOT
  mutate the returned dict (the LLM tool boundary serializes it with
  ``json.dumps`` before sending to OpenAI, which is read-only).
* Error envelopes (``{"error": ...}``) are **not** cached — a transient
  ``no_user`` or ``invalid_user_id`` is cheap to recompute and caching
  it would mask a race-after-signup edge case.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, Optional

_DEFAULT_TTL_SEC = 600


def _cache_ttl_sec() -> int:
    """Read TTL from env on each set — lets tests bump TTL without reloading the module."""
    raw = (os.getenv("SMARTCOACH_MOBILE_USER_CONTEXT_CACHE_TTL") or "").strip()
    if not raw:
        return _DEFAULT_TTL_SEC
    try:
        return max(0, int(raw))
    except ValueError:
        return _DEFAULT_TTL_SEC


_lock = threading.Lock()
_store: Dict[str, tuple[float, Dict[str, Any]]] = {}


def _key(user_id: str, tz: str, today_iso: str) -> str:
    # Schema-version suffix in the key lets a deployed rev that bumps
    # USER_CONTEXT_SCHEMA_VERSION avoid serving stale shape from a
    # long-running worker.
    from src.services.user.user_context import USER_CONTEXT_SCHEMA_VERSION

    return f"{user_id}:{tz}:{today_iso}:v{USER_CONTEXT_SCHEMA_VERSION}"


def get_cached(user_id: str, tz: str, today_iso: str) -> Optional[Dict[str, Any]]:
    """Return the cached payload for this key if it is still fresh, else ``None``."""
    key = _key(user_id, tz, today_iso)
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
    user_id: str,
    tz: str,
    today_iso: str,
    payload: Dict[str, Any],
    *,
    ttl_sec: Optional[int] = None,
) -> None:
    """Cache a successful ``user_context`` payload.

    Error envelopes (dicts with an ``error`` key) are NOT cached — see
    module docstring. TTL defaults to
    ``SMARTCOACH_MOBILE_USER_CONTEXT_CACHE_TTL`` (10 minutes).
    """
    if not isinstance(payload, dict) or "error" in payload:
        return
    ttl = ttl_sec if ttl_sec is not None else _cache_ttl_sec()
    if ttl <= 0:
        return
    key = _key(user_id, tz, today_iso)
    with _lock:
        _store[key] = (time.time() + ttl, payload)


def invalidate_user_context(user_id: str) -> int:
    """Drop every cached entry for a single user.

    Call from any write path that mutates an input of
    ``build_user_context_payload`` (plan, plan_workouts,
    user_coach_preferences, user_profile, user_athletes). Returns the
    number of entries cleared (mostly for tests / logging).
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
