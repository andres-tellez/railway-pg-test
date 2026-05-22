"""Coach response entrypoint: single-call, fact-bundle driven."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.smartcoach_mobile_coach.coach_context import (
    build_snapshot,
    coach_context_v1_enabled,
)
from src.smartcoach_mobile_coach.coach_response.classifier import (
    ClassifierResult,
    classify_user_message,
)
from src.smartcoach_mobile_coach.coach_response.config import (
    CoachResponseConfig,
    load_coach_response_config,
)
from src.smartcoach_mobile_coach.coach_response.context_builder import build_context
from src.smartcoach_mobile_coach.coach_response.envelope import (
    RUN_SUMMARY_LAYOUT_INLINE,
    RUN_SUMMARY_LAYOUT_RECAP,
    build_coach_response_envelope,
    build_coach_response_meta,
)
from src.smartcoach_mobile_coach.coach_response.errors import (
    CoachResponseFallback,
    CoachResponseSkip,
)
from src.smartcoach_mobile_coach.coach_response.responder import generate_review
from src.smartcoach_mobile_coach.dialogue_manager import INTENT_SPLIT_DETAIL
from src.smartcoach_mobile_coach.coach_response.telemetry import (
    record_coach_response_event,
)
from src.smartcoach_mobile_coach.thread_derived_context import DerivedThreadCoachContext

logger = logging.getLogger("smartcoach_mobile_coach")


def _classification_for_split_detail_intent() -> ClassifierResult:
    return ClassifierResult(
        is_run_review=True,
        scope="splits_only",
        confidence="medium",
        day_hint="last_run",
        source="dialogue_intent",
        reason_code="split_detail_intent",
    )


def _apply_split_intent_scope(
    classification: ClassifierResult,
    dialogue_intent: str,
) -> ClassifierResult:
    if (dialogue_intent or "").strip() != INTENT_SPLIT_DETAIL:
        return classification
    if classification.scope == "splits_only":
        return classification
    return ClassifierResult(
        is_run_review=classification.is_run_review,
        scope="splits_only",
        confidence=classification.confidence,
        day_hint=classification.day_hint,
        source=classification.source,
        reason_code=(
            classification.reason_code + "+split_intent_scope"
            if classification.reason_code
            else "split_intent_scope"
        ),
    )


def should_use_coach_response(
    *,
    user_message: str,
    conversation_history: List[Dict[str, str]],
    internal_user_id: str,
    dialogue_intent: str = "",
    cfg: Optional[CoachResponseConfig] = None,
) -> Tuple[bool, Optional[ClassifierResult], CoachResponseConfig]:
    snapshot = cfg or load_coach_response_config()
    if not snapshot.enabled:
        return False, None, snapshot
    try:
        result = classify_user_message(
            user_message=user_message,
            conversation_history=conversation_history,
            internal_user_id=internal_user_id,
            cfg=snapshot,
        )
    except Exception:
        logger.warning(
            "[coach_response.entry] classifier_threw_unexpectedly; gate=False",
            exc_info=True,
        )
        return False, None, snapshot
    intent = (dialogue_intent or "").strip()
    if result.is_run_review:
        routed = _apply_split_intent_scope(result, intent)
        return True, routed, snapshot
    if intent == INTENT_SPLIT_DETAIL:
        return True, _classification_for_split_detail_intent(), snapshot
    return False, result, snapshot


def handle_coach_response_turn(  # pylint: disable=too-many-arguments,too-many-locals
    *,
    session: Session,
    internal_user_id: str,
    user_message: str,
    conversation_history: List[Dict[str, str]],
    anchor_local_date: str,
    client_timezone: Optional[str] = None,
    thread_derived_context: Optional[DerivedThreadCoachContext] = None,
    base_system_content: str,
    history_window: int,
    model: str,
    temperature: float,
    max_tokens: Optional[int],
    response_directive_dialogue: Dict[str, Any],
    activity_id_hint: Optional[int] = None,
    thread_activity_id: Optional[int] = None,
    cfg: Optional[CoachResponseConfig] = None,
    classifier_result: Optional[ClassifierResult] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    del client_timezone, thread_derived_context
    response_cfg = cfg or load_coach_response_config()
    if not response_cfg.enabled:
        raise CoachResponseFallback("coach_response_flag_disabled")
    classification = classifier_result
    if classification is None:
        classification = classify_user_message(
            user_message=user_message,
            conversation_history=conversation_history,
            internal_user_id=internal_user_id,
            cfg=response_cfg,
        )
    if not classification.is_run_review:
        raise CoachResponseSkip("classifier_says_not_run_review")
    response_scope = (classification.scope or "single_run").strip()
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
                "[coach_context] build failed inside coach_response; continuing without snapshot",
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
            cfg=response_cfg,
            activity_id_hint=activity_id_hint,
            thread_activity_id=thread_activity_id,
        )
    except CoachResponseFallback as exc:
        timings["coach_response_context_ms"] = round(
            (time.perf_counter() - t_ctx0) * 1000, 2
        )
        record_coach_response_event(
            user_id=str(internal_user_id),
            outcome="fallback",
            user_message=user_message,
            properties={
                "mode": "coach_response_v1",
                "stage": "context_build",
                "reason": str(exc) or exc.__class__.__name__,
                "classifier": classification.as_log_dict(),
                "timings_ms": timings,
            },
        )
        raise
    timings["coach_response_context_ms"] = round(
        (time.perf_counter() - t_ctx0) * 1000, 2
    )

    if response_scope == "splits_only":
        from src.smartcoach_mobile_coach.coach_response.splits_content import (
            compose_splits_turn_content,
            render_deterministic_splits_block,
        )

        splits_block = render_deterministic_splits_block(ctx)
        if not splits_block:
            raise CoachResponseFallback("splits_only_missing_split_rows")
        responder_out = generate_review(
            ctx=ctx,
            coach_snapshot=coach_snapshot,
            base_system_content=base_system_content,
            conversation_history=conversation_history,
            user_message=user_message,
            history_window=history_window,
            internal_user_id=internal_user_id,
            cfg=response_cfg,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            splits_coaching_only=True,
        )
        final_content = compose_splits_turn_content(splits_block, responder_out.content)
    else:
        responder_out = generate_review(
            ctx=ctx,
            coach_snapshot=coach_snapshot,
            base_system_content=base_system_content,
            conversation_history=conversation_history,
            user_message=user_message,
            history_window=history_window,
            internal_user_id=internal_user_id,
            cfg=response_cfg,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        final_content = responder_out.content
    timings.update(responder_out.timings_ms)
    structured, sections_attached = build_coach_response_envelope(
        ctx=ctx,
        content=final_content,
        run_summary_layout=(
            RUN_SUMMARY_LAYOUT_INLINE
            if response_scope == "splits_only"
            else RUN_SUMMARY_LAYOUT_RECAP
        ),
    )
    meta = build_coach_response_meta(
        ctx=ctx,
        usage=responder_out.usage,
        cost=responder_out.cost,
        model=responder_out.model,
        timings_ms=timings,
        dialogue=response_directive_dialogue,
        sections_attached=sections_attached,
        classifier_summary=classification.as_log_dict(),
        coach_context_trace=coach_context_trace,
    )
    record_coach_response_event(
        user_id=str(internal_user_id),
        outcome="served",
        user_message=user_message,
        properties={
            "mode": "coach_response_v1",
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
