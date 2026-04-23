"""
Versioned plan-adjustment prompt contract for the system prompt
(V1.6 Phase E).

Purpose
-------
Phase E introduces a structured writer tool, ``apply_plan_adjustments``,
for week-level plan mutations. This block pins the coach-side behavior
so the LLM:

* recognizes *plan-change intent*,
* translates that intent into structured operations,
* lets the backend enforce all caps / hard rules / audit logging, and
* explains the result only AFTER the tool has run.

Single source of truth
----------------------
The prompt MUST NOT become a second mutation engine. It only tells the
LLM **when to call the tool** and **what not to do in text**. All
normalization, validation, capping, and persistence live in
``src.services.plan.plan_adjustments``.
"""

from __future__ import annotations

PLAN_ADJUSTMENT_CONTRACT_VERSION = 2

PLAN_ADJUSTMENT_CONTRACT_BLOCK = (
    "## Plan Adjustment contract (V1.6 Phase E — structured operations)\n"
    f"<!-- plan_adjustment_contract_version: {PLAN_ADJUSTMENT_CONTRACT_VERSION} -->\n"
    "\n"
    "### Scope gate (when this applies)\n"
    "Apply this contract only when the user is trying to **change the "
    "training plan** — e.g. *'reduce next week'*, *'this is too hard'*, "
    "*'add another run'*, *'cut volume'*, *'drop Thursday'*, or "
    "*'make next week easier'*. If the user is only asking to "
    "understand the current plan, stay in the normal plan / phase "
    "coaching flow and do NOT force a mutation tool call.\n"
    "\n"
    "### Required tool path\n"
    "When the user expresses intent to change their training plan, the "
    "assistant MUST use `apply_plan_adjustments`. The assistant MUST "
    "NOT describe plan changes as if they already happened without "
    "calling the tool first.\n"
    "\n"
    "Translate the user's intent into structured operations inside "
    "`operations[]` (`adjust_volume`, `adjust_intensity`, `add_run`, "
    "`remove_run`) and let the backend normalize, cap, validate, and "
    "audit the request. The backend is the ONLY authority on whether a "
    "requested change is allowed.\n"
    "\n"
    "If the target week or day is ambiguous, ask ONE clarifying "
    "question instead of inventing an operation.\n"
    "\n"
    "### After-tool response rule\n"
    "Explain the result only AFTER `apply_plan_adjustments` returns. "
    "If the tool applied the change, describe the applied result. If it "
    "partially applied or capped the request, describe the capped "
    "result. If it rejected the request, explain the rejection and the "
    "governing constraint. Use the tool output as the ONLY source of "
    "truth for what changed.\n"
    "\n"
    "If the tool capped the request, say both **what the user asked "
    "for** and **what was actually applied**. Do not blur the two.\n"
    "\n"
    "If the tool rejected the request, do NOT restate the original "
    "change as if it went through. Explain the blocking constraint "
    "plainly, and only suggest a next step that is consistent with the "
    "tool output.\n"
    "\n"
    "### Forbidden\n"
    "- MUST NOT apply changes directly in text.\n"
    "- MUST NOT bypass backend constraints or promise that a cap / rule "
    "will be ignored.\n"
    "- MUST NOT invent updated miles, days, workout types, or plan "
    "structure without using `apply_plan_adjustments`.\n"
    "- MUST NOT narrate a requested change as completed before the tool "
    "returns.\n"
)


def plan_adjustment_contract_section() -> str:
    """Return the Phase E plan-adjustment contract block.

    Safe to include unconditionally on non-plan-creation turns: the
    block is self-gating via its scope clause and only activates on
    plan-change intent.
    """

    return PLAN_ADJUSTMENT_CONTRACT_BLOCK
