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
    r"\b(?:tell me more about|"
    r"why|how come|explain|more detail|go deeper|break it down|walk me through|"
    r"in detail|elaborate|unpack|dig deeper|what does that mean)\b",
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
# Effort / contradiction cues → prefer question-first before prescribing (see investigation-first gate).
_EASY_SENTIMENT_RE = re.compile(
    r"\b(felt\s+(really\s+)?easy|too\s+easy|super\s+easy|pretty\s+easy|very\s+easy|"
    r"easy\s+day|piece\s+of\s+cake|like\s+a\s+breeze)\b",
    re.IGNORECASE,
)
_HARD_SENTIMENT_RE = re.compile(
    r"\b(felt\s+(really\s+)?hard|really\s+hard|so\s+hard|brutal|"
    r"destroyed\s+me|trashed\s+me|struggled\s+(badly|a\s+lot)|"
    r"felt\s+impossible|could\s+hardly)\b",
    re.IGNORECASE,
)
_INVESTIGATE_FIRST_CUE_RE = re.compile(
    r"\b(actually|i\s+meant|on\s+second\s+thought|wait[,!\s]|hold\s+on)\b|"
    r"(doesn'?t|does\s+not)\s+(match|add\s+up|make\s+sense)|"
    r"that\s+can'?t\s+be\s+right|doesn'?t\s+sound\s+right|"
    r"i'?m\s+confused|feels?\s+inconsistent|contradicts|"
    r"you\s+said\b.*\bbut\b",
    re.IGNORECASE,
)
_FACTUAL_SNAPSHOT_ONLY_RE = re.compile(
    r"^\s*(what('?s| is)|how\s+(much|many|long)|was\s+my|what\s+was\s+my|"
    r"what\s+pace|what'?s\s+drift|heart\s+rate|avg\s+hr|average\s+hr)\b",
    re.IGNORECASE,
)
# Experiential / reassurance → validate before explaining or prescribing (interaction_mode).
_EXPERIENTIAL_MODE_RE = re.compile(
    r"\b(is that|is it|was that)\s+(ok|okay|fine|normal|alright)\b|"
    r"\b(should i|do i need to)\s+worry\b|"
    r"\b(am i|are we)\s+(ok|okay|normal)\b|"
    r"\bworried (that|about)\b|"
    r"\b(nervous|anxious) about\b|"
    r"\bscared (that|about|i'?m)\b|"
    r"\b(feel|feeling|felt)\s+(really\s+)?(weird|off|wrong|sketchy)\b|"
    r"\bfelt\s+(really\s+)?(easy|hard)\b.*\?|"
    r"\?.*\bfelt\s+(really\s+)?(easy|hard)\b",
    re.IGNORECASE,
)
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
    coaching_depth_requested: bool = False
    investigate_first: bool = False
    """True → directive enforces question-first, no prescriptions this turn."""
    interaction_mode: str = "clear_coaching"
    """
    Top-level response shape for this turn:
    minimal | factual | ambiguous | experiential | clear_coaching
    """

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def derive_interaction_mode(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    turn_type: str,
    investigate_first: bool,
) -> str:
    """
    Single high-level mode switch (gates explain / validate / question / factual brevity).

    Order: acknowledgment → ambiguous (investigate) → experiential → factual → default.
    ``conversation_history`` reserved for future cues; unused for now.
    """
    _ = conversation_history
    if turn_type == "acknowledgment":
        return "minimal"
    if investigate_first:
        return "ambiguous"

    raw = (user_message or "").strip()
    msg_low = raw.lower()
    if not msg_low:
        return "clear_coaching"

    if _EXPERIENTIAL_MODE_RE.search(msg_low):
        return "experiential"

    if (
        len(raw) <= 120
        and _FACTUAL_SNAPSHOT_ONLY_RE.search(msg_low)
        and not _INVESTIGATE_FIRST_CUE_RE.search(msg_low)
    ):
        return "factual"

    return "clear_coaching"


def _should_investigate_first(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    turn_type: str,
    coaching_depth_requested: bool,
) -> bool:
    """
    Likely ambiguity or contradiction — prefer one clarifying question before advising.

    Conservative: off for acknowledgments, clarifications, explicit depth asks, and
    short factual snapshot questions without tension cues.
    """
    if coaching_depth_requested or turn_type in ("acknowledgment", "clarification"):
        return False
    cur = (user_message or "").strip()
    if len(cur) < 6:
        return False

    cur_low = cur.lower()
    if (
        len(cur) <= 120
        and _FACTUAL_SNAPSHOT_ONLY_RE.search(cur_low)
        and not _INVESTIGATE_FIRST_CUE_RE.search(cur_low)
    ):
        return False

    prior_user = " ".join(
        (m.get("content") or "").strip()
        for m in conversation_history
        if (m.get("role") or "").strip() == "user"
    )

    if prior_user:
        if _EASY_SENTIMENT_RE.search(prior_user) and _HARD_SENTIMENT_RE.search(cur_low):
            return True
        if _HARD_SENTIMENT_RE.search(prior_user) and _EASY_SENTIMENT_RE.search(cur_low):
            return True

    if turn_type in ("follow_up", "drill_down", "new_topic"):
        if _INVESTIGATE_FIRST_CUE_RE.search(cur_low):
            return True

    return False


def _user_requests_coaching_depth(user_message: str, turn_type: str) -> bool:
    """True when the latest user message asks for deeper explanation (opening or mid-thread)."""
    if turn_type in ("acknowledgment", "clarification"):
        return False
    msg = (user_message or "").strip()
    return bool(msg and _DRILL_DOWN_RE.search(msg))


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
    conversation_history: List[Dict[str, str]],
) -> ResponseDirective:
    """Create a compact per-turn response directive."""
    depth_ask = _user_requests_coaching_depth(user_message, turn_type)
    investigate = _should_investigate_first(
        user_message, conversation_history, turn_type, depth_ask
    )
    mode = derive_interaction_mode(
        user_message, conversation_history, turn_type, investigate
    )
    intent = infer_intent(user_message)
    addon = _intent_addon(intent)
    asks_recap = bool(_RECAP_RE.search((user_message or "").lower()))
    avoid_metrics = [] if asks_recap else list(state.metrics_already_shared)

    if turn_type == "opening":
        target_len = "short recap allowed; keep tight and scannable"
        focus_open = "answer the initial ask with tool-grounded context"
        if intent == "split_detail":
            target_len = (
                "Resolve **activity_id**, call **get_run_splits**. **Short list or compact table** of split rows is OK; "
                "then **2–5 coaching sentences** as needed. Grounded **split-to-split** comparisons from returned rows "
                "are allowed. **Do not** repeat session-level recap stats unless the user asked for a recap."
            )
            focus_open = (
                "Coach-like **read**, not row dictation: **warmup / outlier** first miles, **pacing-driven HR** changes, "
                "**steadier later miles** vs a scary headline drift, what actually mattered. "
                "**get_run_summary** only if session KPIs or facts are still missing. No process narration."
            )
        elif intent == "run_analysis":
            if depth_ask:
                target_len = (
                    "**Depth request:** OUTPUT STRUCTURE — Insight + Facts depth mode for `run_summary` + card: "
                    "usually **up to 5** insight sentences in `content`; **up to 2** sentences may carry *why* / reframing; "
                    "**≤2** tool-verbatim numeric anchors total (**prefer HR drift** for one); optional last insight sentence = "
                    "**qualitative** guidance only; **optional** one short engagement question after (OUTPUT STRUCTURE **Optional close**). **No** full stat lineup — card holds metrics."
                )
            else:
                target_len = (
                    "Usually **2–3 insight sentences** in `content`; **flexible** shape — "
                    "vary opener and flow (not fixed verdict→number→advice); **≤1** numeric anchor in `content` when it helps "
                    "(**prefer HR drift** when it is the main signal). **Optional** one short engagement question after "
                    "(OUTPUT STRUCTURE **Optional close**) when it adds value. Conversational, not report-like — see OUTPUT STRUCTURE — Insight + Facts."
                )
        elif intent == "training_trend":
            if depth_ask:
                target_len = (
                    "**Depth request:** Progress check-in depth mode: usually **up to 5** body sentences; keep **verdict → constraint → action** "
                    "(constraint may use **2** short sentences); **~6–12 words** per line when possible; **spoken** coach; "
                    "**prefer zero numbers**, **≤2** tool-verbatim numerals in the **whole** reply if essential; **optional** one short engagement question after (OUTPUT STRUCTURE **Optional close**). See OUTPUT STRUCTURE."
                )
            else:
                target_len = (
                    "Usually **2–3 body sentences**, **preferred order**: verdict → constraint → action; **~6–10 words** per sentence when "
                    "possible; **spoken** coach (mid/post run). **Prefer zero numbers**; **≤1** if essential; **optional** one short engagement question after when it adds value (OUTPUT STRUCTURE **Optional close**). See OUTPUT STRUCTURE."
                )
        return ResponseDirective(
            turn_type=turn_type,
            intent=intent,
            target_length=target_len,
            tone_hint="coach-like, direct, grounded",
            focus=focus_open,
            avoid_repeating_metrics=[],
            allow_full_recap=True,
            narration_mode=addon["narration_mode"],
            tool_strategy=addon["tool_strategy"],
            natural_style_notes=addon["natural_style_notes"],
            coaching_depth_requested=depth_ask,
            investigate_first=investigate,
            interaction_mode=mode,
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
            coaching_depth_requested=depth_ask,
            investigate_first=investigate,
            interaction_mode=mode,
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
            coaching_depth_requested=depth_ask,
            investigate_first=investigate,
            interaction_mode=mode,
        )

    if turn_type == "drill_down":
        target_len_dd = (
            "2-4 sentences. Start with a direct answer, then one compact explanation with 1-2 tool-grounded "
            "values only if they materially help. Keep language plain and human."
        )
        focus_dd = (
            "Answer the why directly, avoid metric dumping, and use only tool-grounded numbers. "
            "Include one practical coaching interpretation when useful."
        )
        if intent == "split_detail":
            target_len_dd = (
                "**get_run_splits**; **short list or small table** + **2–5 sentences** is fine. "
                "Simple **derived** comparisons across rows when grounded. **Do not** restate session-level distance, "
                "duration, avg pace, session HR, early/late/peak HR, or drift % from a prior turn unless user asked recap."
            )
            focus_dd = (
                "Interpret like a coach: **warmup/outlier** laps, **pace vs HR** story, **late fade vs steady middle**. "
                "Say whether the pattern was **actually a problem** or mostly **artifact**. Lap data from tool only — "
                "no session recap re-dump."
            )
        elif intent == "run_analysis":
            if depth_ask:
                target_len_dd = (
                    "If **run_summary** with card: OUTPUT STRUCTURE depth mode — usually **up to 5** insight sentences in `content`, "
                    "**≤2** anchors total, **up to 2** sentences for *why* if needed; **optional** one short engagement question after; **no** full stat dump. "
                    "Else: 2-4 sentences, plain and human."
                )
                focus_dd = (
                    "Structured run recap: **flexible** Insight + Facts — **≤2** anchors total, **prefer HR drift** when it is the main signal; "
                    "vary flow vs prior turns. Otherwise answer directly."
                )
            else:
                target_len_dd = (
                    "If reply is **run_summary** with card: usually **2–3 insight sentences** in `content` only (Insight + Facts); "
                    "**optional** one short engagement question after (OUTPUT STRUCTURE **Optional close**). Else: 2-4 sentences, plain and human."
                )
                focus_dd = (
                    "For structured run recap: **flexible** shape, **≤1** anchor in `content`, **prefer HR drift** when it is the main signal. "
                    "Otherwise answer the drill-down directly."
                )
        elif intent == "training_trend":
            if depth_ask:
                target_len_dd = (
                    "Progress/readiness + depth: usually **up to 5** body sentences, OUTPUT STRUCTURE Progress check-in depth mode; "
                    "verdict→constraint→action (constraint may be **2** sentences); **≤2** numerals in whole reply if needed; **optional** one short engagement question after. "
                    "Else: 2-4 sentences."
                )
                focus_dd = (
                    "Spoken coach rhythm; **no** corporate phrasing; clear athletic constraint + action. "
                    "Depth allows a bit more room — still **no** metric stacking in one sentence."
                )
            else:
                target_len_dd = (
                    "Progress/readiness: usually **2–3 body sentences**, verdict→constraint→action, **~6–10 words** each when possible; "
                    "**optional** one short engagement question after. **Prefer no numbers**. Else if not a trend ask: 2-4 sentences."
                )
                focus_dd = "No corporate (*room for improvement*, *steady progress*); athletic constraint line + clear action."
        return ResponseDirective(
            turn_type=turn_type,
            intent=intent,
            target_length=target_len_dd,
            tone_hint="Tight and focused, but conversational and warm.",
            focus=focus_dd,
            avoid_repeating_metrics=avoid_metrics,
            allow_full_recap=asks_recap,
            narration_mode=addon["narration_mode"],
            tool_strategy=addon["tool_strategy"],
            natural_style_notes=addon["natural_style_notes"],
            coaching_depth_requested=depth_ask,
            investigate_first=investigate,
            interaction_mode=mode,
        )

    if turn_type == "follow_up":
        target_len_fu = (
            "2-4 sentences max. Lead with direct answer, then add one concise interpretation. "
            "Use at most 1-2 key tool-backed values when relevant."
        )
        focus_fu = (
            "Answer the follow-up directly and avoid repeating prior full metric blocks. "
            "Use the smallest set of numbers needed, grounded in tool outputs, then stop."
        )
        if intent == "split_detail":
            target_len_fu = (
                "**get_run_splits**; **list/table + 2–4 (or 2–5) sentences**; grounded **split-to-split** deltas OK. "
                "**Do not** repeat session-level stats or full drift story you already gave unless they ask recap."
            )
            focus_fu = (
                "Real **coaching read** on the lap pattern — not only re-quoting rows. Flag **outliers/warmup**, "
                "**pacing-driven HR**, **steadier miles**; skip **get_run_summary** aggregates already covered."
            )
        elif intent == "run_analysis":
            if depth_ask:
                target_len_fu = (
                    "If **run_summary** with card: depth mode — usually **up to 5** insight sentences, **≤2** anchors, **optional** one short engagement question after. "
                    "Else: 2-4 sentences max."
                )
                focus_fu = (
                    "Structured run recap: Insight + Facts depth mode — **flexible** flow, **≤2** anchors; **no** stat dump. "
                    "Otherwise: smallest tool-backed set, then stop."
                )
            else:
                target_len_fu = (
                    "If **run_summary** with card: usually **2–3 insight sentences** in `content` (Insight + Facts); **optional** one short engagement question after. "
                    "Else: 2-4 sentences max."
                )
                focus_fu = (
                    "Structured run recap: same Insight + Facts caps as opening — **flexible** shape; **≤1** anchor; "
                    "**prefer drift** when it is the main signal. Otherwise: smallest set of tool numbers, then stop."
                )
        elif intent == "training_trend":
            if depth_ask:
                target_len_fu = (
                    "Progress/readiness + depth: usually **up to 5** body sentences (Progress check-in depth mode); **≤2** numerals if needed; **optional** one short engagement question after. "
                    "Else: 2-4 sentences max."
                )
                focus_fu = "Keep verdict→constraint→action; spoken rhythm; one clear action line."
            else:
                target_len_fu = (
                    "Progress/readiness: usually **2–3 body sentences**, verdict→constraint→action, **~6–10 words**; **optional** one short engagement question after. "
                    "**Prefer no numbers**. Else: 2-4 sentences max."
                )
                focus_fu = "Spoken not written; short clauses; third line = one clear coaching action."
        return ResponseDirective(
            turn_type=turn_type,
            intent=intent,
            target_length=target_len_fu,
            tone_hint="Coach texting: direct, natural, and grounded.",
            focus=focus_fu,
            avoid_repeating_metrics=avoid_metrics,
            allow_full_recap=asks_recap,
            narration_mode=addon["narration_mode"],
            tool_strategy=addon["tool_strategy"],
            natural_style_notes=addon["natural_style_notes"],
            coaching_depth_requested=depth_ask,
            investigate_first=investigate,
            interaction_mode=mode,
        )

    # new_topic fallback
    target_len_nt = "2-4 sentences by default; expand only if asked"
    focus_nt = "address the new topic directly"
    if intent == "split_detail":
        target_len_nt = (
            "**get_run_splits** after **activity_id**; **short list/table + 2–5 sentences**; grounded comparisons from rows. "
            "**Do not** layer in session recap numbers unless the ask is recap."
        )
        focus_nt = (
            "**Coach interpretation**: warmup/outlier splits, pace–HR linkage, steadier segments vs headline drift. "
            "**get_run_summary** only if session context is still needed."
        )
    elif intent == "run_analysis":
        if depth_ask:
            target_len_nt = (
                "If **run_summary** with card: depth mode — usually **up to 5** insight sentences, **≤2** anchors; **optional** one short engagement question after. "
                "Else: 2-4 sentences by default; expand only if asked."
            )
            focus_nt = "Run recap with card: **flexible** Insight + Facts, **≤2** anchors; **no** stat dump."
        else:
            target_len_nt = (
                "If **run_summary** with card: usually **2–3 insight sentences** in `content` (Insight + Facts); **optional** one short engagement question after. "
                "Else: 2-4 sentences by default; expand only if asked."
            )
            focus_nt = "Run recap with card: **flexible** Insight + Facts, **≤1** anchor; else address the topic directly."
    elif intent == "training_trend":
        if depth_ask:
            target_len_nt = (
                "Progress/readiness + depth: usually **up to 5** body sentences (Progress check-in depth mode), **≤2** numerals if needed; **optional** one short engagement question after. "
                "Else: 2-4 sentences by default; expand only if asked."
            )
            focus_nt = "Gold-standard shape with a bit more room: verdict → constraint (may be 2 lines) → clear action."
        else:
            target_len_nt = (
                "Progress/readiness: usually **2–3 body sentences**, verdict→constraint→action, **~6–10 words**, **prefer no numbers**; **optional** one short engagement question after. "
                "Else: 2-4 sentences by default; expand only if asked."
            )
            focus_nt = "Gold-standard shape: good progress → controlled but not fully consistent → keep it steady / move forward."
    return ResponseDirective(
        turn_type="new_topic",
        intent=intent,
        target_length=target_len_nt,
        tone_hint="coach-like and conversational",
        focus=focus_nt,
        avoid_repeating_metrics=[] if asks_recap else avoid_metrics,
        allow_full_recap=asks_recap,
        narration_mode=addon["narration_mode"],
        tool_strategy=addon["tool_strategy"],
        natural_style_notes=addon["natural_style_notes"],
        coaching_depth_requested=depth_ask,
        investigate_first=investigate,
        interaction_mode=mode,
    )


def _interaction_mode_subsection(directive: ResponseDirective) -> str:
    """Hard prompt block for the derived interaction mode (acknowledgment: none)."""
    if directive.turn_type == "acknowledgment":
        return ""
    mode = directive.interaction_mode
    if mode == "ambiguous":
        return (
            "\n\n### Interaction mode — ambiguous (mandatory)\n"
            "- Ambiguity or contradiction wins over default coaching flow. "
            "Follow **### Investigation-first gate** below as the executable contract for this mode.\n"
        )
    if mode == "experiential":
        depth_cap = (
            "\n- **Coaching depth requested: yes** — cap at **4** short sentences total; you may add **one** short *why* beat "
            "**only** if they explicitly asked to explain more; still **no** prescriptive training plan unless they explicitly "
            "asked what to do."
            if directive.coaching_depth_requested
            else ""
        )
        return (
            "\n\n### Interaction mode — experiential (mandatory; overrides conflicting Target length / Focus above)\n"
            "- **Experiential turns only:** sound like **texting a coach**, not a lesson. This block **overrides** default "
            "coaching / explanatory habits from OUTPUT STRUCTURE, intent add-ons, and long **Insight + Facts** patterns for "
            "**this** reply.\n"
            "- **Do not** give general training **explanations**, **causes**, physiology, or **advice** (what to do next, "
            "plans, workouts) **unless** the user **explicitly** asked what to do / what they should change / how to fix it.\n"
            "- **Avoid** coach-explanation templates: “this can happen when…”, “this indicates that…”, “often that means…”, "
            "“from a training perspective…”, “what’s going on is…”, “which suggests…”.\n"
            "- **Avoid prescriptive softeners:** “consider…”, “make sure to…”, “you should…”, “try to…”, “it’s important to…”, "
            "“I’d recommend…” — same as hard prescriptions here unless they explicitly asked for guidance.\n"
            "- **Default shape:** (1) **One sentence** — validation / normalization in **plain** language. "
            "(2) **One sentence** — a **simple** read of what it means for them in **everyday** words (**no** deep mechanism, "
            "**no** data tour). (3) **Optional:** **one** short follow-up question (a **fork** is OK per **Questions — form and filler**) "
            "if it genuinely helps; otherwise **stop**.\n"
            "- **Length:** usually **≤2–3 short sentences** total; **≤2** when you can stay clear. **No** paragraphs or stacked "
            "“because / which means” chains.\n"
            + depth_cap
            + "- **Do not** open sentence 1 with distance, pace, HR, time, or drift numbers. If one tool-backed number helps answer "
            "“is it ok / normal?”, keep it to **at most one** plain mention in sentence 2 — **not** a stat recap.\n"
            + "- If uncertainty remains after those sentences, **one** forked clarifier is OK; otherwise skip.\n"
        )
    if mode == "factual":
        return (
            "\n\n### Interaction mode — factual (mandatory)\n"
            "- Answer **only** what they asked. Lead with the **direct** tool-backed fact.\n"
            "- **No** extended coaching interpretation, training prescription, or “here’s what to do next” unless they explicitly asked for that.\n"
            "- **≤2–3 short sentences** by default; skip optional engagement questions unless they clear an ambiguity.\n"
        )
    return ""


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
    depth_line = "yes" if directive.coaching_depth_requested else "no"
    inv_line = "yes" if directive.investigate_first else "no"

    mode_line = directive.interaction_mode.replace("_", " ")

    base = (
        "## Response directive (current turn)\n"
        f"- **Interaction mode (read this first):** **{directive.interaction_mode}** ({mode_line})\n"
        f"- Turn type: **{directive.turn_type}**\n"
        f"- Intent: **{directive.intent}**\n"
        f"- Coaching depth requested: **{depth_line}**\n"
        f"- Investigation-first (question before advice): **{inv_line}**\n"
        f"- Target length: {directive.target_length}\n"
        f"- Tone: {directive.tone_hint}\n"
        f"- Focus: {directive.focus}\n"
        f"- Narration mode: {directive.narration_mode}\n"
        f"- Tool strategy: {directive.tool_strategy}\n"
        f"- Avoid repeating metrics already shared unless asked: {avoid_line}\n"
        f"- Full recap requested by user: {recap_line}\n"
        "- Prior assistant messages are shared context. Do not re-explain unchanged points."
    )
    base += _interaction_mode_subsection(directive)
    if directive.investigate_first and directive.turn_type != "acknowledgment":
        base += (
            "\n\n### Investigation-first gate (mandatory this turn; overrides conflicting length/focus above)\n"
            "- Planner flagged **likely ambiguity or contradiction** (effort wording shifted vs earlier user text, "
            "or explicit hedging / mismatch cues).\n"
            "- **Do not** give training prescriptions in this reply: **no** “next time…”, “try to…”, "
            "“I’d aim for…”, “you should…”, progression or workout assignment — **unless** clearly required for "
            "**safety** (e.g. sharp pain → stop / see a professional).\n"
            "- **Do** end with **exactly one** short, specific **clarifying question** whose answer would change your guidance. "
            "Prefer a **concrete fork** (A vs B, or A / B / other) when honestly possible — not a vague “tell me more.”\n"
            "- **Do not** meta-justify the question (no “so I can understand…”, “this will help me…”, “I’m asking because…”). Ask directly.\n"
            "- **Hard stop — no causal explanation before the question:** In all user-visible text **before** the final "
            "clarifying question, **do not** give **causal** stories, **why** tours, **reconciliation with tool facts** "
            "(pace/HR/drift narratives, “what likely happened”), or **mechanistic interpretation** — even if tools ran. "
            "You may state the **tension in plain words** in **≤2** short sentences (acknowledgment only). The **only** "
            "analytic move this turn is the **question** itself. **Safety** (e.g. sharp pain → stop / professional): "
            "**one** short sentence, **no** diagnosis.\n"
            "- **No metrics before the question:** In all user-visible text **before** the final clarifying question, **do not** "
            "restate, interpret, or reference **any** run metrics (distance, duration, pace, HR, drift %, zones, splits) — "
            "**including a single number** offered as “quick context.” Tools may run internally; **do not** surface numbers "
            "in `content` until a **later** turn after they answer. **Safety** wording: prefer plain language; avoid numbers if possible.\n"
            "- **Do not** ask multiple stacked questions. **Do not** open with a full run recap to “prove” the contradiction; "
            "tools may still ground you internally, but the **user-visible** shape stays **question-first**.\n"
            "- After the user answers, a **later** turn may interpret and advise normally."
        )
    inv_addon = directive.investigate_first and directive.turn_type != "acknowledgment"
    if directive.natural_style_notes or inv_addon:
        if inv_addon:
            base += (
                "\n\n### Human coach style addon\n"
                "- Keep the reply sounding like one coach talking to one athlete, not a report or dashboard.\n"
                "- **Investigation-first this turn:** Do **not** apply intent `natural_style_notes` or generic OUTPUT STRUCTURE "
                "habits that push metrics, multi-sentence run insight in `content`, HR drift anchors, or split tables **before** "
                "the final clarifying question — defer those to the **next** turn after the user answers. This turn’s "
                "user-visible shape follows **### Investigation-first gate** only.\n"
            )
        else:
            natural_lines = "\n".join(
                [f"- {line}" for line in directive.natural_style_notes]
            )
            base += (
                "\n\n### Human coach style addon\n"
                "- Keep the reply sounding like one coach talking to one athlete, not a report or dashboard.\n"
                "- Stay tool-grounded for numbers; follow OUTPUT STRUCTURE + STYLE in the base prompt "
                "(run_summary + card: usually **2–3** insight sentences in content by default (depth: usually up to **5** with **≤2** anchors); "
                "**optional** one short engagement question after when it adds value (**Optional close**); "
                "**flexible** shape; **≤1** anchor by default (**≤2** with depth); **prefer HR drift** when it is the main signal; "
                "conversational not report-like; card carries metrics; "
                "progress/readiness (training_trend): usually **2–3** body sentences by default (depth: usually up to **5**), **verdict→constraint→action**, "
                "**~6–10 words** when possible, **prefer no numbers**, Progress check-in, plus same optional engagement question rule; "
                "split_detail: **short table/list + human coaching read**, grounded derived comparisons from split rows allowed; "
                "other topics: woven prose where appropriate).\n"
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
            "mile over mile",
            "mile-by-mile",
            "mile by mile",
            "per mile",
            "each mile",
            "every mile",
            "split",
            "splits",
            "lap by lap",
            "by mile",
        )
    ):
        return "split_detail"
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
            "create a plan",
            "build a plan",
            "training plan",
            "make me a plan",
            "help me train",
            "plan for",
        )
    ):
        return "plan_creation"
    if any(
        k in t
        for k in (
            "how was my run",
            "how's my run",
            "hows my run",
            "how is my run",
            "how did my run",
            "how went my run",
            "analyze my run",
            "how did today go",
            "how was today",
            "how did today",
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
        "narration_mode": "woven_coach",
        "tool_strategy": "Use the minimum required tools, then answer directly from results.",
        "natural_style_notes": [
            "Default to short, scannable prose; lead with takeaway; bold key numbers when it helps — not labeled report sections or stat-bullet dumps unless the user asks for a list or breakdown.",
            "For run-level recap: lead with a clear coaching read, then one concise explanation; let structured run summary carry detailed metrics.",
            "Do not narrate your process (no 'let me pull' / 'now let me calculate').",
            "If tool data is thin, say so in one honest line.",
        ],
    }
    profiles: Dict[str, Dict[str, Any]] = {
        "race_projection": {
            "narration_mode": "scenario_coach",
            "tool_strategy": (
                "For marathon prediction asks, prioritize get_marathon_projection as the primary source. "
                "Include only a brief trend context line unless the user explicitly asks for a deeper trend breakdown."
            ),
            "natural_style_notes": [
                "Sound like a planning coach: confident but honest about uncertainty.",
                "Weave conservative / on-track / stretch scenarios into flowing prose or a very short list — tool numbers only.",
                "Keep trend context short so the projection stays central.",
                "Close with one practical next-step sentence tied to the projection window.",
            ],
        },
        "volume_query": {
            "narration_mode": "numbers_then_context",
            "tool_strategy": (
                "Use aggregate_runs_in_range for totals and weekly_summaries; keep the window explicit and consistent."
            ),
            "natural_style_notes": [
                "State the headline total in prose with the exact tool values bolded.",
                "Prefer weaving a few weeks into a sentence; use a short bullet list only if many weeks or the user asked for a list.",
            ],
        },
        "training_trend": {
            "narration_mode": "coach_story",
            "tool_strategy": (
                "Use weekly insight / training KPI tools first; decide verdict + constraint + action in plain athletic language — then say it in three short lines, not a stat readout."
            ),
            "natural_style_notes": [
                "**Preferred order:** verdict → constraint → action (spoken, athletic wording; avoid review-speak such as *room for improvement* / *steady progress*).",
                "**~6–10 words** per sentence when possible; **spoken** rhythm, not memo prose; one idea per sentence — avoid metric + band + % + comparison in one line.",
                "**Default: no numbers**; **≤1** only if essential — never % + deltas + bands together; ban *showing*, *indicating*, *in the yellow zone*, *over last week*.",
                "**Gold standard** (adapt claims to tools): *You're making good progress.* / *Your effort is more controlled, but not fully consistent yet.* / *Keep it steady — that's what will move you forward.*",
            ],
        },
        "split_detail": {
            "narration_mode": "woven_coach",
            "tool_strategy": (
                "After **activity_id** is known, call **get_run_splits** for per-lap HR and pace. "
                "Use **get_run_summary** only if session KPIs or facts are still missing for the same run."
            ),
            "natural_style_notes": [
                "Quote split row **display** fields (**avg_heart_rate_display**, **avg_pace_display**, **segment_label**) **exactly**; respect **scope**.",
                "Simple **split-to-split** comparisons and deltas are allowed when **grounded in returned rows** — not from memory.",
                "Call out **warmup** or **outlier** early miles when they **skew** a simple whole-run drift read.",
                "If a **run recap** already happened in-thread, **do not** repeat session-level stats/drift — add **lap narrative** and coaching read only.",
            ],
        },
        "run_analysis": {
            "narration_mode": "run_recap",
            "tool_strategy": (
                "Resolve run identity first, then use run summary payload for facts and interpretation."
            ),
            "natural_style_notes": [
                "Insight + Facts: `content` = coaching insight only — usually **2–3 insight sentences**; **optional** one short engagement question after (OUTPUT STRUCTURE **Optional close**) when it adds value; card below has metrics.",
                "Vary structure from reply to reply — avoid the same verdict→drift%→advice pattern every time. **≤1** numeric anchor in `content` by default (**prefer HR drift** when it is the main signal); no filler openers (*today*, *you completed*, *this run was*).",
                "No report tone (short clauses, not *which indicates… for a controlled pace*). Do not paste hr_drift_summary_display into content.",
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
        "plan_creation": {
            "narration_mode": "coach_intake",
            "tool_strategy": (
                "Use deterministic plan-intake tools: update_plan_intake each turn, then "
                "generate_training_plan only after explicit confirmation."
            ),
            "natural_style_notes": [
                "Ask one clear intake question at a time, driven by update_plan_intake missing_required; "
                "half marathon and marathon only—no experience quiz or plan-length-in-weeks question.",
                "When they name a full marathon event, set Marathon + race_name in update_plan_intake the same turn; "
                "accept spoken training-day ranges (e.g. Monday through Saturday) via the tool—no need to force abbreviations.",
                "Summarize captured details before asking for final confirmation.",
                "After generation, lead with a concise what-to-expect-this-week overview.",
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
    if "bpm" in text_l or "heart rate" in text_l:
        metrics.add("heart_rate")
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
