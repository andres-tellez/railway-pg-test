"""
Minimal prompt builder for Run Review Lab mode.

Lab mode deliberately avoids rubric/shape contracts. It provides data and one
short grounding instruction so we can observe the model's "raw" coaching style.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from src.smartcoach_mobile_coach.run_review.context import RunReviewContext


def build_run_review_lab_appendix(
    *,
    ctx: RunReviewContext,
    coach_snapshot: Optional[Dict[str, Any]],
) -> str:
    payload: Dict[str, Any] = {"run_context": ctx.to_compact_dict(for_llm=True)}
    if isinstance(coach_snapshot, dict):
        payload["coach_snapshot"] = coach_snapshot
    return (
        "\n## Run review (lab mode)\n"
        "Use the JSON below as the source of truth for this run. "
        "Answer naturally as a coach. Do not invent numbers; if data is missing, "
        "say what is unknown.\n\n"
        "**Do not recap the RunSummary card.** The athlete already sees headline "
        "stats there (distance, time, pace, core HR, and the HR drift band chip). "
        "HR drift **percentage** and **band** are **not** included in the JSON below "
        "(on purpose)—do **not** invent them or open by restating the drift line. "
        "Other `training_kpis` fields (e.g. early/late HR, zone mix) are fair game "
        "when they support interpretation. Prefer: Evidence Pack / similar-run "
        "comparisons, **planned intent** fit, phase or plan context from "
        "`coach_snapshot`, and a concise takeaway.\n\n"
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
