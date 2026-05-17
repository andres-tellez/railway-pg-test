"""Run Review Lab entrypoint: minimal prompt, same data pipeline."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.smartcoach_mobile_coach.coach_context import (
    build_snapshot,
    coach_context_v1_enabled,
)
from src.smartcoach_mobile_coach.run_review.classifier import (
    ClassifierResult,
    classify_user_message,
)
from src.smartcoach_mobile_coach.run_review.config import (
    load_config as load_run_review_config,
)
from src.smartcoach_mobile_coach.run_review.context_builder import build_context
from src.smartcoach_mobile_coach.run_review.errors import (
    RunReviewFallback,
    RunReviewSkip,
)
from src.smartcoach_mobile_coach.run_review.payload import build_run_review_envelope
from src.smartcoach_mobile_coach.run_review.telemetry import record_run_review_event
from src.smartcoach_mobile_coach.run_review_lab.config import (
    RunReviewLabConfig,
    load_config,
)
from src.smartcoach_mobile_coach.run_review_lab.responder import generate_review
from src.smartcoach_mobile_coach.experiments.run_review_lab_isolated_system import (
    build_isolated_lab_system_prefix,
)
from src.smartcoach_mobile_coach.thread_derived_context import DerivedThreadCoachContext

logger = logging.getLogger("smartcoach_mobile_coach")

RUN_REVIEW_LAB_VERSION = "run_review_lab_minimal_v1"


def should_use_run_review_lab(
    *,
    user_message: str,
    conversation_history: List[Dict[str, str]],
    internal_user_id: str,
    cfg: Optional[RunReviewLabConfig] = None,
) -> Tuple[bool, Optional[ClassifierResult], RunReviewLabConfig]:
    snapshot = cfg or load_config()
    if not snapshot.enabled:
        return False, None, snapshot
    rr_cfg = load_run_review_config()
    try:
        result = classify_user_message(
            user_message=user_message,
            conversation_history=conversation_history,
            internal_user_id=internal_user_id,
            cfg=rr_cfg,
        )
    except Exception:  # pragma: no cover - defensive
        logger.warning(
            "[run_review_lab.entry] classifier_threw_unexpectedly; gate=False",
            exc_info=True,
        )
        return False, None, snapshot
    return result.is_run_review, result, snapshot


def handle_run_review_lab_turn(  # pylint: disable=too-many-arguments,too-many-locals
    *,
    session: Session,
    internal_user_id: str,
    user_message: str,
    conversation_history: List[Dict[str, str]],
    anchor_local_date: str,
    base_system_content: str,
    history_window: int,
    model: str,
    temperature: float,
    max_tokens: Optional[int],
    response_directive_dialogue: Dict[str, Any],
    activity_id_hint: Optional[int] = None,
    thread_activity_id: Optional[int] = None,
    cfg: Optional[RunReviewLabConfig] = None,
    classifier_result: Optional[ClassifierResult] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    lab_cfg = cfg or load_config()
    if not lab_cfg.enabled:
        raise RunReviewFallback("run_review_lab_flag_disabled")

    rr_cfg = load_run_review_config()
    classification = classifier_result
    if classification is None:
        classification = classify_user_message(
            user_message=user_message,
            conversation_history=conversation_history,
            internal_user_id=internal_user_id,
            cfg=rr_cfg,
        )
    if not classification.is_run_review:
        raise RunReviewSkip("classifier_says_not_run_review")

    timings: Dict[str, Any] = {}
    coach_context_trace: Optional[Dict[str, Any]] = None
    coach_snapshot: Optional[Dict[str, Any]] = None
    t_cc0 = time.perf_counter()
    if coach_context_v1_enabled():
        try:
            cc_result = build_snapshot(
                session=session,
                internal_user_id=str(internal_user_id),
                tz="UTC",
                anchor_local_date=anchor_local_date,
                conversation_history=conversation_history,
            )
            coach_context_trace = cc_result.trace
            coach_snapshot = cc_result.snapshot.to_dict()
        except Exception:
            coach_context_trace = {
                "built": False,
                "enabled": True,
                "reason": "build_failed",
            }
            logger.warning(
                "[coach_context] build failed inside run_review_lab; continuing without snapshot",
                exc_info=True,
            )
    else:
        coach_context_trace = {"built": False, "enabled": False, "reason": "flag_off"}
    timings["coach_context_build_ms"] = round((time.perf_counter() - t_cc0) * 1000, 2)

    t_ctx0 = time.perf_counter()
    try:
        ctx = build_context(
            session=session,
            internal_user_id=internal_user_id,
            anchor_local_date=anchor_local_date,
            classifier=classification,
            cfg=rr_cfg,
            activity_id_hint=activity_id_hint,
            thread_activity_id=thread_activity_id,
        )
    except RunReviewFallback as exc:
        timings["run_review_lab_context_ms"] = round(
            (time.perf_counter() - t_ctx0) * 1000, 2
        )
        record_run_review_event(
            user_id=str(internal_user_id),
            outcome="fallback",
            user_message=user_message,
            properties={
                "mode": "lab",
                "stage": "context_build",
                "reason": str(exc) or exc.__class__.__name__,
                "classifier": classification.as_log_dict(),
                "timings_ms": timings,
            },
        )
        raise
    timings["run_review_lab_context_ms"] = round(
        (time.perf_counter() - t_ctx0) * 1000, 2
    )

    if lab_cfg.isolated_system_enabled:
        effective_base = build_isolated_lab_system_prefix(
            anchor_local_date=anchor_local_date,
            client_timezone=client_timezone,
            session=session,
            internal_user_id=str(internal_user_id),
            thread_ctx=thread_derived_context,
        )
    else:
        effective_base = base_system_content or ""

    responder_out = generate_review(
        ctx=ctx,
        coach_snapshot=coach_snapshot,
        base_system_content=effective_base,
        conversation_history=conversation_history,
        user_message=user_message,
        history_window=history_window,
        internal_user_id=internal_user_id,
        cfg=lab_cfg,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    timings.update(responder_out.timings_ms)

    structured, sections_attached = build_run_review_envelope(
        ctx=ctx,
        content=responder_out.content,
    )

    meta: Dict[str, Any] = {
        "usage": responder_out.usage,
        "cost": responder_out.cost,
        "loops": 1,
        "max_loops": 1,
        "model": responder_out.model,
        "run_review_v2": False,
        "run_review_lab": True,
        "run_review_lab_path": ctx.resolved_via,
        "run_review_lab_scope": ctx.scope,
        "run_review_lab_activity_id": ctx.activity_id,
        "run_review_lab_isolated_system": lab_cfg.isolated_system_enabled,
        "run_review_v2_classifier": classification.as_log_dict(),
        "timings_ms": timings,
        "dialogue": response_directive_dialogue,
        "rubric_version": RUN_REVIEW_LAB_VERSION,
        "evidence_pack_trace": ctx.evidence_pack_trace,
    }
    if sections_attached:
        meta["run_summary_sections"] = True
    if isinstance(coach_context_trace, dict):
        meta["coach_context_trace"] = coach_context_trace

    record_run_review_event(
        user_id=str(internal_user_id),
        outcome="served",
        user_message=user_message,
        properties={
            "mode": "lab",
            "isolated_system": lab_cfg.isolated_system_enabled,
            "activity_id": ctx.activity_id,
            "resolved_via": ctx.resolved_via,
            "scope": ctx.scope,
            "classifier": classification.as_log_dict(),
            "splits_attached": ctx.splits is not None,
            "splits_count": ctx.splits_count,
            "sections_attached": sections_attached,
            "timings_ms": timings,
            "usage": responder_out.usage,
        },
    )
    return structured, meta
