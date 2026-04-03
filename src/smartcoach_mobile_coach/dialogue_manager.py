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
            target_length=(
                "HARD OUTPUT BOUNDARY: **at most 2 sentences** — these are strict limits, not guidelines. "
                "**Sentence 1:** direct answer to the **why** only — when a tool-backed number clarifies the answer, "
                "weave **one** relevant value into this sentence in plain coach language (not a stat table). "
                "**Sentence 2 (optional):** one short human interpretation only. "
                "**STOP** generating immediately after the final allowed sentence — no sentence 3, no tail, no PS."
            ),
            tone_hint=(
                "Tight and focused — answer only what they asked. Confident coach voice, not a lecture."
            ),
            focus=(
                "**No** additional ideas beyond those 1-2 sentences. "
                "After the last allowed sentence, **end the reply** — do not append explanation, summary, coaching, "
                "or “one more thing”. "
                "**One idea per sentence.** Keep each sentence short and standalone. "
                "**No** long sentences with multiple clauses or comma chains. "
                "**Single numeric anchor only** when it helps: pick the **one** most relevant value for the question "
                "(e.g. drift %, pace, HR) — **do not** list multiple metrics or do a formal dump. "
                "Values must be **tool-grounded** (never invented). "
                "**No** generic coaching advice or encouragement unless the user explicitly asked for it. "
                "HARD BAN: “this indicates”, “this suggests”, “which indicates”, “which suggests”, "
                "“indicating”, “which means”, and explanation-style bridges. "
                "Do not start any sentence with the word **This**."
            ),
            avoid_repeating_metrics=avoid_metrics,
            allow_full_recap=asks_recap,
        )

    if turn_type == "follow_up":
        return ResponseDirective(
            turn_type=turn_type,
            target_length=(
                "HARD OUTPUT BOUNDARY: **at most 2 sentences** — strict limits, not guidelines. "
                "**Sentence 1:** direct answer only — when the ask is metric-related, include **one** key "
                "tool-backed number here in natural speech (e.g. “3.7% drift — moderate.” or “Drift was 3.7% — moderate.”). "
                "**Sentence 2 (optional):** one brief human interpretation only. "
                "**STOP** immediately after the final allowed sentence — never continue after sentence 2."
            ),
            tone_hint=(
                "Coach texting: direct and confident — conversational, but anchored by **one** concrete value when relevant."
            ),
            focus=(
                "**No** content beyond those 1-2 sentences — no trailing wrap-up, no extra takeaway. "
                "The response **must end** right after the final period of the last allowed sentence. "
                "**One idea per sentence.** Short standalone lines — **no** comma chains or stacked clauses in one sentence. "
                "**No** coaching advice, tips, or encouragement unless the user explicitly asked for that. "
                "**Do not** re-list or recap a block of metrics from earlier turns — only the **single** most relevant "
                "value for **this** question, woven into sentence 1 when it matters. "
                "HARD BAN: “this indicates”, “this suggests”, “which indicates”, “which suggests”, "
                "“indicating”, “which means”, and other explanation-style transitions. "
                "Do not start any sentence with the word **This**."
            ),
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

    base = (
        "## Response directive (current turn)\n"
        f"- Turn type: **{directive.turn_type}**\n"
        f"- Target length: {directive.target_length}\n"
        f"- Tone: {directive.tone_hint}\n"
        f"- Focus: {directive.focus}\n"
        f"- Avoid repeating metrics already shared unless asked: {avoid_line}\n"
        f"- Full recap requested by user: {recap_line}\n"
        "- Prior assistant messages are shared context. Do not re-explain unchanged points."
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

    if directive.turn_type == "follow_up":
        follow_hard = (
            "\n\n### Follow-up — HARD CONSTRAINTS (must obey)\n"
            "### Termination (hard STOP)\n"
            "- Sentence limits are **strict output boundaries**, not soft targets.\n"
            "- After you finish **sentence 1** (or **sentence 2** if you use it), **STOP** — end the assistant message there.\n"
            "- **Do not** add anything after the final allowed sentence: no extra explanation, summary, caveat, "
            "follow-up offer, encouragement, or coaching — **under any condition**.\n"
            "- **Do not** write a sentence 3. **Do not** continue the response after sentence 2.\n"
            "- The reply **must end immediately** after the final period (or question mark) of the last allowed sentence.\n"
            "### Structure\n"
            "- **Maximum 2 sentences** total. **Sentence 1:** direct answer **only** — open with value/judgment. "
            "**Sentence 2 (optional):** one brief human interpretation only.\n"
            "### Numeric anchor (when relevant)\n"
            "- If the follow-up is about a metric (drift, pace, HR, etc.), **sentence 1** should include **exactly one** "
            "key tool-backed value, woven in naturally — not a list or formal recap.\n"
            "- Prefer compact coach lines like “3.7% drift — moderate.” or “Drift was 3.7% — moderate.” "
            "(paraphrase formats; **do not** echo these examples verbatim unless the numbers match tools).\n"
            "- **Only** the **most relevant** number for **this** question; **no** extra metrics in the same reply.\n"
            "- **No** further ideas beyond these two sentences.\n"
            "- **No third sentence.** **No** bullet lists or paragraphs.\n"
            "- **One idea per sentence.** Keep each sentence short and standalone.\n"
            "- **No** long sentences with multiple clauses or comma chains — split or shorten instead.\n"
            "- **No** coaching advice, training tips, or generic encouragement unless the user **explicitly** asked for it.\n"
            "- **Do not** use: “this indicates”, “this suggests”, “which indicates”, “which suggests”, "
            "“indicating”, “which means”, or close variants.\n"
            "- **No** explanation-style transitions (“as a result”, “therefore”, “this means that”, “in other words”) — prefer **none**.\n"
            "- **Do not** start any sentence with the word **This**.\n"
            "- Desired flavor (paraphrase; **do not** quote or enumerate these in the reply): "
            "e.g. “3.7% drift — moderate.” then optional second sentence for plain interpretation."
        )
        return base + follow_hard

    if directive.turn_type == "drill_down":
        drill_hard = (
            "\n\n### Drill-down — HARD CONSTRAINTS (must obey)\n"
            "### Termination (hard STOP)\n"
            "- Sentence limits are **strict output boundaries**, not guidelines.\n"
            "- After **sentence 1** (or **sentence 2** if you use it), **STOP** — produce **nothing** further in this reply.\n"
            "- **Do not** continue after sentence 2 under **any** circumstance — no trailing explanation, recap, "
            "hedge, or coaching.\n"
            "- **No sentence 3.** The message **must terminate** right after the last allowed sentence ends.\n"
            "### Structure\n"
            "- **Maximum 2 sentences** total — **no third sentence ever**. "
            "**Sentence 1:** direct answer to the **why** **only**. **Sentence 2 (optional):** one short interpretation only.\n"
            "### Numeric anchor (when it helps)\n"
            "- When a **single** tool-backed number makes the “why” clearer, integrate **that one value** into "
            "**sentence 1** in natural coach language — **not** a metric dump or bullet list.\n"
            "- Pick **only** the value that best answers the question (e.g. drift %, threshold edge, pace, HR). "
            "**Do not** stack several numbers in one reply.\n"
            "- Stay conversational — no statistical/report tone.\n"
            "- **No** additional ideas beyond these two sentences.\n"
            "- **One idea per sentence.** Short standalone lines only.\n"
            "- **No** long sentences with multiple clauses or comma chains.\n"
            "- **No** generic coaching advice or encouragement unless the user **explicitly** asked for it.\n"
            "- **Do not** use: “this indicates”, “this suggests”, “which indicates”, “which suggests”, "
            "“indicating”, “which means”, or close variants.\n"
            "- **No** explanation-style transitions — no analyst chains (“which implies…”, “suggesting that…”).\n"
            "- **Do not** start any sentence with the word **This**.\n"
            "- Desired flavor (paraphrase; **do not** quote or enumerate these in the reply): "
            "e.g. “That’s yellow — you’re in the moderate drift band (~3.7%).” plus optional second short line."
        )
        return base + drill_hard

    return base


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
