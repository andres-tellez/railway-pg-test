"""Resolve run data and gather everything the LLM needs."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from src.smartcoach_mobile_coach.coach_response.classifier import ClassifierResult
from src.smartcoach_mobile_coach.coach_response.config import CoachResponseConfig
from src.smartcoach_mobile_coach.coach_response.context import (
    CoachRunContext,
    WorkoutIntent,
)
from src.smartcoach_mobile_coach.coach_response.errors import CoachResponseFallback
from src.smartcoach_mobile_coach.coach_response.evidence_pack import build_evidence_pack

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
            raise CoachResponseFallback("no_runs_for_user")
        first_match = sr["matches"][0]
        activity_id = first_match.get("activity_id")
        local_date = str(first_match.get("start_local_date") or "")[:10]
        if not isinstance(activity_id, int) or len(local_date) != 10:
            raise CoachResponseFallback("most_recent_run_unresolved")
        return {
            "activity_id": int(activity_id),
            "local_date": local_date,
            "resolved_via": "most_recent_run",
        }
    local_day = (anchor_local_date or "").strip()[:10]
    if len(local_day) == 10:
        fr = tool_find_runs_by_date(session, internal_user_id, local_day)
        if fr.get("error"):
            raise CoachResponseFallback(f"find_runs_by_date_error:{fr.get('error')}")
        if fr.get("disambiguation_needed"):
            raise CoachResponseFallback("disambiguation_needed")
        if fr.get("no_runs"):
            raise CoachResponseFallback("no_runs_on_anchor_date")
        activity_id = fr.get("activity_id")
        if not isinstance(activity_id, int):
            raise CoachResponseFallback("anchor_date_unresolved")
        return {
            "activity_id": int(activity_id),
            "local_date": local_day,
            "resolved_via": "find_runs_by_date",
        }
    sr = tool_search_runs(session, internal_user_id, limit=1)
    if sr.get("error") or not sr.get("matches"):
        raise CoachResponseFallback("no_anchor_and_no_recent_run")
    first_match = sr["matches"][0]
    activity_id = first_match.get("activity_id")
    local_date = str(first_match.get("start_local_date") or "")[:10]
    if not isinstance(activity_id, int) or len(local_date) != 10:
        raise CoachResponseFallback("most_recent_run_unresolved")
    return {
        "activity_id": int(activity_id),
        "local_date": local_date,
        "resolved_via": "most_recent_run_default",
    }


def _build_workout_intent(facts: Dict[str, Any]) -> WorkoutIntent:
    execution_summary = (
        facts.get("execution_summary") if isinstance(facts, dict) else None
    )
    if not isinstance(execution_summary, dict):
        return WorkoutIntent()
    planned = (
        execution_summary.get("planned")
        if isinstance(execution_summary.get("planned"), dict)
        else {}
    )
    planned_type = planned.get("type") if isinstance(planned, dict) else None
    raw_miles = planned.get("miles") if isinstance(planned, dict) else None
    try:
        planned_miles = float(raw_miles) if raw_miles is not None else None
    except (TypeError, ValueError):
        planned_miles = None
    plan_status = execution_summary.get("plan_status")
    violated_rest_day = execution_summary.get("violated_rest_day")
    return WorkoutIntent(
        planned_type=(
            str(planned_type).strip().lower() if isinstance(planned_type, str) else None
        ),
        planned_miles=planned_miles,
        plan_status=str(plan_status).strip() if isinstance(plan_status, str) else None,
        violated_rest_day=(
            bool(violated_rest_day) if isinstance(violated_rest_day, bool) else None
        ),
    )


def _fetch_splits(
    session: Session,
    internal_user_id: str,
    activity_id: int,
) -> Optional[Dict[str, Any]]:
    from src.smartcoach_mobile_coach.agent_tools import tool_get_run_splits

    try:
        payload = tool_get_run_splits(session, internal_user_id, int(activity_id))
    except Exception:
        logger.warning(
            "[coach_response.context_builder] tool_get_run_splits raised; degrading",
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
    cfg: CoachResponseConfig,
    activity_id_hint: Optional[int] = None,
    thread_activity_id: Optional[int] = None,
) -> CoachRunContext:
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
        raise CoachResponseFallback(
            f"run_summary_error:{(summary or {}).get('error', 'unknown')}"
        )
    facts = summary.get("facts") if isinstance(summary.get("facts"), dict) else {}
    if not facts:
        raise CoachResponseFallback("run_summary_missing_facts")
    splits_payload: Optional[Dict[str, Any]] = None
    if cfg.fetch_splits and classifier.scope in ("single_run", "splits_only"):
        splits_payload = _fetch_splits(session, internal_user_id, activity_id)
    intent = _build_workout_intent(facts)
    evidence_pack: Optional[Dict[str, Any]] = None
    evidence_pack_trace: Optional[Dict[str, Any]] = None
    if cfg.evidence_pack_enabled:
        try:
            evidence_pack, evidence_pack_trace = build_evidence_pack(
                session=session,
                internal_user_id=internal_user_id,
                activity_id=activity_id,
                anchor_local_date=local_date,
                facts=facts,
                workout_intent=intent,
                is_easy_run=(
                    bool(summary.get("is_easy_run"))
                    if summary.get("is_easy_run") is not None
                    else None
                ),
            )
        except Exception:
            logger.warning(
                "[coach_response.context_builder] evidence_pack build failed; degrading",
                exc_info=True,
            )
            evidence_pack = None
            evidence_pack_trace = {
                "enabled": True,
                "present": False,
                "reason": "build_failed",
            }
    return CoachRunContext(
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
        evidence_pack=evidence_pack,
        evidence_pack_trace=evidence_pack_trace,
        resolved_via=resolved_via,
        scope=classifier.scope or "single_run",
    )
