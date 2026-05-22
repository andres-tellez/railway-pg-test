"""Intent classifier for isolated coach response."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.services.security.external_apis.openai_service import (
    CostLimitExceededError,
    RateLimitExceededError,
    get_openai_service,
)
from src.smartcoach_mobile_coach.coach_response.config import CoachResponseConfig
from src.smartcoach_mobile_coach.dialogue_manager import (
    INTENT_RUN_ANALYSIS,
    INTENT_SPLIT_DETAIL,
    infer_intent,
)

logger = logging.getLogger("smartcoach_mobile_coach")

_VALID_SCOPES = ("single_run", "splits_only", "comparison", "other")
_VALID_CONFIDENCE = ("high", "medium", "low")
_VALID_DAY_HINTS = ("today", "yesterday", "last_run", "named", None)


@dataclass(frozen=True)
class ClassifierResult:
    is_run_review: bool
    scope: str
    confidence: str
    day_hint: Optional[str] = None
    source: str = "heuristic"
    reason_code: str = ""

    def as_log_dict(self) -> Dict[str, Any]:
        return {
            "is_run_review": self.is_run_review,
            "scope": self.scope,
            "confidence": self.confidence,
            "day_hint": self.day_hint,
            "source": self.source,
            "reason_code": self.reason_code,
        }


_REVIEW_PHRASES = (
    "how was my run",
    "how was my last run",
    "how did i do",
    "how did that go",
    "how did today go",
    "analyze my run",
    "review my run",
    "look at my run",
    "look at my splits",
    "review my splits",
    "was that too hard",
    "was that too easy",
    "did i run this right",
    "did i run it right",
    "what could i have done better",
)

_SPLIT_HINTS = (
    "split",
    "splits",
    "mile by mile",
    "mile-by-mile",
    "per mile",
    "each mile",
    "lap by lap",
)

_NON_REVIEW_HINTS = (
    "build a plan",
    "build me a plan",
    "create a plan",
    "training plan",
    "race plan",
    "race projection",
    "marathon time",
    "this week",
    "weekly volume",
    "connect strava",
    "what is z2",
    "explain z2",
    "explain hr",
)

_SHORT_REFERENTIAL = re.compile(
    r"^\s*(was that|was it|how was that|how was it|how about it|"
    r"what about it|did i do|was the run|was my run)\b",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    return (text or "").strip().lower()


def _infer_day_hint(text_l: str) -> Optional[str]:
    if "yesterday" in text_l:
        return "yesterday"
    if " today" in f" {text_l} " or text_l.startswith("today"):
        return "today"
    if "last run" in text_l or "most recent" in text_l or "latest run" in text_l:
        return "last_run"
    return None


def _day_hint_for_run_review(text_l: str) -> str:
    hint = _infer_day_hint(text_l)
    return hint if hint is not None else "last_run"


def _heuristic_classify(user_message: str) -> ClassifierResult:
    msg = _normalize(user_message)
    if not msg:
        return ClassifierResult(
            is_run_review=False,
            scope="other",
            confidence="high",
            reason_code="empty_message",
        )
    if any(p in msg for p in _REVIEW_PHRASES):
        scope = "splits_only" if any(s in msg for s in _SPLIT_HINTS) else "single_run"
        return ClassifierResult(
            is_run_review=True,
            scope=scope,
            confidence="high",
            day_hint=_day_hint_for_run_review(msg),
            reason_code="review_phrase",
        )
    if any(s in msg for s in _SPLIT_HINTS):
        return ClassifierResult(
            is_run_review=True,
            scope="splits_only",
            confidence="high",
            day_hint=_day_hint_for_run_review(msg),
            reason_code="split_hint",
        )
    if any(p in msg for p in _NON_REVIEW_HINTS):
        return ClassifierResult(
            is_run_review=False,
            scope="other",
            confidence="high",
            reason_code="non_review_hint",
        )
    inferred = infer_intent(user_message)
    if inferred == INTENT_RUN_ANALYSIS:
        return ClassifierResult(
            is_run_review=True,
            scope="single_run",
            confidence="medium",
            day_hint=_day_hint_for_run_review(msg),
            reason_code="infer_intent_run_analysis",
        )
    if inferred == INTENT_SPLIT_DETAIL:
        return ClassifierResult(
            is_run_review=True,
            scope="splits_only",
            confidence="medium",
            day_hint=_day_hint_for_run_review(msg),
            reason_code="infer_intent_split_detail",
        )
    if _SHORT_REFERENTIAL.search(user_message or ""):
        return ClassifierResult(
            is_run_review=False,
            scope="other",
            confidence="low",
            reason_code="short_referential_ambiguous",
        )
    return ClassifierResult(
        is_run_review=False,
        scope="other",
        confidence="low",
        reason_code="no_match",
    )


_LLM_SYSTEM_PROMPT = (
    "You are a strict intent router for a running coach app. Decide whether the "
    "latest USER message is asking the coach to review a SPECIFIC, ALREADY-COMPLETED RUN. "
    "Return ONLY compact JSON matching this schema:\n"
    "{\n"
    '  "is_run_review": true|false,\n'
    '  "scope": "single_run"|"splits_only"|"comparison"|"other",\n'
    '  "confidence": "high"|"medium"|"low",\n'
    '  "day_hint": "today"|"yesterday"|"last_run"|"named"|null\n'
    "}\n"
    "Rules: future/plan/race-projection questions are not_run_review. "
    'Metric definitions ("what is Z2?") are not_run_review. '
    'If they ask to look at splits / per-mile / lap-by-lap, scope="splits_only". '
    "Paraphrases count."
)


def _coerce_classifier_json(raw: str) -> Optional[Dict[str, Any]]:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    is_review = obj.get("is_run_review")
    if not isinstance(is_review, bool):
        return None
    scope = obj.get("scope")
    if scope not in _VALID_SCOPES:
        return None
    confidence = obj.get("confidence")
    if confidence not in _VALID_CONFIDENCE:
        return None
    day_hint = obj.get("day_hint")
    if day_hint not in _VALID_DAY_HINTS:
        day_hint = None
    return {
        "is_run_review": is_review,
        "scope": scope,
        "confidence": confidence,
        "day_hint": day_hint,
    }


def _build_classifier_messages(
    user_message: str, conversation_history: List[Dict[str, str]]
) -> List[Dict[str, str]]:
    messages: List[Dict[str, str]] = [{"role": "system", "content": _LLM_SYSTEM_PROMPT}]
    last_assistant_preview = ""
    for message in reversed(conversation_history or []):
        if (
            message.get("role") == "assistant"
            and (message.get("content") or "").strip()
        ):
            last_assistant_preview = str(message.get("content"))[:280].strip()
            break
    if last_assistant_preview:
        messages.append(
            {
                "role": "system",
                "content": (
                    "Recent assistant message (context only, not the message to classify):\n"
                    + last_assistant_preview
                ),
            }
        )
    messages.append({"role": "user", "content": (user_message or "").strip()})
    return messages


def _llm_classify(
    *,
    user_message: str,
    conversation_history: List[Dict[str, str]],
    internal_user_id: str,
    cfg: CoachResponseConfig,
) -> Optional[ClassifierResult]:
    service = get_openai_service()
    messages = _build_classifier_messages(user_message, conversation_history)
    t0 = time.perf_counter()
    try:
        result = service.chat_completion(
            messages=messages,
            user_id=str(internal_user_id),
            model=cfg.classifier_model,
            temperature=0.0,
            max_tokens=cfg.classifier_max_tokens,
            timeout=cfg.classifier_timeout_s,
            require_json=True,
        )
    except (RateLimitExceededError, CostLimitExceededError):
        logger.info("[coach_response.classifier] llm_skipped reason=rate_or_cost_limit")
        return None
    except Exception:
        logger.warning(
            "[coach_response.classifier] llm_failed; falling back to heuristic",
            exc_info=True,
        )
        return None
    coerced = _coerce_classifier_json(result.content or "")
    if coerced is None:
        logger.info(
            "[coach_response.classifier] llm_invalid_json fallback=heuristic raw_preview=%r",
            (result.content or "")[:80],
        )
        return None
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    logger.info(
        "[coach_response.classifier] llm_ok ms=%s scope=%s confidence=%s",
        elapsed_ms,
        coerced["scope"],
        coerced["confidence"],
    )
    return ClassifierResult(
        is_run_review=bool(coerced["is_run_review"]),
        scope=str(coerced["scope"]),
        confidence=str(coerced["confidence"]),
        day_hint=coerced.get("day_hint"),
        source="llm",
        reason_code="llm_classified",
    )


def classify_user_message(
    *,
    user_message: str,
    conversation_history: List[Dict[str, str]],
    internal_user_id: str,
    cfg: CoachResponseConfig,
) -> ClassifierResult:
    heuristic = _heuristic_classify(user_message)
    if heuristic.confidence == "high":
        return heuristic
    if cfg.classifier_mode != "llm":
        return heuristic
    llm_result = _llm_classify(
        user_message=user_message,
        conversation_history=conversation_history,
        internal_user_id=internal_user_id,
        cfg=cfg,
    )
    if llm_result is None:
        return ClassifierResult(
            is_run_review=heuristic.is_run_review,
            scope=heuristic.scope,
            confidence=heuristic.confidence,
            day_hint=heuristic.day_hint,
            source="llm_fallback",
            reason_code=heuristic.reason_code,
        )
    return llm_result
