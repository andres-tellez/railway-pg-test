"""
Minimal prompt builder for Run Review Lab mode.

Lab mode deliberately avoids rubric/shape contracts. It provides data and one
short grounding instruction so we can observe the model's "raw" coaching style.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from src.smartcoach_mobile_coach.run_review.context import RunReviewContext


def _single_run_instructions() -> str:
    return (
        "Tone and style:\n"
        "- Talk like a **real coach** 1:1—warm, plain-spoken, encouraging. "
        "Use **you** and simple words (*kept it easy*, *stayed controlled*, "
        "*solid effort*), not analyst-speak (*commendable*, *compliance with*, "
        "*aerobic efficiency*, *this indicates*).\n"
        "- **Compact:** 4–6 short paragraphs, 1–2 sentences each, about **90–140 "
        "words** total. Cut filler openers and hedges; go straight to the point.\n"
        "- **Dates:** when comparing to a prior run, prefer friendly relative "
        "phrasing (*last week*, *a week ago*, *earlier this week*) when the gap "
        "is obvious from the JSON; use a calendar date only if it would confuse "
        "the reader.\n\n"
        "**Do not recap the RunSummary card.** The athlete already sees headline "
        "stats there (distance, time, pace, core HR, zone mix, and the HR drift "
        "chip). Those card-level fields are intentionally reduced in the JSON below; "
        "do **not** invent or re-state them. Prefer: Evidence Pack / similar-run "
        "comparisons, **planned intent** fit, phase or plan context from "
        "`coach_snapshot`, and a concise takeaway."
    )


def _splits_only_instructions() -> str:
    return (
        "This turn is **split / per-mile detail** on the run already in thread.\n\n"
        "Tone and style:\n"
        "- Warm, plain-spoken coach voice—answer what they asked about laps/miles.\n"
        "- **Compact:** about **60–110 words** unless they asked for every mile listed.\n"
        "- Use a short bullet or numbered list when listing multiple split rows.\n\n"
        "**Splits are the focus.** Use `run_context.splits` rows as source of truth. "
        "Quote **`avg_heart_rate_display`**, **`avg_pace_display`**, and "
        "`segment_label` **exactly** as shown. Respect **`splits_truncated`**: only "
        "discuss returned laps; do not invent middle miles.\n\n"
        "**Do not** repeat a full session recap or RunSummary card headlines unless "
        "the user explicitly asked for recap context."
    )


def build_run_review_lab_appendix(
    *,
    ctx: RunReviewContext,
    coach_snapshot: Optional[Dict[str, Any]],
    scope: Optional[str] = None,
) -> str:
    effective_scope = (scope or ctx.scope or "single_run").strip()
    payload: Dict[str, Any] = {"run_context": ctx.to_compact_dict(for_llm=True)}
    if isinstance(coach_snapshot, dict):
        payload["coach_snapshot"] = coach_snapshot
    if effective_scope == "splits_only":
        heading = "## Run splits (lab mode)"
        body = _splits_only_instructions()
    else:
        heading = "## Run review (lab mode)"
        body = _single_run_instructions()
    return (
        f"\n{heading}\n"
        "Use the JSON below as the source of truth for this run. "
        "Do not invent numbers; if data is missing, say what is unknown.\n\n"
        f"{body}\n\n"
        "```json\n"
        f"{json.dumps(payload, default=str)}\n"
        "```"
    )


def build_messages(
    *,
    base_system_content: str,
    ctx: RunReviewContext,
    coach_snapshot: Optional[Dict[str, Any]],
    conversation_history: List[Dict[str, str]],
    user_message: str,
    history_window: int,
) -> List[Dict[str, str]]:
    augmented_system = (base_system_content or "") + build_run_review_lab_appendix(
        ctx=ctx,
        coach_snapshot=coach_snapshot,
        scope=ctx.scope,
    )
    messages: List[Dict[str, str]] = [{"role": "system", "content": augmented_system}]
    if conversation_history:
        for m in conversation_history[-history_window:]:
            role = m.get("role")
            content = m.get("content")
            if (
                role in ("user", "assistant")
                and isinstance(content, str)
                and content.strip()
            ):
                messages.append({"role": str(role), "content": content.strip()})
    messages.append({"role": "user", "content": (user_message or "").strip()})
    return messages
