"""Single-completion responder for coach response."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.services.security.external_apis.openai_service import (
    OpenAIResponse,
    get_openai_service,
)
from src.smartcoach_mobile_coach.coach_response.config import CoachResponseConfig
from src.smartcoach_mobile_coach.coach_response.context import CoachRunContext
from src.smartcoach_mobile_coach.coach_response.errors import CoachResponseFallback
from src.smartcoach_mobile_coach.coach_response.prompt import build_messages

logger = logging.getLogger("smartcoach_mobile_coach")


@dataclass
class CoachResponderOutput:
    content: str
    usage: Dict[str, int]
    cost: float
    model: str
    timings_ms: Dict[str, Any]
    retried_on_empty: bool


def _empty_usage() -> Dict[str, int]:
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def _add_usage(target: Dict[str, int], src: Dict[str, int]) -> None:
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        target[key] = int(target.get(key, 0)) + int(src.get(key, 0))


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
    ctx: CoachRunContext,
    coach_snapshot: Optional[Dict[str, Any]],
    base_system_content: str,
    conversation_history: List[Dict[str, str]],
    user_message: str,
    history_window: int,
    internal_user_id: str,
    cfg: CoachResponseConfig,
    model: str,
    temperature: float,
    max_tokens: Optional[int],
    splits_coaching_only: bool = False,
) -> CoachResponderOutput:
    messages = build_messages(
        base_system_content=base_system_content,
        ctx=ctx,
        coach_snapshot=coach_snapshot,
        conversation_history=conversation_history,
        user_message=user_message,
        history_window=history_window,
        splits_coaching_only=splits_coaching_only,
    )
    use_model = cfg.responder_model_override or model
    effective_max_tokens = (
        max_tokens if max_tokens is not None else cfg.max_response_tokens
    )
    effective_max_tokens = min(effective_max_tokens, cfg.max_response_tokens)
    if splits_coaching_only:
        effective_max_tokens = min(effective_max_tokens, 400)
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
            max_tokens=effective_max_tokens,
            timeout=cfg.responder_timeout_s,
        )
    except Exception as exc:
        logger.warning("[coach_response.responder] first_call_failed: %s", exc)
        raise CoachResponseFallback(
            f"coach_response_first_call_failed:{type(exc).__name__}"
        ) from exc
    timings["coach_response_llm_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    _add_usage(usage, first.usage)
    cost_total += float(first.cost or 0.0)
    text = (first.content or "").strip()
    retried = False
    if not text and not splits_coaching_only:
        retried = True
        retry_messages = [dict(message) for message in messages]
        retry_messages.append(
            {
                "role": "system",
                "content": (
                    "Your previous attempt was empty. Reply with non-empty coaching prose "
                    "grounded in the provided JSON."
                ),
            }
        )
        t1 = time.perf_counter()
        try:
            second = _call_one(
                messages=retry_messages,
                internal_user_id=internal_user_id,
                model=use_model,
                temperature=min(temperature, 0.35),
                max_tokens=effective_max_tokens,
                timeout=cfg.responder_timeout_s,
            )
        except Exception as exc:
            logger.warning("[coach_response.responder] retry_call_failed: %s", exc)
            raise CoachResponseFallback(
                f"coach_response_retry_failed:{type(exc).__name__}"
            ) from exc
        timings["coach_response_llm_retry_ms"] = round(
            (time.perf_counter() - t1) * 1000, 2
        )
        _add_usage(usage, second.usage)
        cost_total += float(second.cost or 0.0)
        text = (second.content or "").strip()
        if not text:
            raise CoachResponseFallback("coach_response_empty_after_retry")
    return CoachResponderOutput(
        content=text,
        usage=usage,
        cost=cost_total,
        model=use_model,
        timings_ms=timings,
        retried_on_empty=retried,
    )
