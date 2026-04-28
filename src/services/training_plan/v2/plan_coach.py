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
    weeks = plan.get("weeks") or (context.validation or {}).get("draft", {}).get(
        "weeks", []
    )
    phases_present = sorted(
        {str(w.get("phase")).strip() for w in weeks if w.get("phase")}
    )
    has_peak_phase = "Peak" in phases_present
    peak_phase_evidence = insights.get("peak_phase_evidence")

    summary = insights.get("summary", {})
    long_run = insights.get("long_run", {})
    validation = insights.get("validation", {})
    spine_quality = insights.get("spine_quality", {})

    validation_ctx = context.validation or {}
    violations = validation_ctx.get("violations") or []
    spine_quality_issues = list(context.spine_quality_issues or [])
    decision_trace = context.decision_trace
    if decision_trace is None:
        decision_trace = validation_ctx.get("decision_trace") or []
    decision_trace = list(decision_trace)

    from src.domain.running.terminology import WORKOUT_DEFINITIONS

    system_instructions = (
        "You are a running coach. "
        "Explain plans using only the provided data. "
        "When explaining the plan, prefer using decision_trace and validation "
        "signals below. Do not rely on generic explanations. "
        "Use training_invariants (product policy names from "
        "src.domain.running.invariants) to connect structure to rules—without "
        "deriving numeric thresholds unless they already appear in insights. "
        "Do NOT compute new metrics. "
        "Do NOT invent facts. "
        "If something is not in the data, say you don't know."
    )
    if has_peak_phase:
        system_instructions += (
            " You MUST reference training_invariants.when_discussing_peak_phase when "
            "explaining long runs in Peak phase."
        )
    if peak_phase_evidence:
        system_instructions += (
            " When you relate Peak long runs to training invariants, use "
            "peak_phase_evidence.max_long_run and peak_phase_evidence.min_long_run "
            "exactly as given—do not recompute or re-derive them from progression "
            "arrays, week lists, or other context."
        )

    tasks = [
        "Provide a concise summary of the plan.",
        "Explain why the long run progresses as it does.",
        "If decision_trace is non-empty, reference specific entries (field, source, rationale, values) when you explain why the plan is shaped this way.",
        "If spine_quality_issues is non-empty, mention those issues and their impact on the schedule or risk.",
        "If validation.violations is non-empty, explain the runner-facing impact of notable violations; if empty, do not invent problems.",
    ]
    if has_peak_phase:
        if peak_phase_evidence:
            tasks.append(
                "MANDATORY: Include at least one bullet that references "
                "training_invariants.when_discussing_peak_phase and names "
                "PEAK_LONG_RUN_MIN_FRACTION_OF_PEAK_BLOCK_MAX for Peak-phase long runs. "
                "That bullet MUST use peak_phase_evidence.max_long_run and "
                "peak_phase_evidence.min_long_run exactly as given (do not recompute "
                "from long_run.progression, week lists, or other context). Do not skip "
                "this bullet. Do not compute mile thresholds from the invariant constant "
                "itself."
            )
        else:
            tasks.append(
                "MANDATORY: Include at least one bullet that references "
                "training_invariants.when_discussing_peak_phase and names "
                "PEAK_LONG_RUN_MIN_FRACTION_OF_PEAK_BLOCK_MAX when describing Peak-phase "
                "long runs. peak_phase_evidence is absent—do not require or invent "
                "numeric Peak-block max/min miles; explain the invariant in words only "
                "(no derived mile evidence). Do not skip this bullet. Do not compute "
                "mile thresholds from the invariant constant itself."
            )
    tasks.append("Give one actionable recommendation for the runner.")

    return {
        "system_instructions": system_instructions,
        "context": {
            "summary": summary,
            "long_run": {
                "progression": long_run.get("progression"),
                "first_three_weeks": long_run.get("first_three_weeks"),
            },
            "validation": validation,
            "spine_quality": spine_quality,
            "reasoning_signals": {
                "validation": {
                    "violations": violations,
                },
                "spine_quality_issues": spine_quality_issues,
                "decision_trace": decision_trace,
            },
            "terminology": dict(WORKOUT_DEFINITIONS),
            "plan_structure_hints": {
                "phases_present": phases_present,
            },
            "peak_phase_evidence": peak_phase_evidence,
            "training_invariants": {
                "module": "src.domain.running.invariants",
                "when_discussing_peak_phase": (
                    "If you discuss the Peak phase (or this plan includes Peak—see "
                    "plan_structure_hints.phases_present), mention that Peak-week long "
                    "runs are kept at or above "
                    "PEAK_LONG_RUN_MIN_FRACTION_OF_PEAK_BLOCK_MAX of the **maximum "
                    "long run within the Peak block** (before taper)—i.e. the floor is "
                    "defined inside the Peak block, not from global Build/Base highs. "
                    "Use peak_phase_evidence.max_long_run and peak_phase_evidence."
                    "min_long_run (from plan_insights) as the provided Peak-block miles "
                    "when you explain the block; name the invariant constant but do "
                    "not state the constant's numeric factor unless the insights "
                    "payload already includes it."
                ),
            },
        },
        "tasks": tasks,
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
