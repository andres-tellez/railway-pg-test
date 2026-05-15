"""
Intent classifier for Run Review V2.

The job is small and well-bounded: decide whether a turn is a *completed-run
review* and, if so, the rough scope (single run, splits, or comparison).
Everything else falls back to the existing orchestrator / fastpath.

Order of operations:

1. **Hard deterministic short-circuits** — positive phrases (e.g. "how was my run",
   "splits") are checked *before* generic "weekly / this week" negatives so
   messages like "How was my run this week?" still route to V2.
2. Then :func:`infer_intent` for medium-confidence cases — common phrases often
   never touch an extra LLM call.
3. **LLM JSON router** — only when (a) the flag is ``llm`` *and* (b) the
   short-circuit was inconclusive. Cheap model, strict JSON, short prompt.
4. **Safe fallback** — any classifier error → "not a run review" so the
   orchestrator can continue normally.

The classifier never fetches DB data or splits. Pure text in → JSON out.
"""

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
from src.smartcoach_mobile_coach.dialogue_manager import (
    INTENT_RUN_ANALYSIS,
    INTENT_SPLIT_DETAIL,
    infer_intent,
)
from src.smartcoach_mobile_coach.run_review.config import RunReviewConfig

logger = logging.getLogger("smartcoach_mobile_coach")


_VALID_SCOPES = ("single_run", "splits_only", "comparison", "other")
_VALID_CONFIDENCE = ("high", "medium", "low")
_VALID_DAY_HINTS = ("today", "yesterday", "last_run", "named", None)


@dataclass(frozen=True)
class ClassifierResult:
    """Outcome of the run-review router for a single user turn."""

    is_run_review: bool
    scope: str  # one of _VALID_SCOPES
    confidence: str  # one of _VALID_CONFIDENCE
    day_hint: Optional[str] = None
    source: str = "heuristic"  # "heuristic" | "llm" | "llm_fallback"
    reason_code: str = ""  # short tag for logs / tests

    def as_log_dict(self) -> Dict[str, Any]:
        return {
            "is_run_review": self.is_run_review,
            "scope": self.scope,
            "confidence": self.confidence,
            "day_hint": self.day_hint,
            "source": self.source,
            "reason_code": self.reason_code,
        }


# Hints that strongly imply the user is asking about a specific completed run.
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


def _heuristic_classify(user_message: str) -> ClassifierResult:
    """Return a deterministic classification when the message is unambiguous."""
    msg = _normalize(user_message)
    if not msg:
        return ClassifierResult(
            is_run_review=False,
            scope="other",
            confidence="high",
            reason_code="empty_message",
        )

    # Strong positives before negatives: `_NON_REVIEW_HINTS` includes broad
    # substrings like "this week" that appear in legitimate run-review asks
    # ("How was my run this week?").
    if any(p in msg for p in _REVIEW_PHRASES):
        scope = "splits_only" if any(s in msg for s in _SPLIT_HINTS) else "single_run"
        return ClassifierResult(
            is_run_review=True,
            scope=scope,
            confidence="high",
            day_hint=_infer_day_hint(msg),
            reason_code="review_phrase",
        )

    if any(s in msg for s in _SPLIT_HINTS):
        return ClassifierResult(
            is_run_review=True,
            scope="splits_only",
            confidence="high",
            day_hint=_infer_day_hint(msg),
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
            day_hint=_infer_day_hint(msg),
            reason_code="infer_intent_run_analysis",
        )
    if inferred == INTENT_SPLIT_DETAIL:
        return ClassifierResult(
            is_run_review=True,
            scope="splits_only",
            confidence="medium",
            day_hint=_infer_day_hint(msg),
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
    'Paraphrases count: "was that too hard?", "what could I have done better?", '
    '"did I run this correctly?" are run reviews. Never include explanations — JSON only.'
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
    conf = obj.get("confidence")
    if conf not in _VALID_CONFIDENCE:
        return None
    day_hint = obj.get("day_hint")
    if day_hint not in _VALID_DAY_HINTS:
        day_hint = None
    return {
        "is_run_review": is_review,
        "scope": scope,
        "confidence": conf,
        "day_hint": day_hint,
    }


def _build_classifier_messages(
    user_message: str, conversation_history: List[Dict[str, str]]
) -> List[Dict[str, str]]:
    messages: List[Dict[str, str]] = [{"role": "system", "content": _LLM_SYSTEM_PROMPT}]
    # Only the latest assistant + user line for tie-breaking on referential phrases
    last_assistant_preview = ""
    for m in reversed(conversation_history or []):
        if m.get("role") == "assistant" and (m.get("content") or "").strip():
            last_assistant_preview = str(m.get("content"))[:280].strip()
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
    cfg: RunReviewConfig,
) -> Optional[ClassifierResult]:
    """One small JSON-mode chat completion. Returns ``None`` on failure."""
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
        logger.info("[run_review.classifier] llm_skipped reason=rate_or_cost_limit")
        return None
    except Exception:  # pragma: no cover - defensive; covered by fallback path
        logger.warning(
            "[run_review.classifier] llm_failed; falling back to heuristic",
            exc_info=True,
        )
        return None
    coerced = _coerce_classifier_json(result.content or "")
    if coerced is None:
        logger.info(
            "[run_review.classifier] llm_invalid_json fallback=heuristic raw_preview=%r",
            (result.content or "")[:80],
        )
        return None
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    logger.info(
        "[run_review.classifier] llm_ok ms=%s scope=%s confidence=%s",
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
    cfg: RunReviewConfig,
) -> ClassifierResult:
    """
    Top-level entry. Always returns a :class:`ClassifierResult`.

    The orchestrator never raises out of this function; on any failure we
    return a deterministic "not a run review" so the legacy path can run.
    """
    heuristic = _heuristic_classify(user_message)

    # Hard yes from heuristics: skip the LLM entirely.
    if heuristic.is_run_review and heuristic.confidence == "high":
        return heuristic
    # Hard no from heuristics: skip the LLM entirely.
    if not heuristic.is_run_review and heuristic.confidence == "high":
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
