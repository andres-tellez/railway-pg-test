"""Readiness and intake-alignment gate for plan generation."""

# pylint: disable=too-many-arguments,too-many-locals,broad-exception-caught,line-too-long

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any, Callable, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from src.coaching_intelligence.pre_generation_runner_assessment import (
    extract_alignment_answer_bookkeeping,
)
from src.smartcoach_mobile_coach.readiness_gate import get_or_compute_readiness_gate

logger = logging.getLogger("smartcoach_mobile_coach")
_ASSESSMENT_FAILURE_DETAIL_MAX_LEN = 500


def _next_alignment_question(allowed_categories: list[str]) -> str:
    first = allowed_categories[0] if allowed_categories else ""
    if first == "frequency_flexibility":
        return "Would you be open to adding one run day to support this goal?"
    if first == "timeline_flexibility":
        return "If needed, are you open to adjusting timeline expectations slightly?"
    return "What feels most adjustable for you right now?"


def _parse_optional_anchor_date_str(raw: Optional[str]) -> Optional[date]:
    if not raw or not str(raw).strip():
        return None
    try:
        return date.fromisoformat(str(raw).strip()[:10])
    except ValueError:
        return None


def _sanitize_assessment_failure_detail(exc: BaseException) -> str:
    raw = str(exc).strip().replace("\n", " ").replace("\r", " ")
    if len(raw) > _ASSESSMENT_FAILURE_DETAIL_MAX_LEN:
        return raw[: _ASSESSMENT_FAILURE_DETAIL_MAX_LEN - 1] + "..."
    return raw


def evaluate_generation_readiness(
    *,
    session: Session,
    internal_user_id: str,
    plan_request: Dict[str, Any],
    current_state: Dict[str, Any],
    anchor_local_date: Optional[str],
    record_event: Callable[[str, str, Optional[Dict[str, Any]]], None],
    gate_fn: Optional[Callable[..., Any]] = None,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Return (blocked_response, next_state, assessment_payload, readiness_payload)."""
    try:
        resolver = gate_fn or get_or_compute_readiness_gate
        gate_result = resolver(
            session=session,
            internal_user_id=str(internal_user_id),
            plan_request=plan_request,
            plan_intake_state=current_state,
            anchor_local_date=_parse_optional_anchor_date_str(anchor_local_date),
        )
    except Exception as exc:
        logger.exception(
            "[generate_training_plan] pre_generation_runner_assessment failed user=%s",
            internal_user_id,
        )
        record_event(
            str(internal_user_id),
            "failure",
            {
                "stage": "pre_generation_runner_assessment",
                "exception_type": type(exc).__name__,
            },
        )
        return (
            {
                "error": "pre_generation_runner_assessment_failed",
                "tool": "generate_training_plan",
                "message": (
                    "We couldn't load your activity summary needed before creating your plan. "
                    "Please try again in a moment."
                ),
                "failure": {
                    "stage": "pre_generation_runner_assessment",
                    "exception_type": type(exc).__name__,
                    "detail": _sanitize_assessment_failure_detail(exc),
                },
                "plan_intake_state": current_state,
            },
            current_state,
            {},
            {},
        )

    assessment_payload = gate_result.assessment_api
    readiness_payload = gate_result.readiness_api
    logger.info(
        "[readiness_gate] %s",
        json.dumps(
            {
                "trace_id": readiness_payload.get("trace_id"),
                "policy_version": readiness_payload.get("policy_version"),
                "decision": readiness_payload.get("decision"),
                "readiness_level": readiness_payload.get("readiness_level"),
                "reason_codes": readiness_payload.get("reason_codes"),
                "user_id": str(internal_user_id),
                "plan_request_digest_sha256": gate_result.plan_request_digest_sha256,
                "evidence_snapshot_id": readiness_payload.get("evidence_snapshot_id"),
                "cache_status": gate_result.cache_status,
            },
            default=str,
        ),
    )
    if readiness_payload.get("decision") != "allow":
        logger.warning(
            "[plan_generation_readiness_deferred] %s",
            json.dumps(
                {
                    "error": (
                        "plan_generation_readiness_deferred"
                        if readiness_payload.get("decision") == "defer"
                        else "plan_generation_readiness_blocked"
                    ),
                    "trace_id": readiness_payload.get("trace_id"),
                    "decision": readiness_payload.get("decision"),
                    "readiness_level": readiness_payload.get("readiness_level"),
                    "confidence": readiness_payload.get("confidence"),
                    "goal_profile": readiness_payload.get("goal_profile"),
                    "reason_codes": readiness_payload.get("reason_codes"),
                    "user_id": str(internal_user_id),
                    "plan_request_digest_sha256": gate_result.plan_request_digest_sha256,
                    "evidence_snapshot_id": readiness_payload.get(
                        "evidence_snapshot_id"
                    ),
                    "cache_status": gate_result.cache_status,
                },
                default=str,
            ),
        )
        record_event(
            str(internal_user_id),
            "blocked",
            {
                "stage": "plan_generation_readiness",
                "decision": readiness_payload.get("decision"),
                "readiness_level": readiness_payload.get("readiness_level"),
                "trace_id": readiness_payload.get("trace_id"),
            },
        )
        return (
            {
                "error": (
                    "plan_generation_readiness_deferred"
                    if readiness_payload.get("decision") == "defer"
                    else "plan_generation_readiness_blocked"
                ),
                "tool": "generate_training_plan",
                "message": (
                    "The deterministic readiness check does not allow plan generation yet. "
                    "Explain the recommendation and use the allowed actions to continue."
                ),
                "plan_intake_state": current_state,
                "pre_generation_runner_assessment": assessment_payload,
                "plan_generation_readiness": readiness_payload,
            },
            current_state,
            assessment_payload,
            readiness_payload,
        )

    ambition = (
        assessment_payload.get("ambition_gap")
        if isinstance(assessment_payload.get("ambition_gap"), dict)
        else None
    )
    alignment_state = (
        assessment_payload.get("intake_alignment_state")
        if isinstance(assessment_payload.get("intake_alignment_state"), dict)
        else None
    )
    assert ambition is not None and alignment_state is not None
    prior_answers, _question_count, asked_categories = (
        extract_alignment_answer_bookkeeping(current_state)
    )
    next_state = dict(current_state)
    next_state["alignment"] = {
        "enabled": True,
        "ambition_stance": ambition.get("stance"),
        "ambition_attributions": list(ambition.get("attributions") or []),
        "goal_demand": ambition.get("goal_demand"),
        "baseline_band": ambition.get("baseline_band"),
        "question_count": alignment_state.get("question_count"),
        "asked_categories": asked_categories,
        "answers": prior_answers,
        "state": alignment_state,
        "attributions": sorted(
            set(
                list(ambition.get("attributions") or [])
                + list(alignment_state.get("attributions") or [])
            )
        ),
        "observability": {
            "pause_fired": bool(alignment_state.get("pause_required")),
            "categories_asked": asked_categories,
            "posture_selected": alignment_state.get("posture_state"),
            "alignment_resolved": bool(alignment_state.get("generation_ready")),
            "question_count": alignment_state.get("question_count"),
            "generation_proceeded": bool(alignment_state.get("generation_ready")),
        },
    }

    if not alignment_state.get("generation_ready"):
        allowed_categories = list(
            alignment_state.get("allowed_question_categories") or []
        )
        alignment_brief = {
            "state": alignment_state,
            "allowed_question_categories": allowed_categories,
            "required_truths": [
                "The planner remains deterministic and unchanged once generation starts.",
                "Current training baseline and stated goal may not match - how aggressive we can be depends on both.",
            ],
            "banned_claims": [
                "Do not promise a specific finish time or guaranteed outcome.",
                "Do not claim plan generation logic has changed.",
            ],
            "posture_context": {
                "current": alignment_state.get("posture_state"),
                "stance": ambition.get("stance"),
                "ambition_attributions": list(ambition.get("attributions") or []),
                "goal_demand": ambition.get("goal_demand"),
            },
            "response_style": {
                "coaching_prose_before_controls": True,
                "ask_one_question_only": False,
                "avoid_numbered_lists": True,
                "tone": "lightweight_collaborative_coach",
            },
            "suggested_next_question": _next_alignment_question(allowed_categories),
        }
        record_event(
            str(internal_user_id),
            "blocked",
            {
                "stage": "alignment_required",
                "trace_id": readiness_payload.get("trace_id"),
            },
        )
        return (
            {
                "error": "alignment_required",
                "message": (
                    "Alignment checkpoint: generation is paused until the user answers one alignment topic. "
                    "Do **not** reply with only the short `suggested_next_question` line. Follow the system "
                    "prompt **## Intake alignment - coach-facing facts** (and activity snapshot): ground in their "
                    "data, say plainly what's mismatched or uncertain, explain why it matters, then end with one closing question "
                    "that matches the same topic as `suggested_next_question` / the inline UI chips."
                ),
                "plan_intake_state": next_state,
                "alignment_brief": alignment_brief,
                "pre_generation_runner_assessment": assessment_payload,
            },
            next_state,
            assessment_payload,
            readiness_payload,
        )
    current_state = next_state

    return None, current_state, assessment_payload, readiness_payload
