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

**Single source of truth.** The §§19.6–19.8 block mirrors
``docs/SMARTCOACH_SYSTEM_SPEC_V1.md`` §§19.6–19.8 verbatim. Exempt
classification strings for §19.6 are sourced **from the live
:mod:`dialogue_manager` enums** at import time so the prompt and the
classifier stay in lockstep — contract tests assert equality.

A separate **coach turn prose shape** block (same module) aligns LLM
Markdown with the mobile app's ``CoachTurnSections`` order — prompt
only; not JSON. It is emitted immediately after the tone contract on
non-plan-creation turns.

The §§19.6–19.8 block is emitted once per turn after
:mod:`plan_guidance_contract`. Plan-creation mode skips it: intake
turns run their own restricted prompt and do not carry a "coaching
response" shape.
"""

from __future__ import annotations

from src.smartcoach_mobile_coach.dialogue_manager import (
    INTENT_PREFERENCE_UPDATE,
    MODE_AMBIGUOUS,
    MODE_FACTUAL,
    TURN_ACKNOWLEDGMENT,
    TURN_CLARIFICATION,
)

# V1.6 Phase D 3D.10 bump: removed raw-threshold language from the §19.8
# tone block. The block now keys off the ``adherence_band`` field name
# (``low`` / ``medium`` / ``high``) without re-stating the `< 70 %` /
# `70 %–90 %` / `> 90 %` cut-offs, which live in the §7 producer and
# must not be duplicated in the prompt. Spec ↔ prompt drift tests
# exercise the new phrasing and its single-source-of-truth pointer.
COACH_TONE_CONTRACT_VERSION = 3


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
        "Apply **only** when authoritative tool / preloaded JSON for **this** "
        "activity shows `plan_status` is the string **`unplanned`** (see "
        "`facts.execution_summary.plan_status` or compact `plan_status` when "
        "present). Then the **first sentence** must briefly acknowledge the "
        "run was not on the plan (one short clause).\n"
        "\n"
        "If `plan_status` is **anything else** or **absent**, do **not** open "
        'with off-plan framing — no "wasn\'t scheduled", "wasn\'t on the plan", '
        '"added a run", or similar; that reads as a data error.\n'
        "\n"
        "Example (**unplanned only**): *\"This run wasn't on today's plan — "
        "here's the read.\"*\n"
        "\n"
        "When `violated_rest_day = true`, apply **stronger emphasis** on "
        "rest-day intent: frame the trade-off (recovery debt, risk to the "
        "next quality session). **Coach the consequence — do not moralize.**\n"
        "\n"
        "### §19.8 Adherence-informed tone\n"
        "Read the **`adherence_band`** field directly — it is the "
        "canonical `low` / `medium` / `high` classification produced by "
        "the §7 adherence service. **Do not re-derive** the band from "
        "`adherence_runs_pct`: the numeric cut-offs live in §7 and the "
        "band field is the only prompt-side source of truth.\n"
        "\n"
        "- **`adherence_band = low`** — **supportive, non-judgmental**; "
        "consistency over performance; propose volume reduction per §16.\n"
        "- **`adherence_band = medium`** — **steady reinforcement**; "
        "acknowledge what's working; hold load.\n"
        "- **`adherence_band = high`** — **progression-ready**; may "
        "surface next-level discussion within §16 caps.\n"
        "- **`adherence_band = null`** — band not yet classifiable "
        "(insufficient evaluable runs). Stay neutral-supportive; do NOT "
        "invent a band.\n"
    )


COACH_TONE_CONTRACT_BLOCK = _build_block()

# ---------------------------------------------------------------------------
# Coach turn prose shape (LLM ↔ mobile CoachTurnSections; prompt-only)
# ---------------------------------------------------------------------------
#
# Centralized here next to the tone contract so orchestrator composes
# one import site. Do not duplicate this block in orchestrator.py.
#
# Version 2 changes:
# - Avoid duplicating metrics already shown in cards/tool output
# - Add soft sentence target (3–5 sentences)
# - Only include a closing question when appropriate
#
# Prevents accidental regressions later.

COACH_TURN_PROSE_SHAPE_VERSION = 2


def _build_coach_turn_prose_shape_block() -> str:
    return (
        "## Coach turn prose shape (conceptual; mobile alignment)\n"
        f"<!-- coach_turn_prose_shape_version: {COACH_TURN_PROSE_SHAPE_VERSION} -->\n"
        "\n"
        "Shape user-visible coaching text **in the same conceptual order** as the mobile app's "
        "`CoachTurnSections` (**alignment only** — keep **plain Markdown** in `content` / the "
        "assistant message; **do not** emit JSON, field names, or a separate schema for this "
        "shape).\n"
        "\n"
        "**Order (woven prose — not labeled section headers in the reply):**\n"
        "\n"
        "1. **Interpretation** — **one sentence**: your coach read (judgment, reaction, or "
        "athletic meaning). **No stats in this sentence** when a RunSummaryCard already shows "
        "headline metrics; elsewhere follow OUTPUT STRUCTURE on sentence-1 rules. Do **not** "
        "restate a **full** metrics lineup in this sentence when the same headline numbers are "
        "already on a **structured card** or clearly **provided separately** (e.g. tool output "
        "the athlete already sees); let the card / prior context carry the digits.\n"
        "\n"
        "2. **Grounding** — **one or two short sentences** with **tool-verified facts** when "
        "they sharpen the read. Do **not** invent numbers; skip when facts would only repeat "
        "the card or add nothing.\n"
        "\n"
        "3. **Nudge** *(optional)* — **at most one sentence** of small coaching refinement or "
        "next focus when it adds value; omit when interpretation + grounding already land.\n"
        "\n"
        "4. **Close** *(optional)* — **one short question** only when it fits the interaction "
        "and OUTPUT STRUCTURE allows an optional close. **Do not** force a question for "
        "**purely informational** replies (straight factual asks, bare acknowledgments, or "
        "when the user only needed a number or label). Omit when a question would feel generic, "
        "tacked on, or add no real decision leverage.\n"
        "\n"
        "**Brevity:** Aim for roughly **3–5 sentences** for the **whole** reply unless this turn "
        "clearly needs more (user asked for depth, OUTPUT STRUCTURE depth mode, or "
        "investigation-first / ambiguity handling needs more beats). Shorter is fine when the "
        "answer is already complete.\n"
        "\n"
        "Continue to obey **OUTPUT STRUCTURE**, numeric caps, §19.6 action-or-question rules, "
        "and investigation-first gates — this names the **voice shape** so LLM replies feel "
        "consistent with deterministic coach copy on the client.\n"
        "\n"
        "**Example (illustrative — teaches the shape; real replies stay unlabeled prose):**\n"
        "\n"
        "- **Interpretation:** *Solid control — you weren't chasing splits on the climbs.*\n"
        "- **Grounding:** *Drift stayed in band B; the last two miles steadied after a messy middle.*\n"
        "- **Nudge (optional):** *Next time on this loop, ease 5–10 sec/mi into the long rise so HR settles earlier.*\n"
        "- **Close (optional):** *Was that middle wobble a pacing choice or the legs talking?*\n"
        "\n"
        "*(Four short beats — within the usual 3–5 sentence budget; weave as plain paragraphs in "
        "`content` and omit nudge or close when they would not help.)*\n"
    )


COACH_TURN_PROSE_SHAPE_BLOCK = _build_coach_turn_prose_shape_block()


def coach_tone_contract_section() -> str:
    """Return the §§19.6–19.8 tone contract block for the system prompt.

    Safe to include unconditionally on non-plan-creation turns. The
    plan-creation branch uses its own restricted prompt and should NOT
    include this block: plan-intake responses do not yet have an
    adherence band, a plan_status, or a coaching "next action" to
    enforce.
    """
    return COACH_TONE_CONTRACT_BLOCK


def coach_turn_prose_shape_section() -> str:
    """Return CoachTurnSections-aligned prose guidance for the system prompt.

    Injected in :mod:`orchestrator` immediately after
    :func:`coach_tone_contract_section` on non-plan-creation turns.
    """
    return COACH_TURN_PROSE_SHAPE_BLOCK
