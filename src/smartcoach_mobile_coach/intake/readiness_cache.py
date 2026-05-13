"""In-process readiness gate cache (Phase 7 — keyed by user, digest, evidence id, alignment)."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from sqlalchemy.orm import Session

from src.coaching_intelligence.policy.policy_table import POLICY_VERSION

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
# Key: (user_id, digest_sha256, evidence_snapshot_id, alignment_enabled)
_READINESS_CACHE: Dict[Tuple[str, str, str, bool], _ReadinessCacheEntry] = {}


def _cache_ttl_seconds() -> int:
    raw = (os.getenv(_CACHE_TTL_ENV) or str(_CACHE_TTL_DEFAULT_SEC)).strip()
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        parsed = _CACHE_TTL_DEFAULT_SEC
    return max(_CACHE_TTL_MIN_SEC, min(_CACHE_TTL_MAX_SEC, parsed))


def _plan_request_digest_sha256(plan_request: Dict[str, Any]) -> str:
    blob = json.dumps(plan_request or {}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _get_cached_entry(
    *,
    cache_key: Tuple[str, str, str, bool],
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
    cache_key: Tuple[str, str, str, bool],
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
    ev_for_lookup = (
        str(prior_readiness.get("evidence_snapshot_id") or "")
        if prior_readiness is not None
        else ""
    )
    cache_key_lookup = (
        str(internal_user_id),
        digest_sha256,
        ev_for_lookup,
        bool(alignment_enabled),
    )

    if prior_readiness is not None:
        entry = _get_cached_entry(cache_key=cache_key_lookup, now_mono=now_mono)
        if entry is not None:
            return ReadinessGateResult(
                assessment_api=copy.deepcopy(entry.assessment_api),
                readiness_api=copy.deepcopy(entry.readiness_api),
                plan_request_digest_sha256=digest_sha256,
                cache_status="hit",
            )

    from src.smartcoach_mobile_coach import readiness_gate as _rg

    assessment = _rg.build_pre_generation_runner_assessment(
        session,
        str(internal_user_id),
        plan_request=plan_request,
        plan_intake_state=plan_intake_state,
        alignment_enabled=alignment_enabled,
    )
    assessment_api = assessment.as_api_dict()
    readiness_api = _rg.evaluate_plan_generation_readiness(
        plan_request=plan_request,
        assessment_api=assessment_api,
        trace_id=str(uuid.uuid4()),
    )

    ev_store = str(readiness_api.get("evidence_snapshot_id") or "") or str(
        assessment_api.get("evidence_snapshot_id") or ""
    )
    cache_key_store = (
        str(internal_user_id),
        digest_sha256,
        ev_store,
        bool(alignment_enabled),
    )

    _set_cached_entry(
        cache_key=cache_key_store,
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
