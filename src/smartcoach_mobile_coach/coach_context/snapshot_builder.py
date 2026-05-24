"""
Purpose:
- Single owner for assembling the compact always-on CoachSnapshot.

Responsibilities:
- Call slice builders behind clean facades.
- Apply budget/drop policy and return trace metadata.
- Degrade gracefully when a slice fails (omit, never crash caller).

Non-goals:
- No LLM calls.
- No deterministic coaching verdict logic.

Guardrails:
- Allowed imports/calls: coach_context slice modules + canonical services.
- Must not import from smartcoach orchestrator.
- Must keep all prompt formatting out of this file.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.services.user.user_context import build_user_context_payload
from src.utils.timezone_helpers import get_today_date_in_timezone
from src.smartcoach_mobile_coach.coach_context.athlete_profile import (
    build_athlete_slice,
)
from src.smartcoach_mobile_coach.coach_context.budget import apply_budget
from src.smartcoach_mobile_coach.memory.coach_snapshot_memory_slice import (
    build_memory_slice,
)
from src.smartcoach_mobile_coach.coach_context.plan_context import build_plan_slice
from src.smartcoach_mobile_coach.coach_context.schemas import (
    CoachSnapshot,
    SnapshotBuildResult,
)
from src.smartcoach_mobile_coach.coach_context.telemetry import build_trace, log_built
from src.smartcoach_mobile_coach.coach_context.training_trends import build_trends_slice
from src.smartcoach_mobile_coach.coach_context.working_context import (
    build_working_slice,
)

COACH_SNAPSHOT_SCHEMA_VERSION = 1

FIELD_SOURCES: Dict[str, str] = {
    "plan.has_active_plan": "services.plan.active_plan",
    "plan.race": "services.user.user_context.race_goal",
    "plan.phase": "services.user.user_context.plan",
    "athlete.display_name": "services.user.user_context.display_name",
    "athlete.baseline_status": "services.user.user_context.baseline_status",
    "athlete.unit_system": "services.user.user_context.preferences.unit_system",
    "athlete.hr_calibration_status": "services.heart_rate.hrmax_resolution_service",
    "athlete.zones_compact": "db.runner_zone_profiles",
    "trends.mileage_4w": "smartcoach_mobile_coach.training_kpi_service.get_training_progress",
    "memory.plan_memories": "services.user.user_context.plan_memories",
    "memory.session_summary_excerpt": "services.user.user_context.session_summary",
    "working.last_structured_run_activity_id": "thread_derived_context",
}


def _opening_turn(conversation_history: List[Dict[str, str]]) -> bool:
    return len(conversation_history or []) == 0


def _safe_uuid(raw_user_id: str) -> Optional[UUID]:
    try:
        return UUID(str(raw_user_id))
    except (TypeError, ValueError):
        return None


def build_snapshot(
    *,
    session: Session,
    internal_user_id: str,
    tz: Optional[str],
    anchor_local_date: Optional[str],
    conversation_history: List[Dict[str, str]],
) -> SnapshotBuildResult:
    """Build CoachSnapshot + trace with graceful degradation."""
    tz_norm = (tz or "UTC").strip() or "UTC"
    if anchor_local_date:
        today_iso = str(anchor_local_date)
    else:
        today_iso = get_today_date_in_timezone(tz_norm).isoformat()
    opening_turn = _opening_turn(conversation_history)

    user_context_payload: Dict[str, Any] = {}
    uid = _safe_uuid(internal_user_id)
    if uid is not None:
        user_context_payload = build_user_context_payload(
            session=session,
            user_id=uid,
            tz=tz_norm,
            today=date.fromisoformat(today_iso),
        )
    if not isinstance(user_context_payload, dict):
        user_context_payload = {}

    athlete = None
    plan = None
    trends = None
    memory = None
    working = None

    try:
        athlete = build_athlete_slice(
            session=session,
            internal_user_id=str(internal_user_id),
            user_context_payload=user_context_payload,
        )
    except Exception:
        athlete = None

    try:
        plan = build_plan_slice(
            session=session,
            internal_user_id=str(internal_user_id),
            user_context_payload=user_context_payload,
        )
    except Exception:
        plan = None

    try:
        trends = build_trends_slice(
            session=session,
            internal_user_id=str(internal_user_id),
            baseline_status=(athlete.baseline_status if athlete else None),
        )
    except Exception:
        trends = None

    try:
        memory = build_memory_slice(
            user_context_payload=user_context_payload,
            opening_turn=opening_turn,
        )
    except Exception:
        memory = None

    try:
        working = build_working_slice(conversation_history=conversation_history)
    except Exception:
        working = None

    snapshot = CoachSnapshot(
        schema_version=COACH_SNAPSHOT_SCHEMA_VERSION,
        today=today_iso,
        tz=tz_norm,
        athlete=athlete,
        plan=plan,
        trends=trends,
        memory=memory,
        working=working,
        omitted_fields=[],
    )
    snapshot, omitted_fields, size_chars = apply_budget(snapshot)
    included = [
        name
        for name, val in (
            ("athlete", snapshot.athlete),
            ("plan", snapshot.plan),
            ("trends", snapshot.trends),
            ("memory", snapshot.memory),
            ("working", snapshot.working),
        )
        if val is not None
    ]
    omitted_slices = [
        n
        for n in ("athlete", "plan", "trends", "memory", "working")
        if n not in included
    ]
    trace = build_trace(
        built=True,
        enabled=True,
        size_chars=size_chars,
        slices_included=included,
        slices_omitted=omitted_slices,
        fields_omitted_due_to_budget=omitted_fields,
        field_sources=FIELD_SOURCES,
        opening_turn=opening_turn,
    )
    log_built(trace)
    return SnapshotBuildResult(snapshot=snapshot, trace=trace)
