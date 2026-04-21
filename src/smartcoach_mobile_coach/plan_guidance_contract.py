"""
Versioned phase-aware emphasis + future-week coaching contract for the
system prompt (V1.6 §§19.4–19.5).

**Purpose (3C.3 + 3C.4).** Phase A landed ``phase_kpi_priority`` and
``week_temporality`` as deterministic fields, and Phase B shipped the
plan-aware tools that carry them. Phase C wires the matching coach-side
prompt contract so the LLM:

* Weights its per-week narrative toward the top 1–2 entries in
  ``phase_kpi_priority`` (§19.4), and
* Talks about **intent / progression** only for future weeks — no
  outcome prediction, no invented actuals, no numbers that are not in
  the payload (§19.5).

Paired together because both operate on the *plan-side* reasoning
surface (what to emphasize when and what not to say about weeks that
have not happened yet) and drift as a unit when the spec changes.

**Single source of truth.** The block mirrors
``docs/SMARTCOACH_SYSTEM_SPEC_V1.md`` §§19.4–19.5 verbatim. When the
spec changes, bump :data:`PLAN_GUIDANCE_CONTRACT_VERSION` and update
the block; contract tests assert the version tag and every key phrase
so spec ↔ prompt drift fails CI.

The block is emitted once per turn as its own system-prompt section
after :mod:`plan_vs_actual_contract`. Plan-creation mode skips it —
there is no phase emphasis or future-week narrative to calibrate
during plan intake.
"""

from __future__ import annotations

PLAN_GUIDANCE_CONTRACT_VERSION = 1

# Spec-anchored. The per-phase table is the exact four-row mapping from
# SMARTCOACH_SYSTEM_SPEC_V1.md §19.4. Future-week rules carry the
# verbatim "may / must not" split from §19.5 so the coach has a clear
# allow-list and deny-list for weeks whose actuals do not exist yet.
PLAN_GUIDANCE_CONTRACT_BLOCK = (
    "## Phase emphasis & future-week contract (V1.6 §§19.4–19.5)\n"
    f"<!-- plan_guidance_contract_version: {PLAN_GUIDANCE_CONTRACT_VERSION} -->\n"
    "\n"
    "### §19.4 Phase-aware KPI emphasis\n"
    "Weight every per-week narrative toward the **top 1–2 entries** of the "
    "`phase_kpi_priority` list emitted by the plan tools (§8). Full KPI "
    "values are still in the payload, but the coach **talks primarily** "
    "about phase-appropriate metrics; everything else is drill-down only.\n"
    "\n"
    "- **Base** — emphasize **HR Drift**, **Aerobic Efficiency**, "
    "**Easy compliance**. De-emphasize Tempo consistency (not yet trained).\n"
    "- **Build** — emphasize **Pace Consistency**, **Quality compliance**. "
    "De-emphasize Maintenance framing (wrong phase).\n"
    "- **Peak** — emphasize **Execution**, **Fatigue consistency**. "
    "De-emphasize capacity-building language (already built).\n"
    "- **Taper** — emphasize **Maintenance**, **Recovery**. De-emphasize "
    "progression pushing (race is near).\n"
    "\n"
    "The list in `phase_kpi_priority` is **authoritative** — if it and "
    "the table above disagree for any reason, follow the list.\n"
    "\n"
    "### §19.5 Future-week contract\n"
    "For weeks with `week_temporality = future`, the coach **may** discuss:\n"
    "\n"
    "- **Intent** of upcoming runs (*why* Tempo sits here, *what* a Long "
    "Run is building).\n"
    "- **Progression** across the coming block (how next week differs "
    "from this one).\n"
    "- **Phase transitions** arriving in the next 1–2 weeks.\n"
    "\n"
    "The coach **must not**:\n"
    "\n"
    "- Predict outcomes (*\"you'll probably hit Tuesday's Tempo\"*).\n"
    '- Infer difficulty (*"this is going to feel hard"*).\n'
    "- Reference `actual.*` fields for a future week — they are absent "
    "by contract (§6 future-week payload) and may not be invented.\n"
    "- Provide pace or HR numbers that are not in the payload.\n"
)


def plan_guidance_contract_section() -> str:
    """Return the §§19.4–19.5 contract block for the system prompt.

    Safe to include unconditionally on non-plan-creation turns. The
    plan-creation branch uses its own restricted prompt and should NOT
    include this block: there is no phase emphasis to calibrate and no
    future-week narrative during plan intake.
    """
    return PLAN_GUIDANCE_CONTRACT_BLOCK
