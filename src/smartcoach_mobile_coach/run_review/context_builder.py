"""
Resolve a run and gather everything the LLM needs to review it.

This file is the only place that talks to the DB / agent tools for V2.
It deliberately mirrors the tool surface used by ``run_recap_fastpath``
(find_runs_by_date / search_runs / get_run_summary / get_run_splits)
so we don't duplicate ownership/validation logic.

Flow:

1. **Resolve activity id**: explicit hint > thread context > anchor date >
   most-recent run (when classifier asked for ``last_run``).
2. **Fetch run summary** with execution KPIs ON; HR profile ON (V2 cares
   about zone framing); peer comparison OFF (we don't need it for review).
3. **Fetch splits** when ``cfg.fetch_splits`` is true and the run has
   any laps. Failures degrade silently — the prompt simply omits splits.
4. **Derive workout intent** from ``facts.execution_summary.planned``.

Anything we can't resolve raises :class:`RunReviewFallback` so the
orchestrator can re-enter the legacy path without an extra round trip.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.smartcoach_mobile_coach.run_review.classifier import ClassifierResult
from src.smartcoach_mobile_coach.run_review.config import RunReviewConfig
from src.smartcoach_mobile_coach.run_review.context import (
    RunReviewContext,
    WorkoutIntent,
)
from src.smartcoach_mobile_coach.run_review.errors import RunReviewFallback

logger = logging.getLogger("smartcoach_mobile_coach")


def _resolve_activity(
    *,
    session: Session,
    internal_user_id: str,
    anchor_local_date: str,
    classifier: ClassifierResult,
    activity_id_hint: Optional[int],
    thread_activity_id: Optional[int],
) -> Dict[str, Any]:
    """Pick one activity id and remember how we got it."""
    from src.smartcoach_mobile_coach.agent_tools import (
        tool_find_runs_by_date,
        tool_search_runs,
    )

    if isinstance(activity_id_hint, int) and activity_id_hint > 0:
        return {
            "activity_id": int(activity_id_hint),
            "local_date": (anchor_local_date or "")[:10],
            "resolved_via": "activity_id_hint",
        }

    if isinstance(thread_activity_id, int) and thread_activity_id > 0:
        return {
            "activity_id": int(thread_activity_id),
            "local_date": (anchor_local_date or "")[:10],
            "resolved_via": "thread_context",
        }

    day_hint = (classifier.day_hint or "").lower() if classifier else ""

    if day_hint == "last_run":
        sr = tool_search_runs(session, internal_user_id, limit=1)
        if sr.get("error") or not sr.get("matches"):
            raise RunReviewFallback("no_runs_for_user")
        m0 = sr["matches"][0]
        aid = m0.get("activity_id")
        local_date = str(m0.get("start_local_date") or "")[:10]
        if not isinstance(aid, int) or len(local_date) != 10:
            raise RunReviewFallback("most_recent_run_unresolved")
        return {
            "activity_id": int(aid),
            "local_date": local_date,
            "resolved_via": "most_recent_run",
        }

    ld = (anchor_local_date or "").strip()[:10]
    if len(ld) == 10:
        fr = tool_find_runs_by_date(session, internal_user_id, ld)
        if fr.get("error"):
            raise RunReviewFallback(f"find_runs_by_date_error:{fr.get('error')}")
        if fr.get("disambiguation_needed"):
            # We deliberately do NOT pick a run for the user — that ambiguity
            # is the kind of thing the regular orchestrator handles politely.
            raise RunReviewFallback("disambiguation_needed")
        if fr.get("no_runs"):
            raise RunReviewFallback("no_runs_on_anchor_date")
        aid = fr.get("activity_id")
        if not isinstance(aid, int):
            raise RunReviewFallback("anchor_date_unresolved")
        return {
            "activity_id": int(aid),
            "local_date": ld,
            "resolved_via": "find_runs_by_date",
        }

    sr = tool_search_runs(session, internal_user_id, limit=1)
    if sr.get("error") or not sr.get("matches"):
        raise RunReviewFallback("no_anchor_and_no_recent_run")
    m0 = sr["matches"][0]
    aid = m0.get("activity_id")
    local_date = str(m0.get("start_local_date") or "")[:10]
    if not isinstance(aid, int) or len(local_date) != 10:
        raise RunReviewFallback("most_recent_run_unresolved")
    return {
        "activity_id": int(aid),
        "local_date": local_date,
        "resolved_via": "most_recent_run_default",
    }


def _build_workout_intent(facts: Dict[str, Any]) -> WorkoutIntent:
    """Read planned_type / planned_miles / plan_status from execution_summary."""
    ex = facts.get("execution_summary") if isinstance(facts, dict) else None
    if not isinstance(ex, dict):
        return WorkoutIntent()
    planned = ex.get("planned") if isinstance(ex.get("planned"), dict) else {}
    planned_type = planned.get("type") if isinstance(planned, dict) else None
    raw_miles = planned.get("miles") if isinstance(planned, dict) else None
    planned_miles: Optional[float]
    try:
        planned_miles = float(raw_miles) if raw_miles is not None else None
    except (TypeError, ValueError):
        planned_miles = None
    plan_status = ex.get("plan_status")
    violated = ex.get("violated_rest_day")
    return WorkoutIntent(
        planned_type=(
            str(planned_type).strip().lower() if isinstance(planned_type, str) else None
        ),
        planned_miles=planned_miles,
        plan_status=str(plan_status).strip() if isinstance(plan_status, str) else None,
        violated_rest_day=(bool(violated) if isinstance(violated, bool) else None),
    )


def _fetch_splits(
    session: Session,
    internal_user_id: str,
    activity_id: int,
) -> Optional[Dict[str, Any]]:
    """Wrap tool_get_run_splits with a defensive degrade-to-None policy."""
    from src.smartcoach_mobile_coach.agent_tools import tool_get_run_splits

    try:
        payload = tool_get_run_splits(session, internal_user_id, int(activity_id))
    except Exception:  # pragma: no cover - belt-and-suspenders
        logger.warning(
            "[run_review.context_builder] tool_get_run_splits raised; degrading",
            exc_info=True,
        )
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("error"):
        return None
    rows = payload.get("splits")
    if not isinstance(rows, list) or not rows:
        return None
    return payload


def build_context(
    *,
    session: Session,
    internal_user_id: str,
    anchor_local_date: str,
    classifier: ClassifierResult,
    cfg: RunReviewConfig,
    activity_id_hint: Optional[int] = None,
    thread_activity_id: Optional[int] = None,
) -> RunReviewContext:
    """Build a :class:`RunReviewContext`, raising :class:`RunReviewFallback`
    on any failure that should bounce us back into the legacy path.
    """
    from src.smartcoach_mobile_coach.agent_tools import tool_get_run_summary

    resolved = _resolve_activity(
        session=session,
        internal_user_id=internal_user_id,
        anchor_local_date=anchor_local_date,
        classifier=classifier,
        activity_id_hint=activity_id_hint,
        thread_activity_id=thread_activity_id,
    )
    activity_id = int(resolved["activity_id"])
    local_date = str(resolved["local_date"])
    resolved_via = str(resolved["resolved_via"])

    summary = tool_get_run_summary(
        session,
        internal_user_id,
        activity_id,
        anchor_local_date=local_date,
        include_peer_comparison=False,
        include_execution_kpis=True,
        include_hr_profile=True,
    )
    if not isinstance(summary, dict) or summary.get("error"):
        raise RunReviewFallback(
            f"run_summary_error:{(summary or {}).get('error', 'unknown')}"
        )

    facts = summary.get("facts") if isinstance(summary.get("facts"), dict) else {}
    if not facts:
        raise RunReviewFallback("run_summary_missing_facts")

    splits_payload: Optional[Dict[str, Any]] = None
    if cfg.fetch_splits and classifier.scope in ("single_run", "splits_only"):
        splits_payload = _fetch_splits(session, internal_user_id, activity_id)

    intent = _build_workout_intent(facts)

    ctx = RunReviewContext(
        activity_id=activity_id,
        anchor_local_date=local_date,
        facts=facts,
        training_kpis=(
            summary.get("training_kpis")
            if isinstance(summary.get("training_kpis"), dict)
            else None
        ),
        zone_bounds=(
            summary.get("zone_bounds")
            if isinstance(summary.get("zone_bounds"), dict)
            else None
        ),
        hr_drift_band_zones=summary.get("hr_drift_band_zones"),
        is_easy_run=(
            bool(summary.get("is_easy_run"))
            if summary.get("is_easy_run") is not None
            else None
        ),
        workout_intent=intent,
        splits=splits_payload,
        splits_truncated=bool((splits_payload or {}).get("splits_truncated", False)),
        splits_count=int((splits_payload or {}).get("splits_count") or 0),
        hr_profile=(
            summary.get("user_hr_profile")
            if isinstance(summary.get("user_hr_profile"), dict)
            else None
        ),
        resolved_via=resolved_via,
        scope=classifier.scope or "single_run",
    )
    return ctx


def stub_context_for_test(  # pragma: no cover - helper for unit tests
    *,
    activity_id: int,
    anchor_local_date: str,
    facts: Dict[str, Any],
    training_kpis: Optional[Dict[str, Any]] = None,
    zone_bounds: Optional[Dict[str, Any]] = None,
    splits_payload: Optional[Dict[str, Any]] = None,
    scope: str = "single_run",
    is_easy_run: Optional[bool] = None,
    hr_profile: Optional[Dict[str, Any]] = None,
) -> RunReviewContext:
    """Build a context object without DB access. For unit tests only."""
    intent = _build_workout_intent(facts)
    rows: List[Dict[str, Any]] = (
        (splits_payload or {}).get("splits") if splits_payload else []
    ) or []
    return RunReviewContext(
        activity_id=activity_id,
        anchor_local_date=anchor_local_date,
        facts=facts,
        training_kpis=training_kpis,
        zone_bounds=zone_bounds,
        is_easy_run=is_easy_run,
        workout_intent=intent,
        splits=splits_payload,
        splits_truncated=bool((splits_payload or {}).get("splits_truncated", False)),
        splits_count=len(rows),
        hr_profile=hr_profile,
        resolved_via="test_stub",
        scope=scope,
    )
