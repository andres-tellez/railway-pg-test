"""Prompt builder for isolated coach response."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from src.smartcoach_mobile_coach.coach_response.context import CoachRunContext

COACH_RESPONSE_PROMPT_VERSION = "coach_response_v1_minimal"


def _base_coach_instruction() -> str:
    return (
        "You are SmartCoach, an expert running coach.\n"
        "- Use a warm, plain-spoken 1:1 coaching voice.\n"
        "- Teach, do not just recite metrics: explain what the facts mean and why it matters for training.\n"
        "- Ground every claim in the provided JSON facts only.\n"
        "- If data is missing, say what is unknown instead of guessing.\n"
    )


def _single_run_instruction() -> str:
    return (
        "Focus on interpretation and coaching takeaways. "
        "Do not repeat the headline run card values unless the user asks for them."
    )


def _splits_instruction() -> str:
    return (
        "This is a split-detail turn. Focus on early/mid/late patterns and coaching takeaways. "
        "Do not invent split rows or numbers that are not present in JSON."
    )


def build_appendix(
    *,
    ctx: CoachRunContext,
    coach_snapshot: Optional[Dict[str, Any]],
    scope: Optional[str] = None,
    splits_coaching_only: bool = False,
) -> str:
    effective_scope = (scope or ctx.scope or "single_run").strip()
    payload: Dict[str, Any] = {"run_context": ctx.to_compact_dict(for_llm=True)}
    if isinstance(coach_snapshot, dict):
        payload["coach_snapshot"] = coach_snapshot
    if effective_scope == "splits_only":
        heading = "## Run splits"
        body = _splits_instruction()
        if splits_coaching_only:
            body += " The server already renders exact per-lap values; provide coaching prose only."
    else:
        heading = "## Run review"
        body = _single_run_instruction()
    return (
        f"\n{heading}\n"
        f"{_base_coach_instruction()}\n"
        f"{body}\n\n"
        "```json\n"
        f"{json.dumps(payload, default=str)}\n"
        "```"
    )


def build_messages(
    *,
    base_system_content: str,
    ctx: CoachRunContext,
    coach_snapshot: Optional[Dict[str, Any]],
    conversation_history: List[Dict[str, str]],
    user_message: str,
    history_window: int,
    splits_coaching_only: bool = False,
) -> List[Dict[str, str]]:
    augmented_system = (base_system_content or "") + build_appendix(
        ctx=ctx,
        coach_snapshot=coach_snapshot,
        scope=ctx.scope,
        splits_coaching_only=splits_coaching_only,
    )
    messages: List[Dict[str, str]] = [{"role": "system", "content": augmented_system}]
    if conversation_history:
        for message in conversation_history[-history_window:]:
            role = message.get("role")
            content = message.get("content")
            if (
                role in ("user", "assistant")
                and isinstance(content, str)
                and content.strip()
            ):
                messages.append({"role": str(role), "content": content.strip()})
    messages.append({"role": "user", "content": (user_message or "").strip()})
    return messages
