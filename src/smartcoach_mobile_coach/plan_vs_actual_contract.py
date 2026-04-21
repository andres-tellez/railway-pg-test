"""
Versioned plan-vs-actual coaching contract for the system prompt
(V1.6 §§19.2–19.3).

**Purpose (3C.1 + 3C.2).** The six deterministic fields landed in
Phase A and the plan-aware tools landed in Phase B. Phase C wires the
matching **coach-side** contract into the system prompt so the LLM
anchors every response in the plan and never mixes plan / actual
wording.

Two spec sections are paired here on purpose — they address the same
reasoning loop and drift together:

* **§19.2 Coach Reasoning Order** — ``PLAN → ACTUAL → GAP → ACTION``
  with special cases for ``plan_status ∈ {missed, unplanned}``.
* **§19.3 Language Separation** — distinct phrasing for plan, actual,
  and comparison, plus three forbidden collapses.

**Single source of truth.** The block here mirrors
``docs/SMARTCOACH_SYSTEM_SPEC_V1.md`` §§19.2–19.3. When the spec
changes, bump :data:`PLAN_VS_ACTUAL_CONTRACT_VERSION` and update the
block; the contract tests assert the version tag and every key phrase
so spec ↔ prompt drift fails CI.

The block is emitted once per turn as its own system-prompt section so
experiments (``SMARTCOACH_EXPERIMENT_MINIMAL_BASE`` etc.) keep it
regardless of which base is active, and plan-creation mode (which uses
a separate system prompt) is intentionally skipped — there is no plan
vs actual to reason about during plan intake.
"""

from __future__ import annotations

PLAN_VS_ACTUAL_CONTRACT_VERSION = 1

# Spec-anchored. Every canonical phrase from §19.2 and §19.3 appears
# verbatim so the LLM's surface wording matches the spec and contract
# tests can lock each anchor. Deliberately short — this section is
# one of the highest-weight per-turn instructions for the coach, so we
# keep the prose tight and avoid optional flourishes.
PLAN_VS_ACTUAL_CONTRACT_BLOCK = (
    "## Plan vs actual coaching contract (V1.6 §§19.2–19.3)\n"
    f"<!-- plan_vs_actual_contract_version: {PLAN_VS_ACTUAL_CONTRACT_VERSION} -->\n"
    "\n"
    "### §19.2 Reasoning order\n"
    "Anchor every response in the plan **before** the actual:\n"
    "\n"
    "**PLAN → ACTUAL (if present) → GAP → ACTION**\n"
    "\n"
    "- **PLAN** — what was scheduled for the run / day / week (type, miles, intent).\n"
    "- **ACTUAL** — what was executed (miles, executed type, HR, "
    "`deviation_direction`). Include **only** when `plan_status` is "
    "`executed` or `in_progress`.\n"
    "- **GAP** — the delta between plan and actual, phrased as a comparison.\n"
    "- **ACTION** — a concrete next step **or** a guiding question (§19.6).\n"
    "\n"
    "**Special cases.**\n"
    "- `plan_status = missed` → **PLAN** → *no ACTUAL* → **GAP = missed "
    "execution** → **ACTION** (recovery consideration, reschedule proposal, "
    "or context question).\n"
    "- `plan_status = unplanned` → *no PLAN* → **ACTUAL** → **GAP replaced "
    "by CONTEXT** (was the unplanned run aerobic / phase-appropriate?) → "
    "**ACTION**. First-sentence unplanned acknowledgment still applies (§19.7).\n"
    "\n"
    "Starting a response with the actual alone when a plan exists "
    '(e.g. *"Your run was 🟢 today"* with no plan anchor) **violates §19.2**.\n'
    "\n"
    "### §19.3 Language separation\n"
    "Never mix planned and actual wording. Use distinct phrasing for each:\n"
    "\n"
    '- **PLAN** — *"This was scheduled as…"*, *"Your Easy run today is '
    'planned for…"*.\n'
    '- **ACTUAL** — *"You ran…"*, *"Your execution was…"*.\n'
    '- **COMPARISON** — *"Compared to plan…"*, *"Versus the intended…"*.\n'
    "\n"
    "**Forbidden.**\n"
    "- Describing an **actual** outcome using the word *planned* "
    '(e.g. *"you planned a 5-mile run"* when referring to a completed run) '
    "— confuses intent with reality.\n"
    "- Describing a **plan** in the **past tense** (e.g. *"
    '"you ran an Easy on Tuesday"* for a future Tuesday) — future weeks '
    "have no actuals (§6 future-week contract).\n"
    "- Collapsing plan and actual into a single noun phrase "
    '(e.g. *"your 5-mile run"*) when the **executed miles differ from '
    "planned** — this hides the adherence gap.\n"
)


def plan_vs_actual_contract_section() -> str:
    """Return the versioned §§19.2–19.3 contract block for the system prompt.

    The block is self-contained and safe to include unconditionally in
    non-plan-creation turns. Plan-creation mode should NOT include it —
    during plan intake there is no plan-vs-actual to reason about, and
    the restricted plan-creation prompt is kept minimal.
    """
    return PLAN_VS_ACTUAL_CONTRACT_BLOCK
