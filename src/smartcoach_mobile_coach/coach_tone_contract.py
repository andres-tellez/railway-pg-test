"""
Versioned coach tone contract for the system prompt (V1.6 §§19.6–19.8).

**Purpose (3C.5 + 3C.6 + 3C.7).** Three tone rules that govern what the
coach must *say at the end of every turn*, what *must lead the first
sentence* on an unplanned run, and how the overall tone must *shift
with weekly adherence*. Bundled together because they all operate on
the **response shape** (not on what tool to call or what KPI to read)
and drift together when the spec moves.

* **§19.6 Action-oriented coaching** — every coaching response MUST
  include a concrete next action OR a guiding question; analysis-only
  responses are forbidden, with five carve-outs pinned to real
  :mod:`dialogue_manager` enums.
* **§19.7 Unplanned run acknowledgment** — first-sentence
  acknowledgment when ``plan_status = unplanned``; stronger rest-day
  framing when ``violated_rest_day = true`` (coaches the consequence,
  does not moralize).
* **§19.8 Adherence-informed tone** — tone bands low / medium / high
  driven by ``adherence_runs_pct`` thresholds from §7.

**Single source of truth.** The block mirrors
``docs/SMARTCOACH_SYSTEM_SPEC_V1.md`` §§19.6–19.8 verbatim. Exempt
classification strings for §19.6 are sourced **from the live
:mod:`dialogue_manager` enums** at import time so the prompt and the
classifier stay in lockstep — contract tests assert equality.

The block is emitted once per turn after :mod:`plan_guidance_contract`.
Plan-creation mode skips it: intake turns run their own restricted
prompt and do not carry a "coaching response" shape.
"""

from __future__ import annotations

from src.smartcoach_mobile_coach.dialogue_manager import (
    INTENT_PREFERENCE_UPDATE,
    MODE_AMBIGUOUS,
    MODE_FACTUAL,
    TURN_ACKNOWLEDGMENT,
    TURN_CLARIFICATION,
)

COACH_TONE_CONTRACT_VERSION = 1


def _build_block() -> str:
    """Assemble the contract block, interpolating live enum values.

    Keeping enum strings derived from :mod:`dialogue_manager` (rather
    than re-typing them) guarantees that spec ↔ classifier ↔ prompt
    cannot drift: if an enum is renamed, the prompt updates
    automatically and the drift tests in
    :mod:`tests.test_coach_tone_contract` still pass.
    """
    return (
        "## Coach tone contract (V1.6 §§19.6–19.8)\n"
        f"<!-- coach_tone_contract_version: {COACH_TONE_CONTRACT_VERSION} -->\n"
        "\n"
        "### §19.6 Action-oriented coaching\n"
        "Every coaching response **must** include either a concrete "
        "**next action** (*\"Run Tuesday's Tempo at 8:30/mi, hold Z3 on "
        'the main block"*) **or** a **guiding question** (*"Did '
        "anything feel off during yesterday's Long Run?\"*). "
        "**Analysis-only responses are forbidden.**\n"
        "\n"
        "**Exempt classifications** (real enums from `dialogue_manager.py` "
        "— the action-or-question rule does **not** apply):\n"
        "\n"
        f'- `turn_type == "{TURN_ACKNOWLEDGMENT}"` — user is affirming / '
        "thanking → minimal response.\n"
        f'- `turn_type == "{TURN_CLARIFICATION}"` — user is asking what '
        "the coach meant → clarify concisely.\n"
        f'- `interaction_mode == "{MODE_FACTUAL}"` — factual snapshot '
        '(*"what was my avg HR?"*) → answer with the number.\n'
        f'- `interaction_mode == "{MODE_AMBIGUOUS}"` — investigate-first '
        "gate → exactly **one clarifying question** this turn.\n"
        f'- `intent == "{INTENT_PREFERENCE_UPDATE}"` — acknowledge the '
        "saved preference.\n"
        "\n"
        "All other classifications (opening, follow_up, drill_down, "
        "new_topic; clear_coaching / experiential modes) carry the "
        "requirement.\n"
        "\n"
        "### §19.7 Unplanned run acknowledgment\n"
        "When `plan_status = unplanned`, the **first sentence** must "
        "explicitly acknowledge that the run was not in the plan. Example "
        "phrasings:\n"
        "\n"
        "- *\"This run wasn't on today's plan — here's how it looks.\"*\n"
        "- *\"You added a run today that wasn't scheduled. Let's break it "
        'down."*\n'
        "\n"
        "When `violated_rest_day = true`, apply **stronger emphasis** on "
        "rest-day intent: frame the trade-off (recovery debt, risk to the "
        "next quality session). **Coach the consequence — do not moralize.**\n"
        "\n"
        "### §19.8 Adherence-informed tone\n"
        "Adapt tone to the `adherence_runs_pct` band (§7):\n"
        "\n"
        "- **low** (`< 70 %`) — **supportive, non-judgmental**; consistency "
        "over performance; propose volume reduction per §16.\n"
        "- **medium** (`70 %–90 %`) — **steady reinforcement**; acknowledge "
        "what's working; hold load.\n"
        "- **high** (`> 90 %`) — **progression-ready**; may surface "
        "next-level discussion within §16 caps.\n"
    )


COACH_TONE_CONTRACT_BLOCK = _build_block()


def coach_tone_contract_section() -> str:
    """Return the §§19.6–19.8 tone contract block for the system prompt.

    Safe to include unconditionally on non-plan-creation turns. The
    plan-creation branch uses its own restricted prompt and should NOT
    include this block: plan-intake responses do not yet have an
    adherence band, a plan_status, or a coaching "next action" to
    enforce.
    """
    return COACH_TONE_CONTRACT_BLOCK
