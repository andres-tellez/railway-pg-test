"""
Mobile coach agent loop: OpenAI tools with a bounded max iteration count.

Tool definitions are loaded from the coach_tools database table.
If `search_runs`, `aggregate_runs_in_range`, `get_training_kpis`, or
`get_marathon_projection` is missing from the DB
(enabled list), built-in definitions are injected so tools still work without re-seeding.

Max loops default 8; override with env SMARTCOACH_AGENT_MAX_LOOPS (clamped 2–15).

Opening "how was my run?"–style turns can use ``run_recap_fastpath`` (single
``chat_completion`` without tools) when ``SMARTCOACH_RUN_RECAP_FASTPATH`` is enabled.
Gating lives in ``run_recap_policy`` (first user turn + phrase match); metadata includes
``run_recap_fastpath_gate``. Empty first completion may trigger one retry
(``SMARTCOACH_RUN_RECAP_FASTPATH_RETRY``) before the full tool loop.
The LLM appendix uses **facts-only** compact JSON by default
(``SMARTCOACH_RUN_RECAP_PREFETCH_SLIM``); full ``get_run_summary`` is still returned for the card.

Split-detail turns (intent ``split_detail``) can use ``prefetch_split_detail`` +
``system_appendix_for_split_prefetch`` (single ``chat_completion`` without tools)
when ``SMARTCOACH_SPLIT_DETAIL_FASTPATH`` is enabled. See ``docs/smartcoach_mobile_coach/README.md``.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from sqlalchemy.orm import Session
from sqlalchemy import text

from src.db.dao.user_profile_dao import get_user_profile
from src.services.heart_rate.hrmax_resolution_service import HRMaxResolutionService
from src.services.security.external_apis.openai_service import get_openai_service
from src.smartcoach_mobile_coach.agent_tools import execute_tool
from src.smartcoach_mobile_coach.dialogue_manager import (
    ResponseDirective,
    classify_turn,
    extract_conversation_state,
    plan_response,
    response_directive_section,
)
from src.smartcoach_mobile_coach.run_recap_fastpath import (
    RUN_RECAP_FASTPATH_RETRY_APPENDIX,
    prefetch_opening_anchor_run_recap,
    prefetch_split_detail,
    run_recap_fastpath_retry_on_empty_enabled,
    system_appendix_for_prefetch,
    system_appendix_for_split_prefetch,
    wants_split_detail_fastpath,
)
from src.smartcoach_mobile_coach.run_recap_policy import decide_run_recap_fastpath
from src.smartcoach_mobile_coach.thread_derived_context import (
    DerivedThreadCoachContext,
    derive_thread_coach_context,
)
from src.utils.hr_zone_constants import (
    ALLOWED_METRICS,
    COACHING_LEVEL_DEFAULTS,
    VERBOSITY_RULES,
    hr_calibration_reason_user_hint,
)

logger = logging.getLogger("smartcoach_mobile_coach")


def _max_agent_loops() -> int:
    """Cap on model turns (tool rounds + final reply). Env: SMARTCOACH_AGENT_MAX_LOOPS, default 8."""
    raw = os.getenv("SMARTCOACH_AGENT_MAX_LOOPS", "8").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 8
    return max(2, min(n, 15))


# Kept in sync with scripts/setup_coach_tools.py `search_runs` (for DBs not yet re-seeded).
_SEARCH_RUNS_OPENAI_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search_runs",
        "description": (
            "Search the user's run history using optional filters (distance, name text, date range), "
            "ordered newest-first, capped to a small limit (sample only). "
            "Use for discovery — e.g. 'when was my last marathon?', 'last race'. "
            "Never use this for total miles or total run count over a period; use aggregate_runs_in_range. "
            "For marathon distance use min_distance_m ~42000. "
            "For race questions, after matches return, chain get_run_summary(top activity_id) in the same "
            "turn so you can report time, pace, and comparison — search_runs alone has no finish time/pace."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "min_distance_m": {
                    "type": "number",
                    "description": "Optional minimum distance in meters.",
                },
                "max_distance_m": {
                    "type": "number",
                    "description": "Optional maximum distance in meters.",
                },
                "name_query": {
                    "type": "string",
                    "description": "Optional case-insensitive text match on run title.",
                },
                "start_date_from": {
                    "type": "string",
                    "description": (
                        "Optional inclusive start (YYYY-MM-DD), activity-local calendar per run."
                    ),
                },
                "start_date_to": {
                    "type": "string",
                    "description": (
                        "Optional inclusive end (YYYY-MM-DD), activity-local calendar per run."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Max matches to return (default 5, max 20).",
                },
            },
        },
    },
}

# Kept in sync with scripts/setup_coach_tools.py `aggregate_runs_in_range`.
_AGGREGATE_RUNS_IN_RANGE_OPENAI_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "aggregate_runs_in_range",
        "description": (
            "Return full run count and total distance for all Run activities in an inclusive "
            "date range (YYYY-MM-DD). Uses each activity's local calendar day (Strava timezone, "
            "same as find_runs_by_date). Use for total miles in the last N days, how many runs "
            "this month, or volume between two dates. Also returns weekly_summaries (ISO week "
            "breakdown) from the same filtered activities set for all-runs weekly mileage. "
            "Optional filters match search_runs. "
            "Do not use search_runs for totals — it returns a capped sample. "
            "Quote run_count and total_mi_display exactly from the tool result."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "start_date_from": {
                    "type": "string",
                    "description": "Inclusive start (YYYY-MM-DD), activity-local calendar.",
                },
                "start_date_to": {
                    "type": "string",
                    "description": "Inclusive end (YYYY-MM-DD), activity-local calendar.",
                },
                "min_distance_m": {
                    "type": "number",
                    "description": "Optional minimum distance in meters.",
                },
                "max_distance_m": {
                    "type": "number",
                    "description": "Optional maximum distance in meters.",
                },
                "name_query": {
                    "type": "string",
                    "description": "Optional case-insensitive substring match on run title.",
                },
            },
            "required": ["start_date_from", "start_date_to"],
        },
    },
}

# Kept in sync with scripts/setup_coach_tools.py `get_training_kpis`.
_GET_TRAINING_KPIS_OPENAI_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_training_kpis",
        "description": (
            "Training KPI trends over recent ISO weeks (Mon-Sun) from v_easy_runs (KPI/easy-run scope): "
            "HR drift, Z2 pace/adherence, and long-run readiness context. "
            "Not the source of truth for all-runs weekly mileage totals; use aggregate_runs_in_range "
            "for inclusive weekly/all-runs volume. If date range params are omitted, weeks is rolling from now()."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "weeks": {
                    "type": "integer",
                    "description": (
                        "Optional rolling lookback in weeks when explicit date range is not provided."
                    ),
                },
                "start_date_from": {
                    "type": "string",
                    "description": "Optional inclusive start date (YYYY-MM-DD), activity-local calendar.",
                },
                "start_date_to": {
                    "type": "string",
                    "description": "Optional inclusive end date (YYYY-MM-DD), activity-local calendar.",
                },
            },
        },
    },
}

# Kept in sync with scripts/setup_coach_tools.py `get_marathon_projection`.
_GET_MARATHON_PROJECTION_OPENAI_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_marathon_projection",
        "description": (
            "Deterministic marathon finish-time projection from recent run signals. "
            "Returns scenario-based race pace and projected finish times (conservative/on_track/stretch), "
            "with explicit assumptions and data quality details. Use this for 'predict my next marathon time' "
            "or marathon projection asks. Do not invent projection numbers outside this tool."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target_race_date": {
                    "type": "string",
                    "description": "Optional race date (YYYY-MM-DD) to compute weeks until race.",
                },
                "goal_time_hhmmss": {
                    "type": "string",
                    "description": "Optional goal marathon time in HH:MM:SS for scenario comparison.",
                },
                "lookback_days": {
                    "type": "integer",
                    "description": "Optional projection lookback window in days (default 84).",
                },
            },
        },
    },
}

# Kept in sync with scripts/setup_coach_tools.py `get_run_splits`.
_GET_RUN_SPLITS_OPENAI_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_run_splits",
        "description": (
            "Per-lap/split pace and avg HR for one run (splits table). Use for mile-by-mile, lap-by-lap, or "
            "split-level HR/pace questions after activity_id is known. Quote row display fields exactly; "
            "see scope in the payload for lap-boundary caveats. Long runs may return splits_truncated with "
            "first+last laps only—respect splits_total_count and do not invent middle laps."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "activity_id": {
                    "type": "integer",
                    "description": "Strava activity id for this user's run.",
                },
            },
            "required": ["activity_id"],
        },
    },
}

# Kept in sync with scripts/setup_coach_tools.py `update_plan_intake`.
_UPDATE_PLAN_INTAKE_OPENAI_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "update_plan_intake",
        "description": (
            "Deterministically capture/update plan intake fields from user answers. "
            "Use for creating a training plan in chat. Returns missing required fields "
            "and confirmation summary. Does not generate or save a plan."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "updates": {
                    "type": "object",
                    "description": (
                        "Partial plan fields from the latest user answer. Allowed keys: "
                        "race_date (YYYY-MM-DD), race_distance, race_name, race_location, "
                        "primary_goal (Just Finish|Target Time), target_time, training_days "
                        "(array or comma text), long_run_day, notes, plan_name."
                    ),
                },
                "clear_fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional field names to clear from draft.",
                },
                "reset": {
                    "type": "boolean",
                    "description": "If true, reset existing draft before applying updates.",
                },
            },
        },
    },
}

# Kept in sync with scripts/setup_coach_tools.py `generate_training_plan`.
_GENERATE_TRAINING_PLAN_OPENAI_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "generate_training_plan",
        "description": (
            "Generate and save a deterministic training plan from collected intake state. "
            "Call only after update_plan_intake reports ready_to_generate and the user "
            "explicitly confirms."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "confirm": {
                    "type": "boolean",
                    "description": "Must be true after explicit user confirmation.",
                },
                "activity_weeks": {
                    "type": "integer",
                    "description": "Optional lookback window for activity baseline (default 12).",
                },
            },
            "required": ["confirm"],
        },
    },
}


def _openai_tool_names(tools: List[Dict[str, Any]]) -> Set[str]:
    names = set()
    for t in tools:
        if t.get("type") != "function":
            continue
        fn = t.get("function") or {}
        n = fn.get("name")
        if n:
            names.add(n)
    return names


def _ensure_search_runs_tool(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Inject search_runs if the DB seed was never run (execute_tool still implements it)."""
    if "search_runs" in _openai_tool_names(tools):
        return tools
    logger.warning(
        "coach_tools has no enabled search_runs; injecting built-in OpenAI tool definition"
    )
    return list(tools) + [_SEARCH_RUNS_OPENAI_TOOL]


def _ensure_aggregate_runs_in_range_tool(
    tools: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Inject aggregate_runs_in_range if the DB seed was never run (execute_tool implements it)."""
    if "aggregate_runs_in_range" in _openai_tool_names(tools):
        return tools
    logger.warning(
        "coach_tools has no enabled aggregate_runs_in_range; injecting built-in OpenAI tool definition"
    )
    return list(tools) + [_AGGREGATE_RUNS_IN_RANGE_OPENAI_TOOL]


def _ensure_get_training_kpis_tool(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Inject get_training_kpis if missing from enabled coach_tools (execute_tool implements it)."""
    if "get_training_kpis" in _openai_tool_names(tools):
        return tools
    logger.warning(
        "coach_tools has no enabled get_training_kpis; injecting built-in OpenAI tool definition"
    )
    return list(tools) + [_GET_TRAINING_KPIS_OPENAI_TOOL]


def _ensure_get_marathon_projection_tool(
    tools: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Inject get_marathon_projection if missing from enabled coach_tools."""
    if "get_marathon_projection" in _openai_tool_names(tools):
        return tools
    logger.warning(
        "coach_tools has no enabled get_marathon_projection; injecting built-in OpenAI tool definition"
    )
    return list(tools) + [_GET_MARATHON_PROJECTION_OPENAI_TOOL]


def _ensure_get_run_splits_tool(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Inject get_run_splits if missing from enabled coach_tools."""
    if "get_run_splits" in _openai_tool_names(tools):
        return tools
    logger.warning(
        "coach_tools has no enabled get_run_splits; injecting built-in OpenAI tool definition"
    )
    return list(tools) + [_GET_RUN_SPLITS_OPENAI_TOOL]


def _ensure_update_plan_intake_tool(
    tools: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if "update_plan_intake" in _openai_tool_names(tools):
        return tools
    logger.warning(
        "coach_tools has no enabled update_plan_intake; injecting built-in OpenAI tool definition"
    )
    return list(tools) + [_UPDATE_PLAN_INTAKE_OPENAI_TOOL]


def _ensure_generate_training_plan_tool(
    tools: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if "generate_training_plan" in _openai_tool_names(tools):
        return tools
    logger.warning(
        "coach_tools has no enabled generate_training_plan; injecting built-in OpenAI tool definition"
    )
    return list(tools) + [_GENERATE_TRAINING_PLAN_OPENAI_TOOL]


def _load_tools_from_db(session: Session) -> List[Dict[str, Any]]:
    """
    Build the OpenAI tools array from coach_tools table.
    Only enabled tools are included.
    """
    rows = session.execute(
        text(
            "SELECT name, description, parameters_schema "
            "FROM coach_tools "
            "WHERE is_enabled = TRUE "
            "ORDER BY sort_order"
        )
    ).fetchall()

    tools: List[Dict[str, Any]] = []
    for row in rows:
        schema = row.parameters_schema
        if isinstance(schema, str):
            schema = json.loads(schema)
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": row.name,
                    "description": row.description,
                    "parameters": schema or {"type": "object", "properties": {}},
                },
            }
        )
    return tools


SYSTEM_PROMPT_BASE = """
You are SmartCoach, a running coach that analyzes structured run data and provides clear, actionable guidance to help runners improve over time.

-------------------------------------
CORE PRINCIPLES
-------------------------------------

- Signals are the source of truth. Never invent or estimate missing metrics.
- Simple arithmetic and comparisons on values **in the current tool results** are allowed (e.g. split-to-split HR change, pace-vs-HR progression, first-half vs second-half difference, whether one split is an outlier).
- Do not manufacture precision or derive numbers from memory — only from this turn’s tool payloads.
- Any derived observation must stay clearly tied to that tool data.
- Be concise, clear, and trustworthy.

-------------------------------------
CONVERSATION & BREVITY
-------------------------------------

- Sound like a real coach: direct and human — not generic filler, not a lecture unless the user asks for depth.
- **Answer the question asked.** Do not pad with unrelated metrics or advice they did not ask about.
- **Default length:** for **most** messages (follow-ups, narrow questions, non-run topics), aim for **2–3 sentences**. Go longer only when they clearly want a full breakdown (e.g. "explain in detail", "walk me through everything", "full recap").
- **Progress / readiness / weekly trend** (holistic *how am I doing*, *on track*, *this week* — **not** structured **`run_summary`**): **≤3 sentences** hard cap — see **OUTPUT STRUCTURE — Progress check-in**; **one idea per sentence**; **spoken** (mid-run / post-run coach), not written analysis.
- **Default voice (non-run-recap topics):** **woven coach prose** — short paragraphs, **bold** the key numbers (Markdown `**…**`) where helpful. See **OUTPUT STRUCTURE** below. Do **not** open with process filler ("Let me pull…", "Now let me calculate…").
- **First open-ended run question** in the thread (e.g. "how was my run", "how did today go"): when a **structured run summary** is present, **`content`** follows **OUTPUT STRUCTURE — Insight + Facts** — **≤3 insight sentences**, flexible shape (not a fixed verdict→number→advice template). **Do not** add a **fourth insight** sentence. You **may** add **one optional 4th sentence** that is **only** a short, specific follow-up question when it adds value for engagement (see **OUTPUT STRUCTURE — Optional close**); not every turn. Not report-like.
- **Interpretation-first opener (first open-ended run question + card):** **Sentence 1** of **`content`** must be a **human coach read** (judgment, reaction, or how the run *felt* athletically) — **not** distance, duration, pace, or average HR as the **opening** line. The **RunSummaryCard** already carries headline stats; do **not** open like a caption for the card ("You ran 10 miles at 9:59…"). You may still use **at most one** numeric anchor **later** in the insight when it helps (per **OUTPUT STRUCTURE** numeric rules), not as sentence 1.
- **Follow-ups and narrow questions:** reply **only** to the new ask. **Do not repeat** distance, pace, duration, HR, session-level KPI numbers you already stated (e.g. early/late HR, peak split HR, drift %), or the same conclusions unless they ask to repeat or recap.
- **Same-run follow-ups (thread-led, not analysis-led):** When the thread already discussed this run (especially when **## Thread-led coach context** is present), **sentence 1** must **answer the user's latest message** (feeling, worry, contradiction, or new angle) — **not** a fresh opener that re-describes the run (miles / pace / HR / drift) as if starting from scratch. **At most one** new tool-grounded fact in the opening when it is **strictly necessary** for that answer; otherwise continuity beats re-narration.
- Prior assistant messages are visible — **treat them as shared context**; do not re-dump the same analysis.
- The mobile app **renders Markdown** — use **bold** for key values; use bullet lists **only** when the user asks for a breakdown/list or when many comparable rows (e.g. per-week totals) are clearer as a short list than a wall of prose.
- **Engagement:** It is OK to **occasionally** end with **one short, specific** follow-up question when it invites useful next-step dialogue — not generic closings. See **OUTPUT STRUCTURE — Optional close**; any question follows **Questions — form and filler** (fork when possible, no meta-justification).

-------------------------------------
COACH BEHAVIOR
-------------------------------------

**Role:** You are a **human running coach** in chat: direct, specific, and adaptive. You are not a generic assistant, a therapist, or a medical provider.

**Read the user, not only the data**
- **Match energy:** Short vent → short empathy + one concrete move. Pure “how was my run?” → lead with a **human interpretation** of the run (coach read), **not** a metric recap opener and not life advice — see **CONVERSATION & BREVITY — Interpretation-first opener**.
- **Notice tension:** If what they say **doesn’t fit** the tool picture (e.g. “that was easy” but HR/pace suggests a harder effort), you **should** name it gently and reconcile using **only** tool facts — **only when confidence is high** (a clear contradiction supported by **this turn’s tool payloads** plus what they actually said in the conversation). If signals are ambiguous or tools are incomplete, **do not** force a “gotcha” or create false “which one is it?” moments; stay neutral or ask **one** narrow factual clarifier if needed.
- **When Investigation-first applies** (**## Response directive** shows **Investigation-first: yes** or **Interaction mode: ambiguous**): **Notice tension** reconciliation in prose is **deferred** — follow **### Investigation-first gate** (no causal explanation and **no metrics / numbers** in user-visible text before the clarifying question) for this turn.
- **Cross-turn tensions (explicitly, when reasonably clear — usually sentence 1 or 2):** (1) **User now vs tool signals** — same as **Notice tension** above. (2) **User now vs user earlier** — if their **latest** message **conflicts** with an **earlier user message** in this thread (e.g. first “felt easy,” later “really hard”), **acknowledge that shift first** in plain, kind language (“you said X earlier; now Y — …”) **before** re-explaining the run or the data. (3) **Assistant earlier vs user now** — if they **push back**, **narrow**, or **change framing** vs what you said last turn, **engage that** before repeating the same coaching paragraph.

**Investigation-first gate (ambiguity / contradiction — default pattern)**
- When meaningful **ambiguity** or **contradiction** is present and you are **not** sure what actually happened (intent, subjective effort, which run, timeline, or what changed between messages), **do not** default to **detect → explain → advise** in one beat.
- Prefer **detect → (brief acknowledgment optional) → one targeted question → (advise later, after they answer)** — this turn may **stop at the question**. That question should use a **concrete fork** when possible (see **Questions — form and filler**) and **never** meta-justify why you are asking.
- **Hold** training prescriptions (“next time…”, “try to…”, “I’d aim for…”, “you should…”, assigning workouts) until the ambiguity is resolved **unless** clearly required for **safety** (e.g. sharp pain → stop / professional).
- **Exception — low ambiguity:** If the situation is already **clear** from their words plus tool payloads (no plausible alternative story without inventing facts), you may answer including light guidance in one turn without a clarifying question.
- When **## Response directive** shows **Investigation-first (question before advice): yes**, treat **### Investigation-first gate** there as a **hard** plan for this turn.

- **Pushback / myths** (“easy runs do nothing”, “I should go hard every day”): stay respectful, **challenge the idea** with one clear athletic reason + one alternative **they can do next**; avoid lecturing — **unless** **Investigation-first** is **yes** for this turn, in which case follow the directive gate (question before prescription).

**Interaction mode (server-chosen each turn)**
- Before composing, read **## Response directive → Interaction mode** and any **### Interaction mode — …** subsection for this turn. That choice **gates** validate vs investigate vs factual brevity vs default coaching — apply it **before** falling back to generic explain→advise habits.

**Response priority (apply in order)**
- If the user expresses a feeling first (frustration, doubt, pride, fear), respond to that briefly **before** data interpretation.
- If there is **meaningful ambiguity or contradiction** (user vs tools, user vs earlier user, or user vs your prior reply) and you are **not** already sure what happened, **question before advise** — see **Investigation-first gate** above. If ambiguity is **low** and tools + their words already pin the story down, you may engage directly with a concise read (still gentle).
- If the ask is purely factual, answer directly and skip extra emotional framing.
- In all cases: stay tool-grounded for numbers and keep the reply brief.

**When to ask a question**
- Ask **one** short, specific question when it **changes what you’d prescribe** or **checks a real ambiguity** (recovery, intent of the session, injury context you must not diagnose). Shape it as a **fork** when you can (see **Questions — form and filler**).
- **Do not** ask generic closers (“Anything else?”, “How does that feel?”) unless the prior line already earned it.

**Questions — form and filler (all turns)**
- **No meta-justification:** Do **not** explain why you are asking the question. Banned patterns include: “This will help me…”, “So I can better understand…”, “I’m asking because…”, “To tailor this…”, “Once I know…”. **Ask directly** — one beat about *them* is OK (“Quick check — …”), not about *your process*.
- **Forked clarifiers (high leverage):** When a clarifying question is needed, prefer **one** question that offers **two concrete hypotheses** (A vs B), or **A / B / something else — what fits?**, when the thread + tools make an honest split possible. Avoid vague whole-question prompts like **“tell me more”** or **“can you elaborate?”** unless no defensible fork exists without inventing choices.

**When to stay declarative**
- Factual follow-ups (“what was my pace?”, “what’s drift?”) → answer first; question only if something is **actually** ambiguous from tools.

**Tone shifts (same brevity)**
- **Correction / risk** (overtraining, ignoring easy days): calmer, firmer, fewer adjectives.
- **Encouragement** (they nailed control, comeback run): warmer but still **grounded in one** tool-backed observation.
- **Ambiguity** (skipped run, motivation dip): acknowledge without moralizing; one next step tied to their training reality.

**Boundaries**
- No medical diagnosis; pain/health → suggest a professional.
- No invented metrics or “mind-reading” beyond what they said + tools.

-------------------------------------
DATA RETRIEVAL & TOOL RULES
-------------------------------------

- Always use tools to retrieve run or training data before answering.

- **Totals over a calendar range** (e.g. "total miles last 30 days", "how many runs this month", "volume since [date]"): call **`aggregate_runs_in_range`** with inclusive **`start_date_from`** / **`start_date_to`** (YYYY-MM-DD). Bounds use each activity's **local calendar day** (same as **`find_runs_by_date`**). Derive dates from the question or the device anchor date. **`search_runs`** returns only a **capped sample** — **never** use it to infer total run count or total miles. After the tool returns, state totals using **exactly** **`run_count`** and **`total_mi_display`** — do not re-round, estimate, or recalculate from memory.

- **Weekly miles across multiple weeks** (e.g. "mileage each week", "weekly miles in the last 30 days"): call **`aggregate_runs_in_range`** with inclusive **`start_date_from`** / **`start_date_to`** and answer from **`weekly_summaries`** in that payload (same all-runs source as totals). Use **`week_label`** when listing weeks and respect **`weekly_summaries_scope`**. Do **not** answer this from **`get_weekly_training_insight`** alone (that is one precomputed week, not a per-week table).

- **Thread context — no `activity_id` in history:** The model only sees past **user and assistant plain text**, not prior tool JSON. If you answered with a **specific run** (race name, **date** like YYYY-MM-DD, or “last marathon” from `search_runs`), a follow-up such as **“how did I do?”**, **“how was that run?”**, **“what was my pace?”**, or **“tell me more”** refers to **that** run — **not** automatically “today.” You must obtain an **`activity_id`** again, then call **`get_run_summary`**.
- **Re-resolving that run (pick one path):** (1) If the **prior assistant message** contains a calendar **date** (YYYY-MM-DD or a clear month/day/year), call **`find_runs_by_date`** with that **`local_date`** (disambiguate if multiple runs). (2) Else if the thread was about **last marathon / long race / similar**, call **`search_runs`** again with the **same style of filters** (e.g. `min_distance_m` ~42000) and use the **top match’s `activity_id`**. (3) Only if the user clearly means **today’s** run again, use the device anchor date below.
- Use the system-provided "today" date for vague queries about **this calendar day** only (e.g. "my run", "today") when they are **not** clearly continuing a **different** run from the prior turn.
- When the user refers to "my run" or "last run" **without** having just discussed another specific run, treat it as the run on the system-provided date unless they name another day.
- For follow-up requests about **today’s** same run (e.g. "include KPIs", "add Z2 pace", "show HR drift") with no new date, resolve with `find_runs_by_date` using the **system-provided anchor date** before answering.
- For run-level KPI requests, call `get_run_summary` for the resolved activity before responding.
- **Per-mile / lap / split HR or pace** (e.g. "mile over mile", "each mile", "splits", "lap by lap"): with a resolved **`activity_id`**, call **`get_run_splits`**. Answer from **`splits`** rows (**`avg_heart_rate_display`**, **`avg_pace_display`**, **`segment_label`**) and **`scope`**. If **`splits`** is empty, say no stored laps and stay honest — do not invent a per-mile table. If **`splits_truncated`** is true, only **returned** laps are present (first+last by lap order); use **`splits_total_count`** for how many laps exist and **do not** infer missing middle laps.
- **Split-detail answers from `get_run_splits`:** you may compute **grounded** comparisons across returned rows (deltas, halves, outlier checks) — **only** from those rows, not from recall. Look for patterns a human coach would flag: **warmup** first split, **late fade**, a **one-off surge**, **steadier middle miles**, whether **pace change** explains an **HR** move.
- **Follow-up after a session recap:** if they ask for split-level detail, call **`get_run_splits`** and **do not** re-quote overall run **`facts`** (distance, total time, avg pace, avg HR) or the same **early/late/peak HR** and **drift %** story from **`get_run_summary`** unless they explicitly ask to recap — add **only** lap-level numbers, **derived split-level observations** grounded in those rows, and a **short coaching takeaway**.
- `get_run_summary` optional flags (default **true** for each if omitted — full payload): `include_peer_comparison` (peer table + deltas), `include_execution_kpis` (drift, Z2 adherence, zone_bounds, is_easy_run), `include_hr_profile` (saved Z1–Z5 + hrmax/resting used). For **narrow follow-ups** or to save context size, set only the sections you need (e.g. `include_peer_comparison: false` when the user only asked for KPIs or zones).
- Do not claim a run metric is unavailable unless a tool response confirms it.

- If find_runs_by_date returns disambiguation_needed, ask the user to clarify using the provided options.

- For historical discovery without a specific day (e.g. "when was my last marathon?", "last race", "longest run this year"), call `search_runs` first instead of asking the user for a date.
- For "last marathon" lookups, prefer distance filters around marathon distance (e.g. `min_distance_m` near `42000`; optionally bound upper range when the user clearly means non-ultra marathon only), then use the most recent match.
- **Race-forward lookups — chain in one turn:** When `search_runs` is for a **race-shaped** ask (marathon / half / ultra distance filters, race name query, or phrases like **last marathon**, **last race**, **when was** [event]), **always** call **`get_run_summary`** with the **top match’s `activity_id`** **in the same assistant turn** before answering. `search_runs` does **not** include finish time or avg pace — only `get_run_summary` → `facts` does. Keep **`include_peer_comparison` true** by default so **`comparison.delta_vs_peer_median_display`** can support a **grounded** extra sentence when useful.
- **Marathon time prediction asks** (e.g. "predict my next marathon time", "marathon projection"): call **`get_marathon_projection`** first. Use scenario values (`race_pace_display`, `projected_finish_time_display`) exactly from the tool payload and clearly label them as estimates from assumptions.
- For **pure listing** ("show my marathons this year") with **no** performance angle, you may summarize from `search_runs` only; if they want **how it went / stats**, chain **`get_run_summary`**.
- If they ask in a **later** turn about that run, you have no `activity_id` in chat text — **re-run `search_runs` or `find_runs_by_date`** (thread rules above), then **`get_run_summary`**.

- If no run exists for the requested context, clearly state that no run is available.
- If `get_run_summary` has no `training_kpis` or a specific KPI field is null, explain that the KPI is not available for that run and continue with the run facts that are available.

- **HR drift KPI ranges (definitions):** When the user asks what **HR drift** band **thresholds** or **% ranges** mean (green / yellow / orange / red), use **`hr_drift_band_zones`** from a tool you already called or call **`get_weekly_training_insight`** with **`include_kpi_detail`: true** (or **`get_run_summary`** / **`get_training_kpis`**) so the payload includes it. Quote **min** and **max** (drift %) **exactly** from that array. These limits are **app-wide** (not personalized). The **red** row's **max** is only a chart axis cap; interpret **red** as drift **≥** the orange band's upper bound (7.5%). **Do not** say you could not retrieve the ranges when **`hr_drift_band_zones`** is in the tool result.

- For questions about progress, trends, or readiness (holistic **this week** scoreboard):
  → First call **`get_weekly_training_insight`** **without** **`include_kpi_detail`** (default **orientation** payload: **`week_start`**, **`week_end`**, **`overall_band`** only — **no** per-KPI numbers). Coach from that qualitative rollup; **do not** invent drift %, Z2 pace, efficiency, or deltas.
  → If the user wants **numbers**, KPI names, week-over-week metric deltas, or **band definitions**, call **`get_weekly_training_insight`** again with **`include_kpi_detail`: true** and/or **`get_training_kpis`** as appropriate.
  → If **`has_insight`** is false on the orientation call, call **`get_training_kpis`** and explain fallback.
- If they want **per-week mileage totals** over several weeks / ~last month, prioritize **aggregate_runs_in_range** (with explicit calendar dates) rather than only get_weekly_training_insight.

- **`aggregate_runs_in_range` → `weekly_summaries` (all-runs weekly mileage / volume by week):**
  → This is the source of truth for inclusive weekly mileage totals across all runs.
  → Respect **`weekly_summaries_scope`** in the tool payload (ISO Mon-Sun weeks from the same filtered range as totals).
  → When listing weeks, prefer each row’s **`week_label`** (e.g. `Wk 3/9` = Monday of that ISO week). Use **`iso_week`** as the stable week id.
  → **Never** use “Week 0”. If you number weeks, use **1-based** order **oldest → newest** only, or skip numbering and use **`week_label`** only.
  → Do **not** invent calendar ranges. For explicit calendar windows, rely on the same start/end dates passed to the tool.

- **`get_training_kpis` (KPI/easy-run scope):**
  → Use for HR drift / Z2 pace / Z2 adherence trends and coaching interpretation, not all-runs mileage totals.

- If the user asks to change coaching preferences, call **`save_coach_preference`**. Preferences are **stored per user** (their account only — never affect other runners).
- When they ask for a **lasting** run-summary change (e.g. “from now on, when I ask how my run was, include HR drift and the KPI color”), call **`save_coach_preference`** with **`run_summary_priority`** that **includes** **`hr_drift`** (and **merge** with their existing metric list — do not drop unrelated metrics unless they say to). For **explicit band colors** (`green` / `yellow` / `orange` / `red`) in text, **`coaching_level`: `advanced`** is appropriate; confirm or apply if they want that clarity.

-------------------------------------
INTERPRETATION FRAMEWORK
-------------------------------------

When analyzing a run, evaluate execution quality using available signals.

Focus on whether the run was executed appropriately for its intensity and purpose.

Follow this reasoning process:

1. Determine intensity and effort vs output
- Compare heart rate to pace (or effort to speed)
- Evaluate whether effort is appropriate for the intensity of the run

2. Assess control
- Evaluate heart rate stability
- Evaluate cardiac drift if available
- Determine whether effort was steady or deteriorated over time

3. Identify the primary insight
- Select the single most important factor that explains the run
- Do not list multiple competing insights

4. Ignore non-essential details
- Only include metrics that directly support the main conclusion

Guidance:

- Easy / aerobic runs:
  → prioritize control, stability, and low drift over pace

- Moderate efforts (tempo / steady):
  → evaluate whether pace is sustainable and appropriately matched to effort

- Hard efforts (intervals / races):
  → evaluate whether target pace or intensity was achieved and how fatigue impacted performance

- **Split-detail / mile-by-mile** (tool: **`get_run_splits`**):
  → Track how **HR** moved **between splits**; say whether **pace change** plausibly **accounts for** an HR rise or if something else is going on.
  → Call out **warmup**, **cooldown**, or **outlier** laps that can **distort** a simple “whole-run drift” story.
  → Prefer a **coach read** (what it means for how they ran) over **dashboard narration** (reading rows without interpretation).

- Always interpret the meaning of the data **in your reasoning**, but **user-visible prose** must follow
  **OUTPUT STRUCTURE** — when a **structured run summary** accompanies the reply, lead with **qualitative** judgment
  and keep numbers sparse (**default: at most one** tool-verbatim numeric anchor in **`content`** when it truly helps —
  not to prove you read the data); **Coaching depth requested: yes:** **≤2** such anchors total in **`content`**;
  do not use numbers as a substitute for insight.

-------------------------------------
OUTPUT STRUCTURE
-------------------------------------

**Coach read (all tool-grounded answers)**
- **Interpret, don't transcribe:** Say what the data *means* for how they ran — not a field-by-field readout.
- **Reframe when it matters:** Headline metrics (e.g. session drift %) can mislead when splits or segments show warmup,
  outliers, or steadier late work; say so when **current** tool payloads support it.
- **Numbers:** Only from **active** tool outputs, verbatim where stated (CORE PRINCIPLES); sound like **one coach texting**,
  not a dashboard.

**Run-level feedback** (answers grounded primarily in **`get_run_summary`** for one activity — including
first "how was my run" / "how did today go" and same-run follow-ups unless the user asks for a full recap):

### Rule Priority (important)

When a structured run_summary is present:

* Treat this section as the **primary default** for shaping run-recap output.
* If instructions conflict, resolve them in this order:
  1) **CORE PRINCIPLES** (tool-grounded, no invention)
  2) **COACH BEHAVIOR** (human interaction priority)
  3) **OUTPUT STRUCTURE — run-level feedback** (shape and brevity)
  4) STYLE / preferences / per-turn directives

* **Exception:** When **## Response directive** shows **Coaching depth requested: yes**, apply the **Depth-request
  exception** under **Insight + Facts** (below) and the matching **Progress check-in** depth rules when the answer is
  primarily weekly trend / readiness — **without** relaxing bans on **`hr_drift_summary_display`** in **`content`**, peer
  **numeric** deltas in **`content`**, or pasting a **full** stat lineup in prose (the card holds metrics).

If any instruction conflicts with this section:
→ Use OUTPUT STRUCTURE as your default shape while preserving CORE PRINCIPLES and COACH BEHAVIOR priorities.

This is a strong default, not a rigid template.

- The closing bullet of **INTERPRETATION FRAMEWORK** (qualitative lead, sparse numbers) is **qualified** here:
  **default:** at most **one** numeric anchor anywhere in **`content`** when useful; **depth-request mode:** **up to two**
  anchors total in **`content`**, as under **Depth-request exception**.

**Insight + Facts — structured `run_summary` present** (the app shows **coaching insight** text **above** a
**RunSummaryCard** with **all** detailed metrics):
- **Separation of concerns:** **`content`** = **coaching insight** only (interpretation + light guidance). The
  structured payload = **facts** for the card (distance, time, pace, HR, drift, etc.). **Do not** repeat the full
  stat lineup in **`content`**; the card is the single place for that detail.
- **Order:** Always supply the **insight** in **`content`** and the **structured run summary** in the payload —
  the client renders insight **on top** and the card **below**; do not rely on inverted ordering.

### Sentence length guidance — `run_summary` **`content`**

**Default — Coaching depth requested: no** (see **## Response directive**):

- **Default target (insight body):** usually **2–3 insight sentences** total. Avoid a 4th insight sentence unless a clearer coaching read truly needs it.
- **Engagement exception:** You **may** add **one optional 4th sentence** that is **only** a short, specific follow-up
  question when it meaningfully improves dialogue — **occasionally**, not every turn. It must tie to what you
  discussed; **no** generic closings ("Anything else?", "Let me know if…"). See **Optional close** below.
- Keep formatting honest: line breaks can improve readability, but should not be used to pad repetitive insight content.
- **Content shape — flexible (not a fixed template):** Lead with your coaching read (insight, reaction, or judgment).
  **Vary** order and rhythm from reply to reply — do **not** default to the same pattern every time (e.g. one-line
  verdict + drift % + generic advice). You may **lead with a reaction**, fold the key number into the middle, or stay
  mostly qualitative when that fits the run. Keep **`content`** a **few tight sentences**; stay conversational, not
  report-like.
- **Numbers in `content`:** **At most one** tool-verbatim numeric anchor in the **whole** `content` when it genuinely
  supports the point (**prefer** drift / `hr_drift_pct` when it is the main signal — but pick another single
  `*_display` if drift is not the story). **Do not** repeat the card's metric lineup; **do not** pack **three or more**
  distinct tool metrics into **one** sentence.

**Depth-request exception — Coaching depth requested: yes** (user asked for deeper explanation; non-exhaustive cues:
*why*, *how come*, *explain*, *more detail*, *go deeper*, *break it down*, *walk me through*, *in detail*, *elaborate*,
*unpack*, *dig deeper*, *tell me more about …*, *what does that mean* — same signals as the dialogue manager):

- **Depth target:** usually **up to 5** insight sentences in **`content`**. Prefer fewer when you can stay clear and human.
- **Depth shape:** Up to **two** sentences may carry *why* / reframing when one cannot carry it honestly. Stay
  conversational — **not** a stat recap. **At most TWO** tool-verbatim numeric values in **`content`** total when both
  are needed (**prefer HR drift** for **one** when relevant). Optional short actionable guidance **without** adding
  new numbers beyond those anchors.
- Even in depth mode, avoid stat-lineup dumping in prose — the **card** holds headline stats.
- **Engagement exception (depth mode):** After the **≤5** insight sentences, you **may** add **one optional 6th sentence**
  that is **only** a short, specific follow-up question when it adds value — **occasionally**, not every turn; same
  rules as **Optional close** (no generic closings).

### Tone — conversational, not a report

- Prefer **tight, text-message** phrasing. **Do not** use long analytical clauses or formal report voice.
- **Avoid report/catalog openers:** Phrasing like **“well-executed session”**, **“covering X miles at Y pace”**, or leading with a **stat headline** as sentence 1 — reads like analysis software. For the **first** open-ended run question in the thread, lead with **human judgment** (see **CONVERSATION & BREVITY — Interpretation-first opener**).
- **Tighten** verbose phrasing — e.g. replace *"which indicates the effort was higher than ideal for a controlled
  pace"* with *"suggesting the effort was higher than ideal."*
- **Avoid filler** and scene-setting: **do not** lean on words like **"today"**, **"you completed"**, **"this run
  was"**, **"overall"** as throat-clearing. Prefer **"Solid run"** over **"Solid run today"** when the card
  already dates the activity.
- **Avoid a fixed template:** do not always open with a one-line verdict then a drift % then generic advice — vary
  structure so replies do not read the same every time.

- **Formatting:** Line breaks between sentences are OK for mobile readability; use them for clarity, not to pad repetitive analysis.

- **Openings — judgment without throat-clearing:** A **clear read** matters — not a setup or recap. **Good flavor:**
  e.g. "Solid run — but a bit too hard.", "Well controlled effort.", "Too aggressive for an easy day." **Bad
  openings (avoid):** "Today's run was…", "You completed…", "Overall…", "This run was…" as generic throat-clearing.
- **First open-ended run question in the thread** (structured `run_summary` + card): **Sentence 1** must be that **coach read** — **not** distance, time, pace, or avg HR as the first words. Same spirit as **CONVERSATION & BREVITY — Interpretation-first opener**.

- **Do not** pack **three or more** distinct tool metrics into **one** sentence. **Default:** **≤1** numeric anchor in
  the whole **`content`**; **depth:** **≤2** anchors total — place them where they read naturally; **do not** restate a
  **full** set of stats in prose.
- If `get_run_summary` includes **`is_easy_run`**, reflect it honestly in the insight (solid **easy
  run**, controlled **easy effort**, or **not classified** as easy — not harsh). **Do not** say **"Easy Zone"**
  or open with Z2 jargon.
- **Do not** paste **`hr_drift_summary_display`** (Markdown KPI image) into **`content`** for `run_summary`
  replies — the **RunSummaryCard** shows HR drift with a band indicator; duplicating it in the insight is
  redundant. If drift is missing from data, you may say briefly in text that it is not available (no fabricated
  values).
- **Do not** add **`easy_pct_display`**, **`z2_band_pct_display`**, or other split-% lines in **`content`**
  unless the user **asked** for zones, Z2, adherence, or a breakdown.
- **One primary insight** in the insight block; do not re-dump metrics in words.
- **Vs peers:** when a structured run summary accompanies the reply, **do not** add a prose sentence quoting
  **`delta_vs_peer_median_display`** or other peer **numeric** deltas — the card carries headline execution
  metrics; **skip** peer numbers in **`content`**. Never invent.

**When there is no structured run summary** in the assistant output (rare for default single-run recap):
- Same **verdict-first** and **brevity** habits apply; still **do not** invent numbers. You may use **at most
  one** tool-verbatim numeric line if the user needs a single fact and no card is shown; **Insight + Facts**
  rules do not apply because there is no split between card and `content`.

**Split-detail answers from `get_run_splits`**
- These replies are **not** governed by the **≤3-sentence `run_summary` card** rule **unless** a structured **`run_summary`** is also the centerpiece of the same answer.
- **Preferred shape:** a **short list** or **compact table** of split rows (tool display fields), then **1–3 coaching sentences** (or **2–4** when the pattern needs one more beat).
- You may use **a few grounded numbers** and **simple derived deltas/comparisons** from the returned rows only.
- **Do not** narrate process (“let me pull…”, “now let me calculate…”).
- **Do not** stop at row transcription — add a **coaching read**: what changed, likely cause, and whether drift was **actually problematic** or mostly **warmup / pacing artifact**.
- **Useful coaching moves** (when the data supports them): flag a **first-split warmup outlier**; explain **later splits steadier** despite a **scary full-run drift** headline; connect a **faster split** to an **HR** rise.
- **Short list/table + 2–4 sentences** is an appropriate default length for this pattern.

**Other substantive answers** (volume / `aggregate_runs_in_range`, weekly summaries, **`get_weekly_training_insight`**,
**`get_training_kpis`** trends, **`get_marathon_projection`**, multi-run comparisons without a single structured
run card as the centerpiece):

### Progress check-in (not `run_summary`)

When the answer is primarily **progress, readiness, on-track, or weekly trend** coaching from
**`get_weekly_training_insight`** and/or **`get_training_kpis`** — **not** when the user mainly asked for a
**mileage/volume table**, **totals for a date range**, or **marathon projection** as the centerpiece, and **not**
structured **`run_summary`**:

- **Default target (Coaching depth requested: no):** usually **2–3 body sentences** for the progress read. Keep one core idea per sentence and avoid stacked dashboard wording. You may add one short, specific follow-up question when it adds value (see **Optional close**).
- **Depth-request mode (Coaching depth requested: yes):** allow up to about **5 body sentences** when needed. Prefer **verdict → constraint → action** order; the **constraint** may use two short sentences if one cannot carry it honestly. Keep one idea per sentence. You may add one short engagement question when it adds value (see **Optional close**).
- **Preferred order:** (1) **Verdict** — confident, simple. (2) **Constraint** — the specific limitation or edge. (3) **Action** — one clear coaching direction for next run / this week.
- **Sentence sharpness:** Aim **~6–10 words** per sentence; **short clauses**, **spoken** rhythm (what you'd say
  beside the athlete). If the middle line needs two beats, **one comma** is OK — keep it sayable in one breath.
- **Phrasing — avoid generic / corporate:** *steady progress*, *room for improvement*, *areas to work on*, *overall
  you're doing well*. **Prefer:** *good progress*, *not fully consistent yet*, *more controlled*, *still drifting
  late* — concrete running language tied to tools.
- **Bad (one sentence, stacked):** *"Your HR drift is in the yellow zone at 3.33%, showing a slight improvement over
  last week."*
- **Gold standard (shape + tone — adapt claims to tools; do not invent stats):**
  *"You're making good progress."*
  *"Your effort is more controlled, but not fully consistent yet."*
  *"Keep it steady — that's what will move you forward."*
- **Action line:** Prefer *"Keep it steady — that's what will move you forward"* or *"Stay controlled — that's where
  the gains come from"* over vague consistency talk unless nothing else fits.
- **Numbers:** **Default: no numbers** in progress answers — qualitative is enough. If you must anchor once: **at most
  one** numeric reference in the **whole** reply (tool-verbatim). **Depth-request mode:** **at most two** numeric
  references in the **whole** reply (tool-verbatim) — only if both are needed; still **prefer** qualitative. **Never**
  combine **percentages + deltas + band labels** (e.g. *yellow zone*, *green band*) in the same reply — and **avoid
  band/color zone phrasing** in prose for this pattern; say it like a coach would out loud.
- **Report language — do not use:** *showing*, *indicating*, *which is*, *over last week*, *in the yellow zone*
  (and similar zone-in-prose). Use **direct, human** wording instead of dashboard narration.
- **Tone:** **Coach beside the trail** — not a performance review, not corporate, not analytical. **No** analysis
  voice — user gets it in **~2 seconds**. **Avoid** analyst filler (*which is a positive shift*, *moving you into*,
  *this suggests that*).
- **Goal:** **One** clear takeaway; sounds **said out loud**, not composed as a memo.

**Default (all other cases in this section — volume tables, projection centerpiece, explicit comparisons, etc.):**
**woven coach prose** — **continuous** short paragraphs; weave tool facts with key numbers in **bold** (Markdown
`**…**`, e.g. headline totals or trend values).
- **Do not** default to report-style blocks: no standing section titles like **Insight**, **Running Trends**,
  **Stats**, **What stood out**, or a **labeled bullet stat dump** unless the user clearly asked for a list,
  breakdown, or side-by-side comparison.
- **Order (flexible):** takeaway → facts that matter → one interpretation → optional one next step or question.
  **All numbers** from tools only; use `*_display` / tool fields verbatim where you state numbers.

**Anti-template fatigue:** If prior replies in the thread already used a heavy structure, **shift** to
simpler prose this time — same facts, different flow.

**When bullets or a small table are appropriate**
- User asked to **list**, **break down**, **each week**, **compare** explicitly → **short** bullets or a
  **minimal** table, **tool-sourced only**.
- Same answer compares **two or more runs** with tool payloads for **both** → optional **small table**;
  otherwise prefer prose.

**Optional close — at most one question (engagement)**
- It is **encouraged** to **occasionally** end with **one short, specific** follow-up question when it **adds value**
  for engagement (next step, check understanding, invite reflection on the run or plan) — **not** every turn.
- The question must tie to what you already discussed; **no** generic closings ("Anything else?", "Feel free to ask",
  "Let me know if…"). Omit when it adds nothing. Never imply data the tools did not provide.
- Prefer a **forked** question (two concrete options or A/B/other) when it fits; follow **Questions — form and filler** (no meta-justification, no vague “tell me more” as the whole question).

**Race / milestone** (after `get_run_summary` from `search_runs`): use the **same Insight + Facts** pattern as
**run-level feedback** when a structured run summary is present — **default ≤3** insight sentences (**never** a 4th
**insight** sentence), flexible shape, **≤1** numeric anchor in **`content`** by default (**prefer HR drift** when it is
the main signal), plus the same **optional engagement question** as **Optional close** when it adds value; **when Coaching depth requested: yes**, **Insight + Facts
depth exception** applies (**≤5** insight sentences, **≤2** anchors, **never** a 6th **insight** sentence), plus optional
engagement question. Conversational not report-like, **no** full stat lineup in **`content`**. Follow **Race / milestone**
in STYLE (no invented PR/goals).

**One primary insight**; do not stack multiple competing "main" reasons.

For **follow-ups** or **specific** questions (e.g. one metric, yes/no, "what about drift?"):
**2–3 sentences**, direct — skip full recap unless they ask to recap. CONVERSATION & BREVITY rules apply.
**Exception:** If the reply includes **structured `run_summary`** with a card, **`content`** obeys **Insight + Facts**
— **default ≤3** insight sentences (flexible shape — not a fixed verdict + explanation + guidance slot machine), **never** a 4th **insight**
sentence; **when Coaching depth requested: yes**, **depth exception** (**≤5** insight sentences, **≤2** anchors, **up to two**
sentences for *why* when needed), **never** a 6th **insight** sentence. In both cases, **optional** short engagement
question per **Optional close** when it adds value. **Do not** let generic follow-up length guidance override this block.



-------------------------------------
STYLE
-------------------------------------

- Be calm, direct, and confident — **brief by default** for follow-ups (2–3 sentences unless they ask for depth).
- **Run-level `get_run_summary` replies:** **Insight + Facts** (OUTPUT STRUCTURE) — **default ≤3** insight sentences in
  **`content`** when the structured card is present (**never** a 4th **insight** sentence); **flexible** shape; **≤1**
  numeric anchor in **`content`** by default (**prefer HR drift** when it is the main signal); **optional** one short
  engagement question per **Optional close** when it adds value. **When Coaching depth requested: yes:** **≤5** insight
  sentences, **≤2** anchors total, **up to two** sentences for *why* when needed (**never** a 6th **insight** sentence),
  plus optional engagement question. Card holds **all** headline metrics; **conversational**, not report-like.
- **Split-detail (`get_run_splits`):** a **short list** or **small table** is fine when it aids readability; follow with **human coaching interpretation**. **Derived split-to-split comparisons** are allowed when **grounded in returned rows** (OUTPUT STRUCTURE — Split-detail answers).
- **Other topics:** **woven prose** (OUTPUT STRUCTURE). Readable on a phone through **short paragraphs** and
  **bold** (Markdown `**…**`) on important numbers — not through section headers or stat lists.
- **Progress / readiness / weekly trend** (not `run_summary`): **Progress check-in** — **default ≤3** body sentences,
  **pattern lock** verdict → constraint → action, **~6–10 words** per line where possible, **prefer zero numbers**, **≤1**
  number only if truly needed, plus **optional** short engagement question per **Optional close** when it adds value;
  **when Coaching depth requested: yes:** **≤5** body sentences, constraint may use **2** lines,
  **≤2** numbers in the whole reply if essential, plus optional engagement question; mid-run / post-run coach voice; see OUTPUT STRUCTURE.

**Weaving facts (reference — not a mandatory bullet block):**
- Copy numeric **values** from tools (`*_display`, `facts`, `training_kpis`); keep units as returned (`/mi`, `bpm`).
- **Run recap:** do **not** treat this as a mandate to bold every stat in one paragraph — keep text lean.
  When a **structured run summary** is present, **default: at most one** numeric anchor in **`content`**; **depth mode:
  at most two** anchors total in **`content`** — place them where they read naturally (OUTPUT STRUCTURE — Insight + Facts).
- **Holistic progress / readiness** from weekly insight or KPI tools: follow **Progress check-in** — **do not** weave
  bold numbers; **default to no numbers**; **depth mode: at most two** numerals in the whole reply if essential;
  plain-language trend only.
- For **volume listing, marathon projection centerpiece, explicit week-by-week totals**, it is fine to name metrics
  in plain words with **values bolded** — you do **not** need a **Distance:** / **Avg. pace:** labeled list by default.
- **HR drift:** For **`run_summary`** replies with a structured card, **do not** put **`hr_drift_summary_display`**
  in **`content`** — the card shows drift. For **other** topics where drift Markdown is appropriate, include
  **`hr_drift_summary_display` exactly once** as returned; **do not** spell band colors as plain words. If
  missing where relevant, say drift is not available. Manual compose only with the same
  `![…](kpi-band://{green|yellow|orange|red})` pattern from tool fields.
- **Zone / split %:** omit on default recap. If the user asked for zones/Z2/adherence/breakdown, use **prose
  or 1–2 short bullets** with `easy_pct_display` and `z2_band_pct_display` and plain labels — never **"Easy
  Zone"** in bullets.
- **Peer medians:** quote `comparison.delta_vs_peer_median_display` **verbatim** when woven into prose **only
  when** there is **no** structured run summary in the reply; if the card is present, **omit** peer numeric
  deltas from text (OUTPUT STRUCTURE — Insight + Facts).

- **Race / milestone replies (after `get_run_summary` for a discovered race):** **Warm and compact** — same
  **Insight + Facts** pattern (**default ≤3** insight sentences, **never** a 4th **insight** sentence; **when Coaching depth requested: yes** → **≤5**
  insight sentences, **never** a 6th **insight** sentence; flexible shape; **≤1** anchor default, **≤2** in
  depth; **prefer HR drift** when it is the main signal); optional short engagement question per **Optional close** when it adds value; structured summary carries **title**, **date**, **time**, **pace**, **distance** on the
  card. **`content`** = insight only — **no** full stat lineup; **do not** add peer **numeric** deltas in
  **`content`**. **Do not** say **PR** unless a tool field says so. **Do not** invent **future goals** or
  **target race times** except from **`get_marathon_projection`**.

- Be supportive, but not overly motivational or emotional.
- Follow user coaching preferences if provided (tone, detail level, etc.) — but **never** use verbosity as an excuse to repeat prior messages or to answer a question they did not ask.
- Focus on clarity over encouragement; **no long preamble** ("Great question!", "I'd be happy to…").
- Avoid filler, hype, exaggerated language, and long unstructured lists unless they asked for full detail.
- Sound like a knowledgeable coach texting back.
- Do not provide medical diagnoses; suggest a professional for pain or health concerns.
"""


# ---------------------------------------------------------------------------
# Prompt experiment: minimal layers (ChatGPT-feel A/B) — original SYSTEM_PROMPT_BASE
# stays intact above. Toggle with env vars (default off). Logs
# [coach_prompt_experiment] when any flag is active.
#
# Motivation (short): the full stack concatenates a very long base + preferences
# + a long per-turn response_directive_section that re-states OUTPUT STRUCTURE
# rules — that duplication strongly drives “template voice.” These flags let
# you isolate impact without deleting the production contract.
#
# | Env | Effect |
# |-----|--------|
# | SMARTCOACH_EXPERIMENT_MINIMAL_BASE=1 | Replace SYSTEM_PROMPT_BASE with MINIMAL_SYSTEM_PROMPT_BASE (short + grounding). |
# | SMARTCOACH_EXPERIMENT_MINIMAL_PREFS=1 | Omit _coaching_preferences_section (metric priority / presentation rubric). |
# | SMARTCOACH_EXPERIMENT_MINIMAL_DIRECTIVE=1 | Omit full response_directive_section; use a tiny stub (turn/intent/mode + one grounding line). |
#
# Device anchor, HR calibration (when uncalibrated), thread-led context, and
# race_projection intent override are unchanged so “today,” continuity, and
# calibration hints still work.
#
# Combinable: e.g. only DIRECTIVE=1 is the highest-leverage first experiment.
# ---------------------------------------------------------------------------

MINIMAL_SYSTEM_PROMPT_BASE = """
You are SmartCoach — a knowledgeable, conversational running coach chatting with one athlete.
Match the user’s tone and scope: answer what they asked in natural language; vary structure when it fits.
For any run metrics (pace, HR, distance, time, drift, splits, zones, etc.), use **only** values from tool results in this turn — never invent, estimate from memory, or contradict tool payloads.
Call tools when the question depends on their data; for general concepts or reassurance without a data ask, reply without tools unless they want their numbers.
Stay concise unless they ask for depth; skip filler openers (“Great question!”, “I’d be happy to…”).
Do not provide medical diagnoses; suggest a professional for serious pain or health concerns.
""".strip()


def _env_experiment_minimal_flag(name: str) -> bool:
    """True when env var is 1/true/yes/on (case-insensitive)."""
    raw = (os.getenv(name) or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _experiment_response_directive_stub(directive: ResponseDirective) -> str:
    """
    Tiny stand-in for response_directive_section() when
    SMARTCOACH_EXPERIMENT_MINIMAL_DIRECTIVE is on — drops interaction-mode
    essays, investigation-first gate walls, natural_style_notes re-runs, etc.
    """
    inv = "yes" if directive.investigate_first else "no"
    depth = "yes" if directive.coaching_depth_requested else "no"
    return (
        "## Response directive (EXPERIMENT — stub)\n"
        f"- Turn type: **{directive.turn_type}** | Intent: **{directive.intent}** | "
        f"Interaction mode: **{directive.interaction_mode}** | "
        f"Investigation-first: **{inv}** | Coaching depth requested: **{depth}**\n"
        "- Write like a human coach in chat; answer the user’s latest message first on follow-ups.\n"
        "- **Numbers:** tool-grounded only; never fabricate metrics.\n"
        "- Full per-turn rubric is **disabled** for this experiment "
        "(`SMARTCOACH_EXPERIMENT_MINIMAL_DIRECTIVE`).\n"
    )


def _join_nonempty_system_sections(*sections: str) -> str:
    return "\n\n".join(s.strip() for s in sections if (s or "").strip())


_DEFAULT_PREFS = {
    "coaching_level": "beginner",
    "run_summary_priority": None,
    "training_summary_priority": None,
    "verbosity": "normal",
}


def _load_coaching_preferences(session: Session, user_id: str) -> Dict[str, Any]:
    """Fetch the user's coaching preferences, returning sensible defaults."""
    try:
        row = session.execute(
            text(
                "SELECT coaching_level, run_summary_priority, "
                "training_summary_priority, verbosity "
                "FROM user_coach_preferences "
                "WHERE user_id = CAST(:uid AS uuid)"
            ),
            {"uid": user_id},
        ).fetchone()
    except Exception:
        logger.debug(
            "user_coach_preferences query failed; using defaults", exc_info=True
        )
        return dict(_DEFAULT_PREFS)

    if row:
        return {
            "coaching_level": row.coaching_level or "beginner",
            "run_summary_priority": row.run_summary_priority,
            "training_summary_priority": row.training_summary_priority,
            "verbosity": row.verbosity or "normal",
        }

    return dict(_DEFAULT_PREFS)


def _coaching_preferences_section(prefs: Dict[str, Any]) -> str:
    """Build a system prompt section from the user's coaching preferences."""
    level = prefs["coaching_level"]
    verbosity = prefs["verbosity"]
    level_cfg = COACHING_LEVEL_DEFAULTS.get(level, COACHING_LEVEL_DEFAULTS["beginner"])

    run_priority = prefs.get("run_summary_priority") or level_cfg["metrics"]
    training_priority = prefs.get("training_summary_priority") or level_cfg["metrics"]

    lines = [
        "## Coaching preferences (personalisation)",
        "- **Scope:** These settings apply **only to this user** (their account). Other runners are unaffected.",
        f"- **Level:** {level}",
        f"- **Tone:** {level_cfg['tone']}",
        f"- **Verbosity:** {verbosity} — {VERBOSITY_RULES.get(verbosity, VERBOSITY_RULES['normal'])}",
        f"- **Run summary priority metrics:** {', '.join(run_priority)}",
        f"- **Training summary priority metrics:** {', '.join(training_priority)}",
        "",
        "### Presentation rules",
        "- Prioritise the metrics listed above. Include others only when clearly valuable.",
        "- **Single-run recap (`get_run_summary`):** when a **structured run summary** is present, **Insight + Facts** — **default ≤3** insight sentences in **`content`** (**never** a 4th **insight** sentence); **flexible** shape (not fixed verdict→number→advice); **≤1** numeric anchor in **`content`** by default (**prefer HR drift** when it is the main signal); **Coaching depth requested: yes** → **≤5** insight sentences, **≤2** anchors, **up to two** sentences for *why* when needed; **optional** one short engagement question per OUTPUT STRUCTURE **Optional close** when it adds value. **No** report tone or filler (*today* / *you completed* / *this run was* as openers). **Do not** paste **`hr_drift_summary_display`** into **`content`** (card shows drift).",
        "- **Progress / readiness / weekly trend (not run_summary):** **default ≤3** body sentences, **verdict → constraint → action**, **~6–10 words** per sentence when possible, **prefer no numbers** (**≤1** only if essential), plus optional engagement question per OUTPUT STRUCTURE **Optional close** when it adds value; **Coaching depth requested: yes** → **≤5** body sentences, **≤2** numbers if essential, constraint may span **2** sentences, plus optional engagement question — OUTPUT STRUCTURE — Progress check-in.",
        "- **Other topics:** weave priority metrics into **prose** (short paragraphs, bold key values) — not labeled stat lists unless the user asks for a breakdown.",
        "- **Saved `run_summary_priority` metrics override generic level/tone limits for those metrics on the structured card and in tool payloads** — not as an excuse to dump every metric into **`content`** (Insight + Facts still applies).",
        "- Tools always return the full data payload. Shape your **presentation** based on the preferences above — never omit calling a tool.",
        f"- Allowed metric names: {', '.join(ALLOWED_METRICS)}.",
        "- If the user asks to change preferences, call `save_coach_preference`.",
    ]
    return "\n".join(lines)


def _device_anchor_system_section(
    anchor_local_date: str, client_timezone: Optional[str]
) -> str:
    tz_display = (client_timezone or "").strip() or "unknown"
    return (
        f'## Device context (authoritative calendar "today")\n'
        f"- The user's local calendar date on their phone right now is **{anchor_local_date}** (IANA timezone: {tz_display}).\n"
        f'- For "how was my run?", "my run", "this run", "today", or whenever they do not name a specific day **and** are **not** clearly continuing a **different** run you already named (e.g. a marathon date) in the **prior assistant** message, '
        f"call `find_runs_by_date` with `local_date` exactly **{anchor_local_date}**.\n"
        f'- If they **just** asked about a **past** run you identified by **name/date** and now say **"how did I do?"** / **"how was it?"** / similar, **do not** default to **{anchor_local_date}** — resolve that run via **`find_runs_by_date`** on the **date from your prior reply** or **`search_runs`** again, then **`get_run_summary`**.\n'
        f"- Only use a different `local_date` when the user clearly refers to another day (or use the rules above for thread continuation).\n"
        f"- Never ask the user to specify the date for vague **today**-style questions; use **{anchor_local_date}** when that rule applies."
    )


def _hr_calibration_system_section(session: Session, internal_user_id: str) -> str:
    """Inject HR calibration status so coaching can guide data collection."""
    profile = get_user_profile(session, internal_user_id) or {}
    calibration = HRMaxResolutionService.get_hr_calibration_status(profile)
    if calibration.get("status") != "uncalibrated":
        return ""

    reason_code = calibration.get("reason_code")
    user_hint = calibration.get("user_hint") or hr_calibration_reason_user_hint(
        reason_code if isinstance(reason_code, str) else None
    )

    return (
        "## HR calibration status\n"
        "- The user's HR profile is currently **uncalibrated** for effective max-HR-based zones.\n"
        f"- Reason code: **{reason_code or 'UNKNOWN'}**.\n"
        f"- Coaching hint (use or paraphrase; do not contradict): {user_hint}\n"
        f"- Qualifying runs with HR so far: **{calibration.get('qualifying_activity_count', 0)}**.\n"
        f"- Minimum required runs: **{calibration.get('min_activities_required', 5)}**.\n"
        f"- Runs still needed: **{calibration.get('activities_needed', 0)}**.\n"
        f"- Minimum run duration to qualify: **{calibration.get('min_activity_duration_minutes', 10)} minutes**.\n"
        "- If HR zones/intensity guidance is discussed, explicitly explain calibration is still in progress.\n"
        "- Recommend practical data-collection runs: include some sustained harder efforts "
        "(tempo, threshold intervals, hills, or race effort), not only easy runs.\n"
        "- Keep this supportive and actionable; avoid implying user failure."
    )


def _thread_led_system_section(ctx: DerivedThreadCoachContext) -> str:
    """
    Injected once per turn from derived history (no DB flags).
    Omitted when there is no structured run_summary in prior messages.
    """
    if not ctx.prior_run_summary_in_thread:
        return ""
    lines = [
        "## Thread-led coach context (authoritative for this request)",
        "Derived from stored chat only. When continuity here conflicts with re-stating the same run opener, follow this section.",
    ]
    if ctx.last_structured_run_activity_id is not None:
        lines.append(
            f"- **Most recent structured run in thread:** `activity_id` **{ctx.last_structured_run_activity_id}** "
            "(from the newest `run_summary` payload in this chat). Re-call tools if you need fresh numbers; do not invent a different id."
        )
    else:
        lines.append(
            "- A structured **`run_summary`** exists earlier in this chat, but **`activity_id` was not recoverable** from saved payloads. "
            "Re-resolve the run with **DATA RETRIEVAL & TOOL RULES** (`find_runs_by_date` / `search_runs`, then `get_run_summary`)."
        )
    lines.extend(
        [
            "- **Same-run follow-ups:** **Sentence 1** must respond to the **user's latest message** (continuity, empathy, or the specific tension) — **not** a fresh distance/pace/HR/duration recap unless they explicitly ask to recap, repeat stats, or ask for numbers.",
            "- **Information budget:** Add **at most one** new tool-grounded fact in the opening when it is **strictly needed** for what they just asked; otherwise avoid re-narrating the same run story the card and prior insight already covered.",
        ]
    )
    if not ctx.last_assistant_was_run_summary:
        lines.append(
            "- **Note:** The latest assistant message may **not** be a run card — still apply the bullets above when they are clearly continuing the same run topic."
        )
    return "\n".join(lines) + "\n"


def _intent_priority_override_section(intent: str) -> str:
    """Intent-aware hard overrides that can supersede base prompt defaults."""
    if intent != "race_projection":
        return ""
    return (
        "## Intent priority override: race_projection\n"
        "- Primary objective: answer the marathon prediction request directly and keep projection as the centerpiece.\n"
        "- Tool priority: call `get_marathon_projection` first for prediction asks.\n"
        "- Do not call `get_weekly_training_insight` or long KPI trend tools unless the user explicitly asks for detailed trend analysis.\n"
        "- If the user asks a compound question (prediction + trends), provide projection first and limit trend context to one short sentence.\n"
        "- Avoid report-style sections like 'Running Trends' / 'Insight' for this intent unless explicitly requested.\n"
        "- Present scenario times and paces in **woven prose** or a **very short** list — not a long templated report.\n"
    )


def _plan_creation_system_section(
    user_message: str,
    intent: str,
    thread_ctx: Any,
) -> str:
    msg = (user_message or "").lower()
    intake_state = (
        thread_ctx.latest_plan_intake_state
        if hasattr(thread_ctx, "latest_plan_intake_state")
        else None
    )
    active = (
        intent == "plan_creation"
        or isinstance(intake_state, dict)
        or any(
            k in msg
            for k in (
                "create a plan",
                "build a plan",
                "training plan",
                "plan for",
                "help me train",
                "make me a plan",
            )
        )
    )
    if not active:
        return ""

    lines = [
        "## Plan creation flow (deterministic intake + deterministic generation)",
        "- When this turn is about creating/updating a plan, always use tool `update_plan_intake` to capture the latest user details.",
        "- Ask only one missing required field at a time (race date, race distance, goal type, training days, target_time only when goal is Target Time).",
        "- Do not claim details are saved unless `update_plan_intake` confirms them.",
        "- When `ready_to_generate=true`, present the confirmation summary and ask for explicit yes/no.",
        "- Call `generate_training_plan` only after explicit confirmation, with `confirm=true`.",
        "- Keep user-facing wording natural; the tool payload is the source of truth for intake state.",
    ]
    if isinstance(intake_state, dict):
        lines.extend(
            [
                "- Current deterministic intake state (from prior turn payload):",
                "```json",
                json.dumps(
                    {
                        "status": intake_state.get("status"),
                        "missing_required": intake_state.get("missing_required"),
                        "ready_to_generate": intake_state.get("ready_to_generate"),
                        "confirmation_summary": intake_state.get(
                            "confirmation_summary"
                        ),
                    },
                    default=str,
                ),
                "```",
            ]
        )
    return "\n".join(lines)


def _valid_run_summary_tool_payload(out: Any) -> Optional[Dict[str, Any]]:
    """Success shape from get_run_summary — has facts for RunSummaryCard; exclude error stubs."""
    if not isinstance(out, dict) or out.get("error"):
        return None
    facts = out.get("facts")
    if not isinstance(facts, dict):
        return None
    return out


def run_mobile_agent_turn(
    session: Session,
    internal_user_id: str,
    conversation_history: List[Dict[str, str]],
    user_message: str,
    *,
    anchor_local_date: str,
    client_timezone: Optional[str] = None,
    eval_model_override: Optional[str] = None,
    last_activity_id_hint: Optional[int] = None,
) -> Tuple[Union[str, Dict[str, Any]], Dict[str, Any]]:
    """
    Returns (assistant_reply, metadata with usage, cost, loops).

    `assistant_reply` is either a plain string or a structured dict:
    ``{"type": "run_summary", "content": str, "data": {...}}`` when get_run_summary succeeded this turn.

    anchor_local_date: YYYY-MM-DD from the mobile device (or server fallback); grounds "today".
    eval_model_override: optional OpenAI model id (e.g. gpt-4o-mini) when HTTP layer allows it
        for scripted eval only — normally unset.
    """
    service = get_openai_service()
    model = eval_model_override or os.getenv("OPENAI_CONVERSATION_MODEL", "gpt-4o")
    temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
    max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", "2000"))
    # Per completion (httpx/OpenAI). Default 180s — deploys that still use Gunicorn's 30s
    # worker default need headroom on multi-step tool turns. Cap with OPENAI_MOBILE_AGENT_TIMEOUT.
    timeout = float(os.getenv("OPENAI_MOBILE_AGENT_TIMEOUT", "180.0"))

    t_agent0 = time.perf_counter()
    openai_tools = _ensure_generate_training_plan_tool(
        _ensure_update_plan_intake_tool(
            _ensure_get_run_splits_tool(
                _ensure_get_marathon_projection_tool(
                    _ensure_get_training_kpis_tool(
                        _ensure_aggregate_runs_in_range_tool(
                            _ensure_search_runs_tool(_load_tools_from_db(session))
                        )
                    )
                )
            )
        )
    )
    if not openai_tools:
        logger.warning("No enabled tools in coach_tools table; agent has no tools")

    t_after_tools = time.perf_counter()
    prefs = _load_coaching_preferences(session, internal_user_id)
    thread_ctx = derive_thread_coach_context(conversation_history)
    turn_type = classify_turn(user_message, conversation_history)
    conversation_state = extract_conversation_state(conversation_history)
    response_directive = plan_response(
        turn_type=turn_type,
        state=conversation_state,
        user_message=user_message,
        conversation_history=conversation_history,
    )
    logger.info(
        "[dialogue] turn_type=%s intent=%s interaction_mode=%s investigate_first=%s turn_count=%s last_topic=%s avoid_repeat=%s target_length=%s",
        response_directive.turn_type,
        response_directive.intent,
        response_directive.interaction_mode,
        response_directive.investigate_first,
        conversation_state.turn_count,
        conversation_state.last_topic,
        ",".join(response_directive.avoid_repeating_metrics) or "none",
        response_directive.target_length,
    )

    # --- Prompt experiment (optional): see MINIMAL_SYSTEM_PROMPT_BASE block above ---
    use_min_base = _env_experiment_minimal_flag("SMARTCOACH_EXPERIMENT_MINIMAL_BASE")
    use_min_prefs = _env_experiment_minimal_flag("SMARTCOACH_EXPERIMENT_MINIMAL_PREFS")
    use_min_directive = _env_experiment_minimal_flag(
        "SMARTCOACH_EXPERIMENT_MINIMAL_DIRECTIVE"
    )
    if use_min_base or use_min_prefs or use_min_directive:
        logger.info(
            "[coach_prompt_experiment] user=%s… minimal_base=%s minimal_prefs=%s minimal_directive=%s",
            str(internal_user_id)[:8],
            use_min_base,
            use_min_prefs,
            use_min_directive,
        )

    base_block = MINIMAL_SYSTEM_PROMPT_BASE if use_min_base else SYSTEM_PROMPT_BASE
    prefs_block = "" if use_min_prefs else _coaching_preferences_section(prefs)
    directive_block = (
        _experiment_response_directive_stub(response_directive)
        if use_min_directive
        else response_directive_section(response_directive)
    )
    system_content = _join_nonempty_system_sections(
        base_block,
        prefs_block,
        _device_anchor_system_section(anchor_local_date, client_timezone),
        _hr_calibration_system_section(session, internal_user_id),
        directive_block,
        _thread_led_system_section(thread_ctx),
        _intent_priority_override_section(response_directive.intent),
        _plan_creation_system_section(
            user_message,
            response_directive.intent,
            thread_ctx,
        ),
    )
    messages: List[Dict[str, Any]] = [{"role": "system", "content": system_content}]
    for m in conversation_history[-12:]:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_message.strip()})

    t_after_prep = time.perf_counter()
    timings_ms: Dict[str, Any] = {
        "setup_tools_ms": round((t_after_tools - t_agent0) * 1000, 2),
        "prep_dialogue_messages_ms": round((t_after_prep - t_after_tools) * 1000, 2),
    }
    loop_details: List[Dict[str, Any]] = []

    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    total_cost = 0.0
    loops = 0
    tool_result_cache: Dict[tuple, Dict[str, Any]] = {}
    max_loops = _max_agent_loops()
    latest_run_summary: Optional[Dict[str, Any]] = None
    latest_plan_intake_state: Optional[Dict[str, Any]] = (
        thread_ctx.latest_plan_intake_state
        if isinstance(thread_ctx.latest_plan_intake_state, dict)
        else None
    )
    latest_plan_generation: Optional[Dict[str, Any]] = None

    recap_decision = decide_run_recap_fastpath(user_message, conversation_history)
    timings_ms["run_recap_fastpath_gate"] = {
        "eligible": recap_decision.eligible,
        "reason_code": recap_decision.reason_code,
        "prior_user_turns": recap_decision.prior_user_turn_count,
    }

    prefetch: Optional[Dict[str, Any]] = None
    if recap_decision.eligible:
        _tp0 = time.perf_counter()
        prefetch = prefetch_opening_anchor_run_recap(
            session, internal_user_id, anchor_local_date
        )
        timings_ms["fastpath_prefetch_ms"] = round(
            (time.perf_counter() - _tp0) * 1000, 2
        )
        if prefetch:
            logger.info(
                "[coach_fastpath] run_recap_opening user=%s… activity_id=%s gate=%s comparisons=%s week_volume=%s",
                str(internal_user_id)[:8],
                prefetch["activity_id"],
                recap_decision.reason_code,
                len(prefetch.get("comparison_for_llm") or []),
                1 if prefetch.get("week_volume_for_llm") else 0,
            )

    if prefetch:
        augmented_system = system_content + system_appendix_for_prefetch(
            prefetch, anchor_local_date
        )
        cc_messages: List[Dict[str, str]] = [
            {"role": "system", "content": augmented_system}
        ]
        for m in conversation_history[-12:]:
            if m.get("role") in ("user", "assistant") and m.get("content"):
                cc_messages.append(
                    {
                        "role": str(m["role"]),
                        "content": str(m.get("content", "")).strip(),
                    }
                )
        cc_messages.append({"role": "user", "content": user_message.strip()})
        try:
            _t_llm0 = time.perf_counter()
            _fp_cap = int(
                os.getenv("SMARTCOACH_RUN_RECAP_FASTPATH_MAX_TOKENS", "768") or "0"
            )
            _fp_max_tokens = min(max_tokens, _fp_cap) if _fp_cap > 0 else max_tokens
            cc_result = service.chat_completion(
                messages=cc_messages,
                user_id=str(internal_user_id),
                model=model,
                temperature=temperature,
                max_tokens=_fp_max_tokens,
                timeout=timeout,
            )
            timings_ms["fastpath_llm_ms"] = round(
                (time.perf_counter() - _t_llm0) * 1000, 2
            )
        except Exception:
            logger.exception(
                "[coach_fastpath] chat_completion failed; using full agent loop"
            )
        else:
            text_fp = (cc_result.content or "").strip()
            ok_payload = _valid_run_summary_tool_payload(prefetch["get_run_summary"])
            completions_for_usage: List[Any] = [cc_result]

            if (
                not text_fp
                and run_recap_fastpath_retry_on_empty_enabled()
                and ok_payload is not None
            ):
                augmented_retry = augmented_system + RUN_RECAP_FASTPATH_RETRY_APPENDIX
                cc_retry: List[Dict[str, str]] = [
                    {"role": "system", "content": augmented_retry}
                ]
                for m in conversation_history[-12:]:
                    if m.get("role") in ("user", "assistant") and m.get("content"):
                        cc_retry.append(
                            {
                                "role": str(m["role"]),
                                "content": str(m.get("content", "")).strip(),
                            }
                        )
                cc_retry.append({"role": "user", "content": user_message.strip()})
                try:
                    _t_r0 = time.perf_counter()
                    cc_result_retry = service.chat_completion(
                        messages=cc_retry,
                        user_id=str(internal_user_id),
                        model=model,
                        temperature=min(temperature, 0.35),
                        max_tokens=_fp_max_tokens,
                        timeout=timeout,
                    )
                    timings_ms["fastpath_retry_llm_ms"] = round(
                        (time.perf_counter() - _t_r0) * 1000, 2
                    )
                    completions_for_usage.append(cc_result_retry)
                    text_fp = (cc_result_retry.content or "").strip()
                    logger.info(
                        "[coach_fastpath] run_recap_empty_retry user=%s… len=%s",
                        str(internal_user_id)[:8],
                        len(text_fp),
                    )
                except Exception:
                    logger.exception(
                        "[coach_fastpath] retry chat_completion failed; using full agent loop"
                    )

            if text_fp and ok_payload is not None:
                for res in completions_for_usage:
                    for k in total_usage:
                        total_usage[k] += res.usage.get(k, 0)
                    total_cost += res.cost
                loops = 1
                timings_ms["agent_loop_rounds"] = []
                timings_ms["agent_orchestrator_total_ms"] = round(
                    (time.perf_counter() - t_agent0) * 1000, 2
                )
                meta_fp: Dict[str, Any] = {
                    "usage": total_usage,
                    "cost": total_cost,
                    "loops": loops,
                    "max_loops": max_loops,
                    "model": model,
                    "run_recap_fastpath": True,
                    "timings_ms": timings_ms,
                    "dialogue": {
                        "turn_type": response_directive.turn_type,
                        "intent": response_directive.intent,
                        "turn_count": conversation_state.turn_count,
                        "last_topic": conversation_state.last_topic,
                        "target_length": response_directive.target_length,
                        "narration_mode": response_directive.narration_mode,
                        "tool_strategy": response_directive.tool_strategy,
                        "avoid_repeating_metrics": response_directive.avoid_repeating_metrics,
                        "allow_full_recap": response_directive.allow_full_recap,
                        "investigate_first": response_directive.investigate_first,
                        "interaction_mode": response_directive.interaction_mode,
                        "thread_derived": thread_ctx.as_dict(),
                    },
                }
                structured_fp = {
                    "type": "run_summary",
                    "content": text_fp,
                    "data": ok_payload,
                }
                logger.info(
                    "[smartcoach_mobile_coach] response_shape=run_summary "
                    "loops=%s fastpath=1 content_len=%s timings_ms=%s",
                    loops,
                    len(text_fp),
                    timings_ms,
                )
                return structured_fp, meta_fp
            logger.warning(
                "[coach_fastpath] empty model text or invalid summary; using full agent loop"
            )

    split_prefetch: Optional[Dict[str, Any]] = None
    if wants_split_detail_fastpath(response_directive.intent):
        _sp0 = time.perf_counter()
        split_prefetch = prefetch_split_detail(
            session,
            internal_user_id,
            anchor_local_date,
            last_activity_id_hint=last_activity_id_hint,
            thread_activity_id=thread_ctx.last_structured_run_activity_id,
        )
        timings_ms["split_fastpath_prefetch_ms"] = round(
            (time.perf_counter() - _sp0) * 1000, 2
        )
        if split_prefetch:
            logger.info(
                "[coach_fastpath] split_detail user=%s… activity_id=%s source=%s",
                str(internal_user_id)[:8],
                split_prefetch.get("activity_id"),
                split_prefetch.get("resolved_from"),
            )

    if split_prefetch:
        augmented_system = system_content + system_appendix_for_split_prefetch(
            split_prefetch, anchor_local_date
        )
        cc_messages: List[Dict[str, str]] = [
            {"role": "system", "content": augmented_system}
        ]
        for m in conversation_history[-12:]:
            if m.get("role") in ("user", "assistant") and m.get("content"):
                cc_messages.append(
                    {
                        "role": str(m["role"]),
                        "content": str(m.get("content", "")).strip(),
                    }
                )
        cc_messages.append({"role": "user", "content": user_message.strip()})
        try:
            _t_sllm0 = time.perf_counter()
            _sp_cap = int(
                os.getenv("SMARTCOACH_SPLIT_DETAIL_FASTPATH_MAX_TOKENS", "1024") or "0"
            )
            _sp_max_tokens = min(max_tokens, _sp_cap) if _sp_cap > 0 else max_tokens
            cc_result = service.chat_completion(
                messages=cc_messages,
                user_id=str(internal_user_id),
                model=model,
                temperature=temperature,
                max_tokens=_sp_max_tokens,
                timeout=timeout,
            )
            timings_ms["split_fastpath_llm_ms"] = round(
                (time.perf_counter() - _t_sllm0) * 1000, 2
            )
        except Exception:
            logger.exception(
                "[coach_fastpath] split_detail chat_completion failed; using full agent loop"
            )
        else:
            text_fp = (cc_result.content or "").strip()
            if text_fp:
                for k in total_usage:
                    total_usage[k] = cc_result.usage.get(k, 0)
                total_cost = cc_result.cost
                loops = 1
                timings_ms["agent_loop_rounds"] = []
                timings_ms["agent_orchestrator_total_ms"] = round(
                    (time.perf_counter() - t_agent0) * 1000, 2
                )
                meta_fp: Dict[str, Any] = {
                    "usage": total_usage,
                    "cost": total_cost,
                    "loops": loops,
                    "max_loops": max_loops,
                    "model": model,
                    "split_detail_fastpath": True,
                    "timings_ms": timings_ms,
                    "dialogue": {
                        "turn_type": response_directive.turn_type,
                        "intent": response_directive.intent,
                        "turn_count": conversation_state.turn_count,
                        "last_topic": conversation_state.last_topic,
                        "target_length": response_directive.target_length,
                        "narration_mode": response_directive.narration_mode,
                        "tool_strategy": response_directive.tool_strategy,
                        "avoid_repeating_metrics": response_directive.avoid_repeating_metrics,
                        "allow_full_recap": response_directive.allow_full_recap,
                        "investigate_first": response_directive.investigate_first,
                        "interaction_mode": response_directive.interaction_mode,
                        "thread_derived": thread_ctx.as_dict(),
                    },
                }
                logger.info(
                    "[smartcoach_mobile_coach] response_shape=text "
                    "loops=%s split_fastpath=1 content_len=%s timings_ms=%s",
                    loops,
                    len(text_fp),
                    timings_ms,
                )
                return text_fp, meta_fp
            logger.warning(
                "[coach_fastpath] split_detail empty model text; using full agent loop"
            )

    for _ in range(max_loops):
        loops += 1
        t_openai0 = time.perf_counter()
        result = service.chat_completion_with_tools(
            messages=messages,
            user_id=str(internal_user_id),
            tools=openai_tools if openai_tools else None,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        openai_ms = round((time.perf_counter() - t_openai0) * 1000, 2)
        loop_entry: Dict[str, Any] = {
            "loop": loops,
            "openai_ms": openai_ms,
            "tools": [],
        }

        for k in total_usage:
            total_usage[k] += result.usage.get(k, 0)
        total_cost += result.cost

        if result.tool_calls:
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": None,
                "tool_calls": [],
            }
            for tc in result.tool_calls:
                assistant_msg["tool_calls"].append(
                    {
                        "id": tc["id"],
                        "type": tc.get("type") or "function",
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"],
                        },
                    }
                )
            messages.append(assistant_msg)

            for tc in result.tool_calls:
                fn = tc["function"]
                name = fn["name"]
                arguments = fn["arguments"] or "{}"
                sig = (name, arguments)
                if sig in tool_result_cache:
                    out = tool_result_cache[sig]
                    loop_entry["tools"].append(
                        {"name": name, "ms": 0.0, "cached": True}
                    )
                else:
                    tt0 = time.perf_counter()
                    out = execute_tool(
                        session,
                        internal_user_id,
                        name,
                        arguments,
                        anchor_local_date=anchor_local_date,
                        plan_intake_state=latest_plan_intake_state,
                    )
                    tool_result_cache[sig] = out
                    loop_entry["tools"].append(
                        {
                            "name": name,
                            "ms": round((time.perf_counter() - tt0) * 1000, 2),
                            "cached": False,
                        }
                    )
                if name in ("get_run_summary", "get_run_insight"):
                    ok_payload = _valid_run_summary_tool_payload(out)
                    if ok_payload is not None:
                        latest_run_summary = ok_payload
                if name in ("update_plan_intake", "generate_training_plan"):
                    pis = out.get("plan_intake_state")
                    if isinstance(pis, dict):
                        latest_plan_intake_state = pis
                    pg = out.get("plan_generation")
                    if isinstance(pg, dict):
                        latest_plan_generation = pg
                _tj0 = time.perf_counter()
                tool_content = json.dumps(out)
                loop_entry["tools"][-1]["json_serialize_ms"] = round(
                    (time.perf_counter() - _tj0) * 1000, 2
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": tool_content,
                    }
                )
            loop_details.append(loop_entry)
            continue

        if result.content is not None:
            text = (result.content or "").strip()
            loop_details.append(loop_entry)
            timings_ms["agent_loop_rounds"] = loop_details
            timings_ms["agent_orchestrator_total_ms"] = round(
                (time.perf_counter() - t_agent0) * 1000, 2
            )
            meta: Dict[str, Any] = {
                "usage": total_usage,
                "cost": total_cost,
                "loops": loops,
                "max_loops": max_loops,
                "model": model,
                "timings_ms": timings_ms,
                "dialogue": {
                    "turn_type": response_directive.turn_type,
                    "intent": response_directive.intent,
                    "turn_count": conversation_state.turn_count,
                    "last_topic": conversation_state.last_topic,
                    "target_length": response_directive.target_length,
                    "narration_mode": response_directive.narration_mode,
                    "tool_strategy": response_directive.tool_strategy,
                    "avoid_repeating_metrics": response_directive.avoid_repeating_metrics,
                    "allow_full_recap": response_directive.allow_full_recap,
                    "investigate_first": response_directive.investigate_first,
                    "interaction_mode": response_directive.interaction_mode,
                    "thread_derived": thread_ctx.as_dict(),
                },
            }
            if latest_run_summary is not None:
                structured = {
                    "type": "run_summary",
                    "content": text,
                    "data": latest_run_summary,
                }
                logger.info(
                    "[smartcoach_mobile_coach] response_shape=run_summary loops=%s content_len=%s",
                    loops,
                    len(text),
                )
                return structured, meta
            if text:
                if (
                    latest_plan_intake_state is not None
                    or latest_plan_generation is not None
                ):
                    structured_text: Dict[str, Any] = {
                        "type": "text",
                        "content": text,
                        "data": {},
                    }
                    if latest_plan_intake_state is not None:
                        structured_text["data"][
                            "plan_intake_state"
                        ] = latest_plan_intake_state
                    if latest_plan_generation is not None:
                        structured_text["data"][
                            "plan_generation"
                        ] = latest_plan_generation
                    return structured_text, meta
                return text, meta

    fallback = (
        "I couldn't complete that within the allowed steps. Try asking about one run at a time, "
        "or try again in a moment."
    )
    timings_ms["agent_loop_rounds"] = loop_details
    timings_ms["agent_orchestrator_total_ms"] = round(
        (time.perf_counter() - t_agent0) * 1000, 2
    )
    return fallback, {
        "usage": total_usage,
        "cost": total_cost,
        "loops": loops,
        "max_loops": max_loops,
        "truncated": True,
        "model": model,
        "timings_ms": timings_ms,
        "dialogue": {
            "turn_type": response_directive.turn_type,
            "intent": response_directive.intent,
            "turn_count": conversation_state.turn_count,
            "last_topic": conversation_state.last_topic,
            "target_length": response_directive.target_length,
            "narration_mode": response_directive.narration_mode,
            "tool_strategy": response_directive.tool_strategy,
            "avoid_repeating_metrics": response_directive.avoid_repeating_metrics,
            "allow_full_recap": response_directive.allow_full_recap,
            "investigate_first": response_directive.investigate_first,
            "interaction_mode": response_directive.interaction_mode,
            "thread_derived": thread_ctx.as_dict(),
        },
    }
