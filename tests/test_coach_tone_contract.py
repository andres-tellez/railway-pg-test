"""
V1.6 Phase C 3C.5 + 3C.6 + 3C.7 — coach tone contract tests.

Locks the §§19.6–19.8 prompt section against
``docs/SMARTCOACH_SYSTEM_SPEC_V1.md`` AND against the live
:mod:`dialogue_manager` enums so spec ↔ classifier ↔ prompt cannot
silently drift.

Scope:

* version tag wiring,
* spec-header anchors for each of the three sub-sections,
* §19.6 action-or-question rule verbatim, "analysis-only forbidden"
  anchor, and **all five exempt classifications** sourced from the
  live ``dialogue_manager`` enums,
* §19.7 first-sentence acknowledgment + explicit `plan_status` gate + one example,
  ``violated_rest_day`` stronger-emphasis rule, "coach the
  consequence — do not moralize" anchor,
* §19.8 all three adherence bands with their thresholds and tone
  prescriptions, §16 cross-reference for volume reduction + caps,
* payload budget (< 2 KB),
* orchestrator wiring (non-plan-creation, after
  :func:`plan_guidance_contract_section`, not in plan-creation).
"""

from __future__ import annotations

import pytest

from src.smartcoach_mobile_coach import coach_tone_contract
from src.smartcoach_mobile_coach.coach_tone_contract import (
    COACH_TONE_CONTRACT_BLOCK,
    COACH_TONE_CONTRACT_VERSION,
    COACH_TURN_PROSE_SHAPE_BLOCK,
    COACH_TURN_PROSE_SHAPE_VERSION,
    coach_tone_contract_section,
    coach_turn_prose_shape_section,
)
from src.smartcoach_mobile_coach.dialogue_manager import (
    INTENT_PREFERENCE_UPDATE,
    MODE_AMBIGUOUS,
    MODE_FACTUAL,
    TURN_ACKNOWLEDGMENT,
    TURN_CLARIFICATION,
)


# ---------------------------------------------------------------------------
# Version tag & module surface
# ---------------------------------------------------------------------------


def test_contract_version_is_int_and_v3() -> None:
    # v2: §19.8 re-keyed on `adherence_band`. v3: §19.7 explicit gate +
    # removed second example phrasing. Bump on future spec edits.
    assert isinstance(COACH_TONE_CONTRACT_VERSION, int)
    assert COACH_TONE_CONTRACT_VERSION == 3


def test_version_tag_appears_in_block() -> None:
    assert (
        f"<!-- coach_tone_contract_version: {COACH_TONE_CONTRACT_VERSION} -->"
        in COACH_TONE_CONTRACT_BLOCK
    )


def test_section_fn_returns_the_block_verbatim() -> None:
    assert coach_tone_contract_section() is COACH_TONE_CONTRACT_BLOCK


def test_module_surface_exports_expected_names() -> None:
    assert hasattr(coach_tone_contract, "COACH_TONE_CONTRACT_BLOCK")
    assert hasattr(coach_tone_contract, "COACH_TONE_CONTRACT_VERSION")
    assert hasattr(coach_tone_contract, "coach_tone_contract_section")
    assert hasattr(coach_tone_contract, "COACH_TURN_PROSE_SHAPE_BLOCK")
    assert hasattr(coach_tone_contract, "COACH_TURN_PROSE_SHAPE_VERSION")
    assert hasattr(coach_tone_contract, "coach_turn_prose_shape_section")


# ---------------------------------------------------------------------------
# Payload budget
# ---------------------------------------------------------------------------


def test_contract_block_is_non_empty_string() -> None:
    assert isinstance(COACH_TONE_CONTRACT_BLOCK, str)
    assert COACH_TONE_CONTRACT_BLOCK.strip()


def test_coach_turn_prose_shape_version_tag_and_section() -> None:
    assert isinstance(COACH_TURN_PROSE_SHAPE_VERSION, int)
    assert COACH_TURN_PROSE_SHAPE_VERSION == 2
    assert (
        f"<!-- coach_turn_prose_shape_version: {COACH_TURN_PROSE_SHAPE_VERSION} -->"
        in COACH_TURN_PROSE_SHAPE_BLOCK
    )
    assert "## Coach turn prose shape" in COACH_TURN_PROSE_SHAPE_BLOCK
    assert coach_turn_prose_shape_section() is COACH_TURN_PROSE_SHAPE_BLOCK


def test_coach_turn_prose_shape_block_fits_prompt_budget_under_3kb() -> None:
    size = len(COACH_TURN_PROSE_SHAPE_BLOCK.encode("utf-8"))
    assert size < 3072, f"prose shape block grew to {size} bytes"


def test_contract_block_fits_prompt_budget_under_3kb() -> None:
    # V1.6 Phase D 3D.10: budget raised from 2 KB to 3 KB to fit the
    # expanded §19.8 single-source-of-truth clause and the new
    # `adherence_band = null` row. The block is still one of the
    # highest-weight per-turn instructions, so it stays bounded — if a
    # future edit grows it past 3 KB, trim (or split into its own
    # contract module) rather than bumping the budget again.
    size = len(COACH_TONE_CONTRACT_BLOCK.encode("utf-8"))
    assert size < 3072, f"contract grew to {size} bytes; trim before merging"


# ---------------------------------------------------------------------------
# Section headers
# ---------------------------------------------------------------------------


def test_section_header_anchors_19_6_through_19_8() -> None:
    assert "## Coach tone contract (V1.6 §§19.6–19.8)" in COACH_TONE_CONTRACT_BLOCK


@pytest.mark.parametrize(
    "header",
    [
        "### §19.6 Action-oriented coaching",
        "### §19.7 Unplanned run acknowledgment",
        "### §19.8 Adherence-informed tone",
    ],
)
def test_every_subheader_is_present(header: str) -> None:
    assert header in COACH_TONE_CONTRACT_BLOCK


# ---------------------------------------------------------------------------
# §19.6 — action-oriented coaching
# ---------------------------------------------------------------------------


def test_action_or_question_rule_anchored() -> None:
    # Both the "next action" and "guiding question" anchors must survive
    # prose edits; the spec is explicit that either is acceptable.
    assert "**next action**" in COACH_TONE_CONTRACT_BLOCK
    assert "**guiding question**" in COACH_TONE_CONTRACT_BLOCK


def test_concrete_action_example_present() -> None:
    # §19.6 uses this specific example; keep it verbatim so the LLM
    # sees what a "concrete" next action looks like.
    assert "Run Tuesday's Tempo at 8:30/mi" in COACH_TONE_CONTRACT_BLOCK


def test_concrete_question_example_present() -> None:
    assert (
        "Did anything feel off during yesterday's Long Run?"
        in COACH_TONE_CONTRACT_BLOCK
    )


def test_analysis_only_forbidden_anchor() -> None:
    assert "**Analysis-only responses are forbidden.**" in COACH_TONE_CONTRACT_BLOCK


def test_exempt_header_anchor() -> None:
    assert "**Exempt classifications**" in COACH_TONE_CONTRACT_BLOCK


def test_exempt_classifications_cite_dialogue_manager_as_source() -> None:
    # Anchors the single source of truth: whatever the prompt says
    # about exemption names, it got them from dialogue_manager.py.
    assert "`dialogue_manager.py`" in COACH_TONE_CONTRACT_BLOCK


@pytest.mark.parametrize(
    "descriptor,literal",
    [
        ("turn_type", TURN_ACKNOWLEDGMENT),
        ("turn_type", TURN_CLARIFICATION),
        ("interaction_mode", MODE_FACTUAL),
        ("interaction_mode", MODE_AMBIGUOUS),
        ("intent", INTENT_PREFERENCE_UPDATE),
    ],
)
def test_exempt_classification_uses_live_enum_value(
    descriptor: str, literal: str
) -> None:
    """The prompt text MUST contain the exact enum string literal.

    This is the anti-drift guarantee: if ``dialogue_manager`` renames
    one of these classifications, the prompt block (built at import
    time from the enum values) updates automatically, and this test
    still passes. If somebody bypasses the dynamic builder and
    hard-codes a wrong literal, the test fails.
    """
    assert f'`{descriptor} == "{literal}"`' in COACH_TONE_CONTRACT_BLOCK


def test_ambiguous_mode_carves_out_exactly_one_clarifying_question() -> None:
    # §19.6 is explicit: ambiguous mode returns ONE clarifying question,
    # not multiple and not a prescription. Preserve the numeric anchor.
    assert "one clarifying question" in COACH_TONE_CONTRACT_BLOCK


def test_non_exempt_classifications_still_carry_requirement() -> None:
    # opening / follow_up / drill_down / new_topic, clear_coaching,
    # experiential must all remain inside the action-or-question rule.
    for anchor in (
        "opening",
        "follow_up",
        "drill_down",
        "new_topic",
        "clear_coaching",
        "experiential",
    ):
        assert (
            anchor in COACH_TONE_CONTRACT_BLOCK
        ), f"non-exempt classification anchor {anchor!r} missing from block"


# ---------------------------------------------------------------------------
# §19.7 — unplanned run acknowledgment
# ---------------------------------------------------------------------------


def test_unplanned_plan_status_anchor() -> None:
    assert "`unplanned`" in COACH_TONE_CONTRACT_BLOCK
    assert "plan_status" in COACH_TONE_CONTRACT_BLOCK


def test_first_sentence_acknowledgment_rule_anchored() -> None:
    # The wording "first sentence" is load-bearing: §19.7 requires the
    # acknowledgment at the top of the response, not buried later.
    assert "**first sentence**" in COACH_TONE_CONTRACT_BLOCK


def test_unplanned_example_phrasing_present() -> None:
    assert "This run wasn't on today's plan" in COACH_TONE_CONTRACT_BLOCK


def test_unplanned_removed_scheduled_example() -> None:
    assert (
        "You added a run today that wasn't scheduled" not in COACH_TONE_CONTRACT_BLOCK
    )


def test_unplanned_gate_requires_explicit_plan_status() -> None:
    assert "anything else" in COACH_TONE_CONTRACT_BLOCK
    assert "absent" in COACH_TONE_CONTRACT_BLOCK


def test_violated_rest_day_anchor() -> None:
    assert "`violated_rest_day = true`" in COACH_TONE_CONTRACT_BLOCK


def test_violated_rest_day_framing_is_consequence_based() -> None:
    # §19.7 is explicit that the coach frames the trade-off (recovery
    # debt, risk to the next quality session) rather than moralizing.
    assert "recovery debt" in COACH_TONE_CONTRACT_BLOCK
    assert "next quality session" in COACH_TONE_CONTRACT_BLOCK


def test_do_not_moralize_anchor_present() -> None:
    # Specific anti-behavior from §19.7. The coach's job is to explain
    # the consequence, not judge the choice.
    assert "Coach the consequence — do not moralize." in COACH_TONE_CONTRACT_BLOCK


# ---------------------------------------------------------------------------
# §19.8 — adherence-informed tone
# ---------------------------------------------------------------------------


def test_adherence_band_field_is_the_source_of_truth() -> None:
    # V1.6 Phase D 3D.10: the tone block now keys off the
    # `adherence_band` field name (the canonical classifier output),
    # NOT the raw `adherence_runs_pct` percentage. Ensures the prompt
    # matches the single-source-of-truth rule (§X.5): one producer
    # (`src.services.scoring.adherence`), one field name in the
    # prompt, no re-derivation.
    assert "`adherence_band`" in COACH_TONE_CONTRACT_BLOCK


def test_tone_block_does_not_re_state_raw_thresholds() -> None:
    # Hard deprecation lock for 3D.10: the tone block MUST NOT carry
    # the raw `< 70 %` / `70 %–90 %` / `> 90 %` cut-offs. Those live in
    # §7 only — duplicating them in the prompt is exactly the drift
    # pattern the Phase D work set out to eliminate. Any re-
    # introduction of the thresholds fails this test loudly.
    for forbidden in ("< 70 %", "70 %–90 %", "> 90 %", "70 % – 90 %"):
        assert forbidden not in COACH_TONE_CONTRACT_BLOCK, (
            f"raw threshold '{forbidden}' re-introduced into coach tone "
            "contract; Phase D 3D.10 deprecated these — read the "
            "`adherence_band` field instead."
        )


def test_tone_block_has_explicit_no_re_derive_clause() -> None:
    # Closes the loophole where the prompt still mentions the percent
    # field and lets the LLM "re-derive" the band mentally. The
    # 3D.10 clause explicitly forbids re-derivation and names the
    # `adherence_band` field as the only prompt-side truth.
    block_lower = COACH_TONE_CONTRACT_BLOCK.lower()
    assert "do not re-derive" in block_lower
    assert "canonical" in block_lower


@pytest.mark.parametrize(
    "band,tone",
    [
        ("low", "supportive, non-judgmental"),
        ("medium", "steady reinforcement"),
        ("high", "progression-ready"),
    ],
)
def test_adherence_band_row_has_name_and_tone(band: str, tone: str) -> None:
    # V1.6 Phase D 3D.10: each row carries the field-scoped band name
    # (e.g. ``adherence_band = low``) and its tone prescription.
    # Dropping either half would leave the coach guessing at runtime,
    # even under the new field-based phrasing.
    assert f"`adherence_band = {band}`" in COACH_TONE_CONTRACT_BLOCK
    assert tone in COACH_TONE_CONTRACT_BLOCK


def test_adherence_band_null_row_is_present() -> None:
    # V1.6 Phase D 3D.10: the `null` band (insufficient evaluable
    # runs) now has an explicit row. Without it the LLM either
    # silences itself or invents a band — both violate §19.8.
    assert "`adherence_band = null`" in COACH_TONE_CONTRACT_BLOCK
    assert "neutral-supportive" in COACH_TONE_CONTRACT_BLOCK
    assert "do NOT invent" in COACH_TONE_CONTRACT_BLOCK


def test_low_adherence_band_proposes_volume_reduction_per_19_16() -> None:
    # §19.8 low-band prescription routes to §16 adaptation caps.
    # Keeping the cross-reference keeps the tone work and the
    # adaptation work in lockstep.
    assert "volume reduction per §16" in COACH_TONE_CONTRACT_BLOCK


def test_high_adherence_band_references_19_16_caps() -> None:
    assert "§16 caps" in COACH_TONE_CONTRACT_BLOCK


# ---------------------------------------------------------------------------
# Orchestrator wiring
# ---------------------------------------------------------------------------


def test_orchestrator_imports_contract_section() -> None:
    from src.smartcoach_mobile_coach import orchestrator

    assert hasattr(orchestrator, "coach_tone_contract_section")
    assert orchestrator.coach_tone_contract_section is coach_tone_contract_section
    assert hasattr(orchestrator, "coach_turn_prose_shape_section")
    assert orchestrator.coach_turn_prose_shape_section is coach_turn_prose_shape_section


def test_orchestrator_source_wires_contract_into_non_plan_creation_branch() -> None:
    # The tone contract must be composed exactly once in the non-plan-
    # creation branch, AFTER plan_guidance_contract_section (so phase
    # emphasis + future-week rules precede response-shape rules, which
    # are the final layer before preferences and device anchor).
    from pathlib import Path

    src = Path("src/smartcoach_mobile_coach/orchestrator.py").read_text(
        encoding="utf-8"
    )
    assert src.count("coach_tone_contract_section()") == 1
    assert src.count("coach_turn_prose_shape_section()") == 1
    guidance_idx = src.index("plan_guidance_contract_section()")
    tone_idx = src.index("coach_tone_contract_section()")
    prose_idx = src.index("coach_turn_prose_shape_section()")
    assert guidance_idx < tone_idx < prose_idx, (
        "coach_turn_prose_shape_section must be composed AFTER "
        "coach_tone_contract_section (and after plan_guidance)"
    )


def test_orchestrator_does_not_wire_contract_into_plan_creation_branch() -> None:
    # Plan-creation turns do not have a plan_status, adherence band, or
    # coaching "next action" to enforce — the tone contract has no
    # meaning during intake and should not bloat that prompt.
    from pathlib import Path

    src = Path("src/smartcoach_mobile_coach/orchestrator.py").read_text(
        encoding="utf-8"
    )
    plan_creation_base_idx = src.index("PLAN_CREATION_SYSTEM_PROMPT_BASE")
    tone_idx = src.index("coach_tone_contract_section()")
    assert plan_creation_base_idx < tone_idx, (
        "coach_tone_contract_section() must be wired in the non-plan-"
        "creation else block"
    )
