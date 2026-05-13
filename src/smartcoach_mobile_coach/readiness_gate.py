"""Shared readiness-gate evaluation with short-lived in-process caching.

Purpose:
- Prevent same-intent drift between orchestrator runner-review build and
  ``tool_generate_training_plan``.
- Reuse one assessment snapshot + readiness verdict for a short TTL window
  keyed by user + plan-request digest.
"""

from __future__ import annotations

import copy
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from sqlalchemy.orm import Session

from src.coaching_intelligence.plan_generation_readiness import (
    evaluate_plan_generation_readiness,
)
from src.coaching_intelligence.policy.policy_table import POLICY_VERSION
from src.coaching_intelligence.pre_generation_runner_assessment import (
    build_pre_generation_runner_assessment,
)

_CACHE_TTL_ENV = "SMARTCOACH_READINESS_GATE_CACHE_TTL_SEC"
_CACHE_TTL_DEFAULT_SEC = 30
_CACHE_TTL_MIN_SEC = 5
_CACHE_TTL_MAX_SEC = 120


@dataclass(frozen=True)
class ReadinessGateResult:
    assessment_api: Dict[str, Any]
    readiness_api: Dict[str, Any]
    plan_request_digest_sha256: str
    cache_status: str  # "hit" | "miss"


@dataclass
class _ReadinessCacheEntry:
    created_monotonic: float
    policy_version: str
    assessment_api: Dict[str, Any]
    readiness_api: Dict[str, Any]


_READINESS_CACHE_LOCK = threading.Lock()
_READINESS_CACHE: Dict[Tuple[str, str, bool], _ReadinessCacheEntry] = {}


def _cache_ttl_seconds() -> int:
    raw = (os.getenv(_CACHE_TTL_ENV) or str(_CACHE_TTL_DEFAULT_SEC)).strip()
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        parsed = _CACHE_TTL_DEFAULT_SEC
    return max(_CACHE_TTL_MIN_SEC, min(_CACHE_TTL_MAX_SEC, parsed))


def _plan_request_digest_sha256(plan_request: Dict[str, Any]) -> str:
    blob = json.dumps(plan_request or {}, sort_keys=True, default=str)
    import hashlib

    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _get_cached_entry(
    *,
    cache_key: Tuple[str, str, bool],
    now_mono: float,
) -> _ReadinessCacheEntry | None:
    ttl = float(_cache_ttl_seconds())
    with _READINESS_CACHE_LOCK:
        entry = _READINESS_CACHE.get(cache_key)
        if entry is None:
            return None
        if (now_mono - entry.created_monotonic) > ttl:
            _READINESS_CACHE.pop(cache_key, None)
            return None
        if str(entry.policy_version) != str(POLICY_VERSION):
            _READINESS_CACHE.pop(cache_key, None)
            return None
        return entry


def _set_cached_entry(
    *,
    cache_key: Tuple[str, str, bool],
    now_mono: float,
    assessment_api: Dict[str, Any],
    readiness_api: Dict[str, Any],
) -> None:
    with _READINESS_CACHE_LOCK:
        _READINESS_CACHE[cache_key] = _ReadinessCacheEntry(
            created_monotonic=now_mono,
            policy_version=str(POLICY_VERSION),
            assessment_api=copy.deepcopy(assessment_api),
            readiness_api=copy.deepcopy(readiness_api),
        )


def get_or_compute_readiness_gate(
    *,
    session: Session,
    internal_user_id: str,
    plan_request: Dict[str, Any],
    plan_intake_state: Dict[str, Any],
    alignment_enabled: bool,
) -> ReadinessGateResult:
    """Return one assessment+readiness pair for a short intent window."""
    digest_sha256 = _plan_request_digest_sha256(plan_request)
    cache_key = (str(internal_user_id), digest_sha256, bool(alignment_enabled))
    now_mono = time.monotonic()
    ux = (
        plan_intake_state.get("ux")
        if isinstance(plan_intake_state.get("ux"), dict)
        else {}
    )
    prior_readiness = (
        ux.get("plan_generation_readiness")
        if isinstance(ux.get("plan_generation_readiness"), dict)
        else None
    )

    # Only reuse cached readiness when the current state already carries a prior
    # readiness snapshot (same-intent follow-up). This avoids stale cross-turn
    # cache hits for new intents that happen to share the same draft digest.
    if prior_readiness is not None:
        entry = _get_cached_entry(cache_key=cache_key, now_mono=now_mono)
        if entry is not None:
            return ReadinessGateResult(
                assessment_api=copy.deepcopy(entry.assessment_api),
                readiness_api=copy.deepcopy(entry.readiness_api),
                plan_request_digest_sha256=digest_sha256,
                cache_status="hit",
            )

    assessment = build_pre_generation_runner_assessment(
        session,
        str(internal_user_id),
        plan_request=plan_request,
        plan_intake_state=plan_intake_state,
        alignment_enabled=alignment_enabled,
    )
    assessment_api = assessment.as_api_dict()
    readiness_api = evaluate_plan_generation_readiness(
        plan_request=plan_request,
        assessment_api=assessment_api,
        trace_id=str(uuid.uuid4()),
    )

    _set_cached_entry(
        cache_key=cache_key,
        now_mono=now_mono,
        assessment_api=assessment_api,
        readiness_api=readiness_api,
    )
    return ReadinessGateResult(
        assessment_api=assessment_api,
        readiness_api=readiness_api,
        plan_request_digest_sha256=digest_sha256,
        cache_status="miss",
    )


def _clear_readiness_gate_cache_for_tests() -> None:
    """Test helper: clear in-process cache between test cases."""
    with _READINESS_CACHE_LOCK:
        _READINESS_CACHE.clear()
