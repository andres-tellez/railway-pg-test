"""
Run Review V2 public entry — the only thing the orchestrator imports.

Two functions:

- :func:`should_use_run_review_v2`: gate; returns ``True`` when the feature
  flag is on **and** classification says the turn is a completed-run review.
- :func:`handle_run_review_turn`: orchestrates the full V2 path
  (context build → prompt → single LLM call → envelope) and returns
  ``(structured_payload, meta)`` matching what the orchestrator already
  returns for the legacy fastpath.

Any failure inside V2 raises :class:`RunReviewFallback`. The orchestrator
should swallow that and continue into the legacy fastpath / full agent
loop. We never raise out of ``should_use_run_review_v2``.

``plan_creation_mode`` is logged in the orchestrator gate timings only; this
gate relies on the classifier, not the thread-wide plan-intake flag.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from src.smartcoach_mobile_coach.run_review.classifier import (
    ClassifierResult,
    classify_user_message,
)
from src.smartcoach_mobile_coach.run_review.config import (
    RunReviewConfig,
    load_config,
)
from src.smartcoach_mobile_coach.run_review.context_builder import build_context
from src.smartcoach_mobile_coach.run_review.errors import (
    RunReviewFallback,
    RunReviewSkip,
)
from src.smartcoach_mobile_coach.run_review.payload import (
    build_run_review_envelope,
    build_run_review_meta,
)
from src.smartcoach_mobile_coach.run_review.responder import generate_review
from src.smartcoach_mobile_coach.run_review.telemetry import (
    record_run_review_event,
)

logger = logging.getLogger("smartcoach_mobile_coach")


def should_use_run_review_v2(
    *,
    user_message: str,
    conversation_history: List[Dict[str, str]],
    internal_user_id: str,
    cfg: Optional[RunReviewConfig] = None,
) -> Tuple[bool, Optional[ClassifierResult], RunReviewConfig]:
    """
    Cheap gate. Returns ``(use_v2, classifier_result_or_None, cfg)``.

    Threads with ``latest_plan_intake_state`` force ``plan_creation_mode=True``
    in the orchestrator, but that must not block run-review classification;
    this function always runs the classifier when the flag is on.
    """
    snapshot = cfg or load_config()
    if not snapshot.enabled:
        return False, None, snapshot
    try:
        result = classify_user_message(
            user_message=user_message,
            conversation_history=conversation_history,
            internal_user_id=internal_user_id,
            cfg=snapshot,
        )
    except Exception:  # pragma: no cover - defensive
        logger.warning(
            "[run_review.entry] classifier_threw_unexpectedly; gate=False",
            exc_info=True,
        )
        return False, None, snapshot
    return result.is_run_review, result, snapshot


def handle_run_review_turn(  # pylint: disable=too-many-arguments,too-many-locals
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
    cfg: Optional[RunReviewConfig] = None,
    classifier_result: Optional[ClassifierResult] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Run the V2 path end-to-end and return ``(structured_payload, meta)``.

    The orchestrator should call this only after ``should_use_run_review_v2``
    returned ``True``; we still re-classify defensively if no classifier
    result was passed in. Any failure raises :class:`RunReviewFallback`.
    """
    snapshot = cfg or load_config()
    if not snapshot.enabled:
        raise RunReviewFallback("flag_disabled_at_handler")

    classification = classifier_result
    if classification is None:
        classification = classify_user_message(
            user_message=user_message,
            conversation_history=conversation_history,
            internal_user_id=internal_user_id,
            cfg=snapshot,
        )
    if not classification.is_run_review:
        # The orchestrator usually filters this case, but be safe.
        raise RunReviewSkip("classifier_says_not_run_review")

    timings: Dict[str, Any] = {}

    t_ctx0 = time.perf_counter()
    try:
        ctx = build_context(
            session=session,
            internal_user_id=internal_user_id,
            anchor_local_date=anchor_local_date,
            classifier=classification,
            cfg=snapshot,
            activity_id_hint=activity_id_hint,
            thread_activity_id=thread_activity_id,
        )
    except RunReviewFallback as exc:
        timings["run_review_v2_context_ms"] = round(
            (time.perf_counter() - t_ctx0) * 1000, 2
        )
        record_run_review_event(
            user_id=str(internal_user_id),
            outcome="fallback",
            user_message=user_message,
            properties={
                "stage": "context_build",
                "reason": str(exc) or exc.__class__.__name__,
                "classifier": classification.as_log_dict(),
                "timings_ms": timings,
            },
        )
        raise
    timings["run_review_v2_context_ms"] = round(
        (time.perf_counter() - t_ctx0) * 1000, 2
    )

    try:
        responder_out = generate_review(
            ctx=ctx,
            base_system_content=base_system_content,
            conversation_history=conversation_history,
            user_message=user_message,
            history_window=history_window,
            internal_user_id=internal_user_id,
            cfg=snapshot,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except RunReviewFallback as exc:
        record_run_review_event(
            user_id=str(internal_user_id),
            outcome="fallback",
            user_message=user_message,
            properties={
                "stage": "responder",
                "reason": str(exc) or exc.__class__.__name__,
                "classifier": classification.as_log_dict(),
                "activity_id": ctx.activity_id,
                "resolved_via": ctx.resolved_via,
                "timings_ms": timings,
            },
        )
        raise

    timings.update(responder_out.timings_ms)

    structured, sections_attached = build_run_review_envelope(
        ctx=ctx,
        content=responder_out.content,
    )

    meta = build_run_review_meta(
        ctx=ctx,
        usage=responder_out.usage,
        cost=responder_out.cost,
        model=responder_out.model,
        timings_ms=timings,
        dialogue=response_directive_dialogue,
        sections_attached=sections_attached,
        classifier_summary=classification.as_log_dict(),
    )

    record_run_review_event(
        user_id=str(internal_user_id),
        outcome="served",
        user_message=user_message,
        properties={
            "activity_id": ctx.activity_id,
            "resolved_via": ctx.resolved_via,
            "scope": ctx.scope,
            "classifier": classification.as_log_dict(),
            "retried_on_empty": responder_out.retried_on_empty,
            "splits_attached": ctx.splits is not None,
            "splits_count": ctx.splits_count,
            "sections_attached": sections_attached,
            "timings_ms": timings,
            "usage": responder_out.usage,
        },
    )

    logger.info(
        "[run_review_v2] served activity_id=%s scope=%s resolved_via=%s "
        "splits_attached=%s sections_attached=%s timings_ms=%s",
        ctx.activity_id,
        ctx.scope,
        ctx.resolved_via,
        bool(ctx.splits),
        sections_attached,
        timings,
    )

    return structured, meta
