"""
Run Review V2 responder — one focused LLM call, no tool round-trips.

This file owns the OpenAI call and the empty-text retry policy. It does
NOT decide whether to run V2 (that's :mod:`.entry`) and does NOT format
the final mobile envelope (that's :mod:`.payload`).

Design:

- Single ``chat_completion`` call with the augmented system prompt.
- If the model returns empty text, retry **once** with a short directive
  appendix. Same model, same temperature minus a small clamp. This
  mirrors the existing ``run_recap_fastpath`` empty-retry pattern.
- If still empty, raise :class:`RunReviewFallback`. The orchestrator can
  decide to drop into the legacy fastpath / full agent loop.

We never silently swallow upstream OpenAI errors here — they propagate
to ``entry.handle_run_review_turn``, which converts them to fallbacks
with telemetry.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.services.security.external_apis.openai_service import (
    OpenAIResponse,
    get_openai_service,
)
from src.smartcoach_mobile_coach.run_review.config import RunReviewConfig
from src.smartcoach_mobile_coach.run_review.context import RunReviewContext
from src.smartcoach_mobile_coach.run_review.errors import RunReviewFallback
from src.smartcoach_mobile_coach.run_review.prompt import build_messages

logger = logging.getLogger("smartcoach_mobile_coach")


_EMPTY_RETRY_APPENDIX = (
    "\n\n## Required output\n"
    "Your previous attempt produced no text. Reply with **3–6 sentences** of "
    "coaching prose about this run using only the pre-loaded JSON. Do **not** "
    "leave the reply empty. Do **not** return JSON."
)


@dataclass
class ResponderOutput:
    """Result of one or more chat completions for this turn."""

    content: str
    usage: Dict[str, int]
    cost: float
    model: str
    timings_ms: Dict[str, Any]
    retried_on_empty: bool


def _empty_usage() -> Dict[str, int]:
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def _add_usage(target: Dict[str, int], src: Dict[str, int]) -> None:
    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
        target[k] = int(target.get(k, 0)) + int(src.get(k, 0))


def _call_one(
    *,
    messages: List[Dict[str, str]],
    internal_user_id: str,
    model: str,
    temperature: float,
    max_tokens: int,
    timeout: float,
) -> OpenAIResponse:
    service = get_openai_service()
    return service.chat_completion(
        messages=messages,
        user_id=str(internal_user_id),
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )


def generate_review(
    *,
    ctx: RunReviewContext,
    base_system_content: str,
    conversation_history: List[Dict[str, str]],
    user_message: str,
    history_window: int,
    internal_user_id: str,
    cfg: RunReviewConfig,
    model: str,
    temperature: float,
    max_tokens: Optional[int],
) -> ResponderOutput:
    """
    Make the run-review completion(s) and return aggregated usage + text.

    Raises :class:`RunReviewFallback` when the LLM is unresponsive twice
    or the call itself fails.
    """
    messages = build_messages(
        base_system_content=base_system_content,
        ctx=ctx,
        conversation_history=conversation_history,
        user_message=user_message,
        history_window=history_window,
    )

    use_model = cfg.responder_model_override or model
    eff_max_tokens = max_tokens if max_tokens is not None else cfg.max_response_tokens
    eff_max_tokens = min(eff_max_tokens, cfg.max_response_tokens)

    usage: Dict[str, int] = _empty_usage()
    cost_total = 0.0
    timings: Dict[str, Any] = {}

    t0 = time.perf_counter()
    try:
        first = _call_one(
            messages=messages,
            internal_user_id=internal_user_id,
            model=use_model,
            temperature=temperature,
            max_tokens=eff_max_tokens,
            timeout=cfg.responder_timeout_s,
        )
    except Exception as exc:
        logger.warning(
            "[run_review.responder] first_call_failed; falling back: %s",
            exc,
        )
        raise RunReviewFallback(
            f"responder_first_call_failed:{type(exc).__name__}"
        ) from exc
    timings["run_review_v2_llm_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    _add_usage(usage, first.usage)
    cost_total += float(first.cost or 0.0)
    text = (first.content or "").strip()

    retried = False
    if not text:
        retried = True
        retry_messages = [dict(m) for m in messages]
        if retry_messages and retry_messages[0].get("role") == "system":
            retry_messages[0]["content"] = (
                str(retry_messages[0].get("content") or "") + _EMPTY_RETRY_APPENDIX
            )
        t1 = time.perf_counter()
        try:
            second = _call_one(
                messages=retry_messages,
                internal_user_id=internal_user_id,
                model=use_model,
                temperature=min(temperature, 0.35),
                max_tokens=eff_max_tokens,
                timeout=cfg.responder_timeout_s,
            )
        except Exception as exc:
            logger.warning(
                "[run_review.responder] retry_call_failed; falling back: %s",
                exc,
            )
            raise RunReviewFallback(
                f"responder_retry_failed:{type(exc).__name__}"
            ) from exc
        timings["run_review_v2_llm_retry_ms"] = round(
            (time.perf_counter() - t1) * 1000, 2
        )
        _add_usage(usage, second.usage)
        cost_total += float(second.cost or 0.0)
        text = (second.content or "").strip()
        if not text:
            raise RunReviewFallback("responder_empty_after_retry")

    return ResponderOutput(
        content=text,
        usage=usage,
        cost=cost_total,
        model=use_model,
        timings_ms=timings,
        retried_on_empty=retried,
    )
