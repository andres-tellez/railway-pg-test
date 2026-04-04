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


_ACK_TOKEN = (
    r"(thanks|thank you|got it|ok|okay|cool|nice|perfect|makes sense|understood)"
)
_ACK_RE = re.compile(
    rf"^\s*{_ACK_TOKEN}(?:\s*[,!.]*\s*{_ACK_TOKEN})*\s*[!.]?\s*$",
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
# Avoid matching the substring "run" inside "runs", "running", etc.
_RUN_WORD_RE = re.compile(r"\b(runs?|running)\b", re.IGNORECASE)


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
    intent: str
    target_length: str
    tone_hint: str
    focus: str
    avoid_repeating_metrics: List[str]
    allow_full_recap: bool
    narration_mode: str
    tool_strategy: str
    natural_style_notes: List[str]

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
    conversation_history: List[Dict[str, str]],
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
    intent = infer_intent(user_message)
    addon = _intent_addon(intent)
    asks_recap = bool(_RECAP_RE.search((user_message or "").lower()))
    avoid_metrics = [] if asks_recap else list(state.metrics_already_shared)

    if turn_type == "opening":
        return ResponseDirective(
            turn_type=turn_type,
            intent=intent,
            target_length="short recap allowed; keep tight and scannable",
            tone_hint="coach-like, direct, grounded",
            focus="answer the initial ask with tool-grounded context",
            avoid_repeating_metrics=[],
            allow_full_recap=True,
            narration_mode=addon["narration_mode"],
            tool_strategy=addon["tool_strategy"],
            natural_style_notes=addon["natural_style_notes"],
        )

    if turn_type == "acknowledgment":
        return ResponseDirective(
            turn_type=turn_type,
            intent=intent,
            target_length=(
                "MANDATORY: exactly one short sentence (one period or question mark max). "
                "No second sentence. No paragraph."
            ),
            tone_hint=(
                "Minimal acknowledgment only — natural, human; not customer-support or chatbot closing."
            ),
            focus=(
                "MUST: brief acknowledgment only. MUST NOT: coaching, analysis, guidance, metrics, "
                "follow-up questions, or tool calls. MUST NOT use filler such as “if you have more questions”, "
                "“feel free to ask”, “let me know”, “keep up the great work”. "
                "Acceptable flavor (paraphrase; do not echo this list in the reply): "
                "“Got it.” “Nice.” “Sounds good.” “Perfect.”"
            ),
            avoid_repeating_metrics=list(state.metrics_already_shared),
            allow_full_recap=False,
            narration_mode=addon["narration_mode"],
            tool_strategy=addon["tool_strategy"],
            natural_style_notes=addon["natural_style_notes"],
        )

    if turn_type == "clarification":
        return ResponseDirective(
            turn_type=turn_type,
            intent=intent,
            target_length="2-3 sentences",
            tone_hint="clear and simple",
            focus="rephrase the last point plainly without full recap",
            avoid_repeating_metrics=avoid_metrics,
            allow_full_recap=asks_recap,
            narration_mode=addon["narration_mode"],
            tool_strategy=addon["tool_strategy"],
            natural_style_notes=addon["natural_style_notes"],
        )

    if turn_type == "drill_down":
        return ResponseDirective(
            turn_type=turn_type,
            intent=intent,
            target_length=(
                "2-4 sentences. Start with a direct answer, then one compact explanation with 1-2 tool-grounded "
                "values only if they materially help. Keep language plain and human."
            ),
            tone_hint="Tight and focused, but conversational and warm.",
            focus=(
                "Answer the why directly, avoid metric dumping, and use only tool-grounded numbers. "
                "Include one practical coaching interpretation when useful."
            ),
            avoid_repeating_metrics=avoid_metrics,
            allow_full_recap=asks_recap,
            narration_mode=addon["narration_mode"],
            tool_strategy=addon["tool_strategy"],
            natural_style_notes=addon["natural_style_notes"],
        )

    if turn_type == "follow_up":
        return ResponseDirective(
            turn_type=turn_type,
            intent=intent,
            target_length=(
                "2-4 sentences max. Lead with direct answer, then add one concise interpretation. "
                "Use at most 1-2 key tool-backed values when relevant."
            ),
            tone_hint="Coach texting: direct, natural, and grounded.",
            focus=(
                "Answer the follow-up directly and avoid repeating prior full metric blocks. "
                "Use the smallest set of numbers needed, grounded in tool outputs, then stop."
            ),
            avoid_repeating_metrics=avoid_metrics,
            allow_full_recap=asks_recap,
            narration_mode=addon["narration_mode"],
            tool_strategy=addon["tool_strategy"],
            natural_style_notes=addon["natural_style_notes"],
        )

    # new_topic fallback
    return ResponseDirective(
        turn_type="new_topic",
        intent=intent,
        target_length="2-4 sentences by default; expand only if asked",
        tone_hint="coach-like and conversational",
        focus="address the new topic directly",
        avoid_repeating_metrics=[] if asks_recap else avoid_metrics,
        allow_full_recap=asks_recap,
        narration_mode=addon["narration_mode"],
        tool_strategy=addon["tool_strategy"],
        natural_style_notes=addon["natural_style_notes"],
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

    base = (
        "## Response directive (current turn)\n"
        f"- Turn type: **{directive.turn_type}**\n"
        f"- Intent: **{directive.intent}**\n"
        f"- Target length: {directive.target_length}\n"
        f"- Tone: {directive.tone_hint}\n"
        f"- Focus: {directive.focus}\n"
        f"- Narration mode: {directive.narration_mode}\n"
        f"- Tool strategy: {directive.tool_strategy}\n"
        f"- Avoid repeating metrics already shared unless asked: {avoid_line}\n"
        f"- Full recap requested by user: {recap_line}\n"
        "- Prior assistant messages are shared context. Do not re-explain unchanged points."
    )
    if directive.natural_style_notes:
        natural_lines = "\n".join(
            [f"- {line}" for line in directive.natural_style_notes]
        )
        base += (
            "\n\n### Human coach style addon\n"
            "- Keep the reply sounding like one coach talking to one athlete, not a report.\n"
            "- Stay tool-grounded for numbers, but narrate naturally.\n"
            f"{natural_lines}"
        )

    if directive.turn_type == "acknowledgment":
        ack_hard = (
            "\n\n### Acknowledgment — HARD CONSTRAINTS (must obey; overrides softer wording elsewhere)\n"
            "- Output **exactly one** short sentence. **No** second sentence.\n"
            "- **No** filler or closings: e.g. “if you have more questions”, “feel free to ask”, "
            "“let me know”, “keep up the great work”, “happy to help”.\n"
            "- **No** coaching, analysis, guidance, metrics, or tools — the user did not ask a new question.\n"
            "- Style: minimal and natural (e.g. “Got it.” “Nice.” “Sounds good.” “Perfect.”) — paraphrase; "
            "do not list examples in the reply.\n"
            "- This is a **hard** constraint, not a suggestion."
        )
        return base + ack_hard

    return base


def infer_intent(user_message: str) -> str:
    """Infer lightweight intent for addon-style response shaping."""
    t = (user_message or "").lower().strip()
    if not t:
        return "general_chat"

    if any(
        k in t
        for k in (
            "predict",
            "projection",
            "project",
            "marathon time",
            "finish time",
            "goal time",
        )
    ):
        return "race_projection"
    if any(
        k in t
        for k in (
            "last 30 days",
            "this month",
            "total miles",
            "how many runs",
            "mileage by week",
            "weekly mileage",
        )
    ):
        return "volume_query"
    if any(k in t for k in ("trend", "progress", "readiness", "on track", "improving")):
        return "training_trend"
    if any(
        k in t
        for k in (
            "how was my run",
            "analyze my run",
            "this run",
            "that run",
            "last run",
        )
    ):
        return "run_analysis"
    if any(k in t for k in ("hr drift", "z2", "zone", "pace", "heart rate")):
        return "metric_explainer"
    if any(k in t for k in ("preference", "from now on", "verbosity", "tone")):
        return "preference_update"
    return "general_chat"


def _intent_addon(intent: str) -> Dict[str, Any]:
    """Second-layer addon: intent-specific narration + retrieval strategy."""
    defaults: Dict[str, Any] = {
        "narration_mode": "compact_coach",
        "tool_strategy": "Use the minimum required tools, then answer directly from results.",
        "natural_style_notes": [
            "Open with a direct answer, then one short interpretation.",
            "Avoid robotic templates and avoid stat dumps unless user asks.",
            "If confidence is limited by missing tool data, say so plainly in one line.",
        ],
    }
    profiles: Dict[str, Dict[str, Any]] = {
        "race_projection": {
            "narration_mode": "scenario_coach",
            "tool_strategy": (
                "Prefer trend + historical race context tools before projecting. "
                "If projection assumptions are needed, state them explicitly and label output as estimate."
            ),
            "natural_style_notes": [
                "Sound like a planning coach: confident but honest about uncertainty.",
                "Use scenario framing when useful (today / conservative / on-track), with tool-grounded values only.",
                "Close with one practical next-step sentence tied to the projection window.",
            ],
        },
        "volume_query": {
            "narration_mode": "numbers_then_context",
            "tool_strategy": (
                "Use aggregate_runs_in_range for totals and weekly_summaries; keep the window explicit and consistent."
            ),
            "natural_style_notes": [
                "Lead with the exact number the user asked for, then a short plain-language context line.",
                "If listing weekly rows, keep labels simple and scannable.",
            ],
        },
        "training_trend": {
            "narration_mode": "coach_story",
            "tool_strategy": (
                "Use weekly insight / training KPI tools first; summarize trend direction before giving advice."
            ),
            "natural_style_notes": [
                "Highlight one main trend, not five competing themes.",
                "Give one concrete coaching implication from the trend.",
            ],
        },
        "run_analysis": {
            "narration_mode": "run_recap",
            "tool_strategy": (
                "Resolve run identity first, then use run summary payload for facts and interpretation."
            ),
            "natural_style_notes": [
                "Blend facts into natural language; avoid report-like headings unless clarity needs them.",
                "Keep the recap personal and specific to this run.",
            ],
        },
        "metric_explainer": {
            "narration_mode": "plain_explainer",
            "tool_strategy": "Use the smallest tool payload that contains the requested metric definitions.",
            "natural_style_notes": [
                "Define the metric in plain words first, then provide value/range.",
                "Skip unrelated stats; stay focused on the asked metric.",
            ],
        },
        "preference_update": {
            "narration_mode": "confirm_and_apply",
            "tool_strategy": "Confirm intent briefly and apply preference tool update.",
            "natural_style_notes": [
                "One-line confirmation is enough unless user asked for details.",
            ],
        },
    }
    out = dict(defaults)
    out.update(profiles.get(intent, {}))
    return out


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
    if any(k in t for k in ("week", "weekly", "trend", "progress", "readiness")):
        return "weekly_progress"
    if any(k in t for k in ("plan", "schedule", "workout this week", "adjust")):
        return "plan"
    if any(k in t for k in ("preference", "from now on", "verbosity", "tone")):
        return "preferences"
    if (
        _RUN_WORD_RE.search(t)
        or "pace" in t
        or "drift" in t
        or re.search(r"\bhr\b", t)
        or "activity" in t
        or "splits" in t
    ):
        return "run_review"
    return "general"


def _extract_last_date(texts: List[str]) -> Optional[str]:
    for txt in reversed(texts):
        m = _DATE_RE.search(txt)
        if m:
            return m.group(1)
    return None
