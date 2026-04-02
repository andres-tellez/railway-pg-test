"""
Lightweight dialogue management for SmartCoach mobile agent turns.

This module intentionally stays rules-based and deterministic:
- classify conversational turn type
- extract minimal state from prior text-only history
- produce a response directive for the current turn
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional, Set


_ACK_RE = re.compile(
    r"^\s*(thanks|thank you|got it|ok|okay|cool|nice|perfect|makes sense|understood)\s*[!.]?\s*$",
    re.IGNORECASE,
)
_CLARIFICATION_RE = re.compile(
    r"\b(what do you mean|can you clarify|i (do not|don't) understand|not clear|rephrase|say that again)\b",
    re.IGNORECASE,
)
_DRILL_DOWN_RE = re.compile(
    r"\b(why|how come|explain|more detail|go deeper|break it down|walk me through)\b",
    re.IGNORECASE,
)
_FOLLOW_UP_RE = re.compile(
    r"^\s*(and|also|what about|how about|plus|ok and|then what|what else)\b",
    re.IGNORECASE,
)
_REFERENTIAL_RE = re.compile(r"\b(that|it|this|those|same run)\b", re.IGNORECASE)
_RECAP_RE = re.compile(
    r"\b(recap|summary|summarize|repeat|again|full breakdown|full recap|everything)\b",
    re.IGNORECASE,
)
_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


@dataclass
class ConversationState:
    turn_count: int
    metrics_already_shared: List[str]
    topics_covered: List[str]
    last_run_date_mentioned: Optional[str]
    last_response_length: int
    last_topic: str

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ResponseDirective:
    turn_type: str
    target_length: str
    tone_hint: str
    focus: str
    avoid_repeating_metrics: List[str]
    allow_full_recap: bool

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def classify_turn(user_message: str, conversation_history: List[Dict[str, str]]) -> str:
    """
    Classify conversational role for this turn.

    Returns one of:
    - opening
    - follow_up
    - drill_down
    - new_topic
    - acknowledgment
    - clarification
    """
    msg = (user_message or "").strip()
    if not msg:
        return "follow_up"

    assistant_msgs = [
        m.get("content", "")
        for m in conversation_history
        if m.get("role") == "assistant" and m.get("content")
    ]
    if not assistant_msgs:
        return "opening"

    if _ACK_RE.search(msg):
        return "acknowledgment"
    if _CLARIFICATION_RE.search(msg):
        return "clarification"
    if _DRILL_DOWN_RE.search(msg):
        return "drill_down"

    current_topic = _infer_topic(msg)
    last_topic = _infer_topic(assistant_msgs[-1])

    if (
        current_topic != "general"
        and last_topic != "general"
        and current_topic != last_topic
    ):
        return "new_topic"

    short_msg = len(msg) <= 90
    if _FOLLOW_UP_RE.search(msg) or (short_msg and _REFERENTIAL_RE.search(msg)):
        return "follow_up"

    if short_msg and "?" in msg:
        return "follow_up"

    return "new_topic"


def extract_conversation_state(
    conversation_history: List[Dict[str, str]]
) -> ConversationState:
    """Build minimal conversation state from text-only history."""
    user_turns = sum(1 for m in conversation_history if m.get("role") == "user")
    assistant_texts = [
        m.get("content", "")
        for m in conversation_history
        if m.get("role") == "assistant" and m.get("content")
    ]
    all_assistant_text = "\n".join(assistant_texts)
    metrics = sorted(_extract_metrics(all_assistant_text))
    topics = sorted(_extract_topics(assistant_texts))
    last_assistant = assistant_texts[-1] if assistant_texts else ""
    last_date = _extract_last_date(assistant_texts)
    last_topic = _infer_topic(last_assistant)

    return ConversationState(
        turn_count=user_turns,
        metrics_already_shared=metrics,
        topics_covered=topics,
        last_run_date_mentioned=last_date,
        last_response_length=len(last_assistant),
        last_topic=last_topic,
    )


def plan_response(
    *,
    turn_type: str,
    state: ConversationState,
    user_message: str,
) -> ResponseDirective:
    """Create a compact per-turn response directive."""
    asks_recap = bool(_RECAP_RE.search((user_message or "").lower()))
    avoid_metrics = [] if asks_recap else list(state.metrics_already_shared)

    if turn_type == "opening":
        return ResponseDirective(
            turn_type=turn_type,
            target_length="short recap allowed; keep tight and scannable",
            tone_hint="coach-like, direct, grounded",
            focus="answer the initial ask with tool-grounded context",
            avoid_repeating_metrics=[],
            allow_full_recap=True,
        )

    if turn_type == "acknowledgment":
        return ResponseDirective(
            turn_type=turn_type,
            target_length="1 short sentence maximum",
            tone_hint="warm and concise",
            focus="acknowledge and keep moving without re-analysis",
            avoid_repeating_metrics=list(state.metrics_already_shared),
            allow_full_recap=False,
        )

    if turn_type == "clarification":
        return ResponseDirective(
            turn_type=turn_type,
            target_length="2-3 sentences",
            tone_hint="clear and simple",
            focus="rephrase the last point plainly without full recap",
            avoid_repeating_metrics=avoid_metrics,
            allow_full_recap=asks_recap,
        )

    if turn_type == "drill_down":
        return ResponseDirective(
            turn_type=turn_type,
            target_length="2-4 sentences focused on requested detail",
            tone_hint="specific and practical",
            focus="go deeper on the exact follow-up point",
            avoid_repeating_metrics=avoid_metrics,
            allow_full_recap=asks_recap,
        )

    if turn_type == "follow_up":
        return ResponseDirective(
            turn_type=turn_type,
            target_length="1-3 sentences",
            tone_hint="brief and direct",
            focus="answer only the new ask from this turn",
            avoid_repeating_metrics=avoid_metrics,
            allow_full_recap=asks_recap,
        )

    # new_topic fallback
    return ResponseDirective(
        turn_type="new_topic",
        target_length="2-4 sentences by default; expand only if asked",
        tone_hint="coach-like and conversational",
        focus="address the new topic directly",
        avoid_repeating_metrics=[] if asks_recap else avoid_metrics,
        allow_full_recap=asks_recap,
    )


def response_directive_section(directive: ResponseDirective) -> str:
    """
    Build a system prompt section that makes this turn plan explicit.
    This is intentionally short and concrete for easier debugging.
    """
    if directive.avoid_repeating_metrics:
        avoid_line = ", ".join(directive.avoid_repeating_metrics)
    else:
        avoid_line = "none"
    recap_line = "yes" if directive.allow_full_recap else "no"

    return (
        "## Response directive (current turn)\n"
        f"- Turn type: **{directive.turn_type}**\n"
        f"- Target length: {directive.target_length}\n"
        f"- Tone: {directive.tone_hint}\n"
        f"- Focus: {directive.focus}\n"
        f"- Avoid repeating metrics already shared unless asked: {avoid_line}\n"
        f"- Full recap requested by user: {recap_line}\n"
        "- Prior assistant messages are shared context. Do not re-explain unchanged points."
    )


def _extract_metrics(text: str) -> Set[str]:
    text_l = (text or "").lower()
    metrics: Set[str] = set()
    if "distance" in text_l or " mi" in text_l or " km" in text_l:
        metrics.add("distance")
    if "avg. pace" in text_l or "pace" in text_l or "/mi" in text_l or "/km" in text_l:
        metrics.add("pace")
    if "time" in text_l or "duration" in text_l:
        metrics.add("time")
    if "avg. hr" in text_l or "average hr" in text_l:
        metrics.add("avg_hr")
    if "max hr" in text_l:
        metrics.add("max_hr")
    if "hr drift" in text_l or "drift" in text_l:
        metrics.add("hr_drift")
    if "z2" in text_l or "adherence" in text_l:
        metrics.add("z2_adherence")
    if "efficiency" in text_l:
        metrics.add("efficiency")
    if "peer" in text_l or "vs" in text_l or "compared" in text_l:
        metrics.add("peer_comparison")
    return metrics


def _extract_topics(texts: Iterable[str]) -> Set[str]:
    topics = set()
    for txt in texts:
        topics.add(_infer_topic(txt))
    return {t for t in topics if t != "general"}


def _infer_topic(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ("run", "pace", "hr", "drift", "activity", "splits")):
        return "run_review"
    if any(k in t for k in ("week", "weekly", "trend", "progress", "readiness")):
        return "weekly_progress"
    if any(k in t for k in ("plan", "schedule", "workout this week", "adjust")):
        return "plan"
    if any(k in t for k in ("preference", "from now on", "verbosity", "tone")):
        return "preferences"
    return "general"


def _extract_last_date(texts: List[str]) -> Optional[str]:
    for txt in reversed(texts):
        m = _DATE_RE.search(txt)
        if m:
            return m.group(1)
    return None
