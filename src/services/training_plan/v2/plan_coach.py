"""
Coach layer: LLM prompts for plan explanations.

Uses only system-provided ``PlanContext`` and ``insights`` payloads.
No plan recomputation; no metrics invented here.
"""

from __future__ import annotations

from typing import Any, Dict, Protocol, runtime_checkable

from src.services.training_plan.v2.plan_context import PlanContext


@runtime_checkable
class PlanCoachLLMClient(Protocol):
    """Minimal contract for ``generate_plan_explanation``."""

    def chat(self, *, system: str, user: str, temperature: float) -> str:
        """Return assistant text (plain string)."""


def build_coach_prompt(
    context: PlanContext, insights: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Returns a structured prompt payload for the LLM.
    """
    plan = context.detailed_plan or {}
    _ = plan.get("weeks") or (context.validation or {}).get("draft", {}).get(
        "weeks", []
    )

    summary = insights.get("summary", {})
    long_run = insights.get("long_run", {})
    validation = insights.get("validation", {})
    spine_quality = insights.get("spine_quality", {})

    from src.domain.running.terminology import WORKOUT_DEFINITIONS

    return {
        "system_instructions": (
            "You are a running coach. "
            "Explain plans using only the provided data. "
            "Do NOT compute new metrics. "
            "Do NOT invent facts. "
            "If something is not in the data, say you don't know."
        ),
        "context": {
            "summary": summary,
            "long_run": {
                "progression": long_run.get("progression"),
                "first_three_weeks": long_run.get("first_three_weeks"),
            },
            "validation": validation,
            "spine_quality": spine_quality,
            "terminology": dict(WORKOUT_DEFINITIONS),
        },
        "tasks": [
            "Provide a concise summary of the plan.",
            "Explain why the long run progresses as it does.",
            "Call out any notable validation or spine quality signals.",
            "Give one actionable recommendation for the runner.",
        ],
    }


def generate_plan_explanation(
    context: PlanContext,
    insights: Dict[str, Any],
    llm_client: PlanCoachLLMClient,
) -> str:
    """
    Calls the LLM with the structured prompt.

    ``llm_client`` must implement :meth:`PlanCoachLLMClient.chat` (e.g. a thin
    adapter around your OpenAI or other provider).
    """
    prompt = build_coach_prompt(context, insights)

    return llm_client.chat(
        system=prompt["system_instructions"],
        user=str(prompt["context"]) + "\nTasks:\n- " + "\n- ".join(prompt["tasks"]),
        temperature=0.2,
    )
