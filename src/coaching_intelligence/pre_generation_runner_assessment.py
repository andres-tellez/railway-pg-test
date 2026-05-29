"""
Pre-generation runner assessment — thin orchestration only.

Builds a single snapshot **before** ``run_v2_plan_generation`` by calling existing
implementations only (activity summary, ambition gap, intake alignment). No planner,
validation, or new coaching rules.

Question flow traceability (where alignment UI comes from)
--------------------------------------------------------
1. **Evaluator:** ``evaluate_intake_alignment_state`` in ``intake_alignment.py`` sets
   ``pause_required``, ``unresolved_flags``, and ``allowed_question_categories``
   (frequency first; optional timeline when HIGH_TENSION and frequency fixed).
2. **Tool brief:** ``generate_training_plan`` attaches ``alignment_brief`` including
   ``suggested_next_question`` from ``agent_tools._next_alignment_question``.
3. **Orchestrator UI:** ``_alignment_ui_prompt_from_plan_intake_state`` maps the first
   allowed category to inline chips; schedule confirmation may run first when
   ``ux.schedule_confirm_before_posture`` (see ``orchestrator.py``).
4. **Coach prose:** ``alignment_pause_coaching_facts_system_section`` in
   ``plan_intake_flow.py`` steers narrative when pause is active.

Consumer code should treat ``activity_summary``, ``ambition_gap``, and
``intake_alignment_state`` as verbatim outputs from their source functions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.coaching_intelligence.ambition_gap import evaluate_ambition_gap
from src.coaching_intelligence.intake_alignment import evaluate_intake_alignment_state
from src.smartcoach_mobile_coach.plan_intake_activity_context import (
    build_runner_evidence,
    strip_runner_evidence_to_activity_summary,
)


SCHEMA_VERSION = "pre_generation_runner_assessment.v1"

_PROVENANCE = [
    "build_runner_evidence / strip_runner_evidence_to_activity_summary "
    "(src.smartcoach_mobile_coach.plan_intake_activity_context)",
    "src.coaching_intelligence.ambition_gap.evaluate_ambition_gap",
    "src.coaching_intelligence.intake_alignment.evaluate_intake_alignment_state",
    "src.smartcoach_mobile_coach.memory.plan_memory_store (optional coach_memory stats only)",
]


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def extract_alignment_answer_bookkeeping(
    plan_intake_state: Dict[str, Any],
) -> Tuple[Dict[str, Any], int, List[str]]:
    """
    Same normalization as ``tool_generate_training_plan`` for prior alignment answers.
    """
    prior_alignment = dict((plan_intake_state or {}).get("alignment") or {})
    prior_answers = dict(prior_alignment.get("answers") or {})
    question_count = _safe_int(prior_alignment.get("question_count")) or 0
    asked_categories = [
        str(x)
        for x in list(prior_alignment.get("asked_categories") or [])
        if isinstance(x, str)
    ]
    if question_count == 0 and asked_categories:
        question_count = len(asked_categories)
    return prior_answers, question_count, asked_categories


def _json_safe_plan_field(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _plan_request_digest(plan_request: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "primary_goal": plan_request.get("primary_goal"),
        "race_distance": plan_request.get("race_distance"),
        "race_date": _json_safe_plan_field(plan_request.get("race_date")),
        "target_time": plan_request.get("target_time"),
        "training_days": plan_request.get("training_days"),
    }


def _coach_memory_stats(session: Session, user_id: str) -> Optional[Dict[str, Any]]:
    try:
        uid_u = uuid.UUID(str(user_id))
        from src.smartcoach_mobile_coach.memory.plan_memory_store import (
            coach_memory_entries_for_plan_generation,
            coach_memory_hints_for_plan_generation,
        )

        hints = coach_memory_hints_for_plan_generation(session, uid_u)
        memories = coach_memory_entries_for_plan_generation(session, uid_u)
        return {
            "hints_loaded": bool(hints),
            "memory_entries_count": len(memories or []),
        }
    except Exception:
        return None


@dataclass(frozen=True)
class PreGenerationRunnerAssessmentV1:
    schema_version: str
    computed_at: str
    user_id: str
    evidence_snapshot_id: str
    activity_summary: Dict[str, Any]
    plan_request_digest: Dict[str, Any]
    runner_evidence: Dict[str, Any]
    ambition_gap: Optional[Dict[str, Any]]
    intake_alignment_state: Optional[Dict[str, Any]]
    coach_memory: Optional[Dict[str, Any]]

    def as_api_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "schema_version": self.schema_version,
            "computed_at": self.computed_at,
            "user_id": self.user_id,
            "evidence_snapshot_id": self.evidence_snapshot_id,
            "activity_summary": self.activity_summary,
            "runner_evidence": self.runner_evidence,
            "plan_request_digest": self.plan_request_digest,
            "provenance": list(_PROVENANCE),
        }
        if self.ambition_gap is not None:
            out["ambition_gap"] = self.ambition_gap
        if self.intake_alignment_state is not None:
            out["intake_alignment_state"] = self.intake_alignment_state
        if self.coach_memory is not None:
            out["coach_memory"] = self.coach_memory
        return out


def build_pre_generation_runner_assessment(
    session: Session,
    user_id: str,
    *,
    plan_request: Dict[str, Any],
    plan_intake_state: Dict[str, Any],
    anchor_local_date: Optional[date] = None,
) -> PreGenerationRunnerAssessmentV1:
    """
    Single place for activity summary + ambition/alignment evaluation.

    ``anchor_local_date`` is forwarded to ``build_runner_evidence`` when set so calendar-week
    windows match an athlete-local "today" (device anchor); omit to use server date.
    """
    evidence_snapshot_id = str(uuid.uuid4())
    ev = build_runner_evidence(
        session, str(user_id), anchor_local_date=anchor_local_date
    )
    ev_api = ev.to_api_dict()
    summary = strip_runner_evidence_to_activity_summary(ev_api)
    digest = _plan_request_digest(plan_request)
    coach_memory = _coach_memory_stats(session, user_id)

    ambition: Optional[Dict[str, Any]] = None
    alignment_state: Optional[Dict[str, Any]] = None

    ambition = evaluate_ambition_gap(
        weekly_mileage=float(summary.get("avg_miles_per_week_approx") or 0.0),
        primary_goal=str(plan_request.get("primary_goal") or ""),
        target_time=str(plan_request.get("target_time") or ""),
        longest_run_miles=float(summary.get("longest_run_miles") or 0.0),
    )
    prior_answers, question_count, _asked = extract_alignment_answer_bookkeeping(
        plan_intake_state
    )
    alignment_state = evaluate_intake_alignment_state(
        ambition_stance=str(ambition.get("stance") or ""),
        primary_goal=str(plan_request.get("primary_goal") or ""),
        ambition_attributions=list(ambition.get("attributions") or []),
        frequency_flexible=prior_answers.get("frequency_flexible"),
        posture_priority=prior_answers.get("posture_priority"),
        timeline_flexible=prior_answers.get("timeline_flexible"),
        question_count=question_count,
    )

    return PreGenerationRunnerAssessmentV1(
        schema_version=SCHEMA_VERSION,
        computed_at=datetime.now(timezone.utc).isoformat(),
        user_id=str(user_id),
        evidence_snapshot_id=evidence_snapshot_id,
        activity_summary=dict(summary),
        runner_evidence=dict(ev_api),
        plan_request_digest=digest,
        ambition_gap=ambition,
        intake_alignment_state=alignment_state,
        coach_memory=coach_memory,
    )
