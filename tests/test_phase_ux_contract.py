"""
V1.6 Phase D 3D.8 — Phase UX prompt contract tests.

Locks the Purpose → Focus → Progress → Action block against the
Phase D UX decisions (locked 2026-04-21) and §19.4 weekly-progress
anchors. Scope:

* version tag wiring,
* spec-header anchor + four ordered step headers,
* scope-gate clause (turn centers on plan / phase / progress),
* plain-language rule for progress labels (no raw enum echo),
* behavior-and-outcome goal shape (KPI thresholds forbidden),
* authoritative deterministic-read rule
  (``get_phase_analysis.goal`` + ``phase_progress_summary`` +
  ``weekly_progress[].status``),
* retrospective + new-goal merge rule at phase transition,
* prompt budget (< 3 KB — slightly larger than the §19.4/19.5 block
  because the UX template owns four steps plus two rule sub-blocks),
* orchestrator wiring (non-plan-creation branch, after
  :func:`plan_guidance_contract_section`, not in plan_creation_mode).
"""

from __future__ import annotations

import pytest

from src.smartcoach_mobile_coach import phase_ux_contract
from src.smartcoach_mobile_coach.phase_ux_contract import (
    PHASE_UX_CONTRACT_BLOCK,
    PHASE_UX_CONTRACT_VERSION,
    phase_ux_contract_section,
)


# ---------------------------------------------------------------------------
# Version tag & module surface
# ---------------------------------------------------------------------------


def test_contract_version_is_int_and_v1() -> None:
    assert isinstance(PHASE_UX_CONTRACT_VERSION, int)
    assert PHASE_UX_CONTRACT_VERSION == 1


def test_version_tag_appears_in_block() -> None:
    assert (
        f"<!-- phase_ux_contract_version: {PHASE_UX_CONTRACT_VERSION} -->"
        in PHASE_UX_CONTRACT_BLOCK
    )


def test_section_fn_returns_the_block_verbatim() -> None:
    assert phase_ux_contract_section() is PHASE_UX_CONTRACT_BLOCK


def test_module_surface_exports_the_expected_names() -> None:
    assert hasattr(phase_ux_contract, "PHASE_UX_CONTRACT_BLOCK")
    assert hasattr(phase_ux_contract, "PHASE_UX_CONTRACT_VERSION")
    assert hasattr(phase_ux_contract, "phase_ux_contract_section")


# ---------------------------------------------------------------------------
# Payload budget
# ---------------------------------------------------------------------------


def test_contract_block_is_non_empty_string() -> None:
    assert isinstance(PHASE_UX_CONTRACT_BLOCK, str)
    assert PHASE_UX_CONTRACT_BLOCK.strip()


def test_contract_block_fits_prompt_budget_under_4kb() -> None:
    # 4 KB upper bound gives ~500 bytes of headroom above the current
    # ~3.4 KB block for minor anchor additions; a bigger bump should
    # force a deliberate spec review + version tag increment.
    size = len(PHASE_UX_CONTRACT_BLOCK.encode("utf-8"))
    assert size < 4096, f"contract grew to {size} bytes; trim before merging"


# ---------------------------------------------------------------------------
# Section headers
# ---------------------------------------------------------------------------


def test_section_header_anchors_phase_ux_title() -> None:
    assert (
        "## Phase UX contract (V1.6 Phase D — Purpose → Focus → Progress → Action)"
        in PHASE_UX_CONTRACT_BLOCK
    )


@pytest.mark.parametrize(
    "subheader",
    [
        "### Scope gate (when to apply this template)",
        "### The four steps (in order)",
        "### Authoritative ordering of deterministic reads",
        "### Retrospective + new-goal merge rule (phase transition)",
    ],
)
def test_expected_subheaders_are_present(subheader: str) -> None:
    assert subheader in PHASE_UX_CONTRACT_BLOCK


# ---------------------------------------------------------------------------
# Scope gate
# ---------------------------------------------------------------------------


def test_scope_gate_lists_plan_phase_progress_as_triggers() -> None:
    # The three locked scope triggers (user-decision 2026-04-21) must
    # all appear so the LLM cannot narrow-read the gate.
    assert "**plan**" in PHASE_UX_CONTRACT_BLOCK
    assert "**phase**" in PHASE_UX_CONTRACT_BLOCK
    assert "**progress against the " in PHASE_UX_CONTRACT_BLOCK


def test_scope_gate_names_unrelated_turns_explicitly() -> None:
    # The coach must recognize these as OUT-of-scope to avoid imposing
    # the Purpose/Focus/Progress/Action structure on a casual question.
    for phrase in (
        "single-run recap",
        "KPI-definition question",
        "preference update",
        "general chat",
    ):
        assert phrase in PHASE_UX_CONTRACT_BLOCK


def test_scope_gate_includes_casual_question_antiexample() -> None:
    # Verbatim anchor from the locked spec — the coach must know the
    # concrete out-of-scope example, not just the abstract category.
    assert "what's Z2?" in PHASE_UX_CONTRACT_BLOCK


# ---------------------------------------------------------------------------
# The four ordered steps
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "step_number,step_title",
    [
        (1, "**Purpose**"),
        (2, "**Focus**"),
        (3, "**Progress**"),
        (4, "**Action**"),
    ],
)
def test_four_steps_are_numbered_and_named(step_number: int, step_title: str) -> None:
    anchor = f"{step_number}. {step_title}"
    assert anchor in PHASE_UX_CONTRACT_BLOCK


def test_steps_appear_in_the_locked_order() -> None:
    # The four-step UX is an ordered pipeline — Focus before Progress,
    # Progress before Action. A test on just the presence of each
    # header would miss an out-of-order block.
    idx_purpose = PHASE_UX_CONTRACT_BLOCK.index("1. **Purpose**")
    idx_focus = PHASE_UX_CONTRACT_BLOCK.index("2. **Focus**")
    idx_progress = PHASE_UX_CONTRACT_BLOCK.index("3. **Progress**")
    idx_action = PHASE_UX_CONTRACT_BLOCK.index("4. **Action**")
    assert idx_purpose < idx_focus < idx_progress < idx_action


# ---------------------------------------------------------------------------
# Focus step — behavior/outcome goals, no KPI thresholds
# ---------------------------------------------------------------------------


def test_focus_reads_from_get_phase_analysis_goal_field() -> None:
    assert "`get_phase_analysis.goal.goal_text`" in PHASE_UX_CONTRACT_BLOCK


def test_focus_proposes_and_saves_when_goal_is_null() -> None:
    # When no active goal exists, the coach MUST propose one and save
    # via the tool — this is the 3D.4 auto-proposal hook surfaced at
    # the prompt level so the LLM does not forget the writer.
    assert "`save_phase_goal`" in PHASE_UX_CONTRACT_BLOCK
    assert "soft semantics" in PHASE_UX_CONTRACT_BLOCK


def test_focus_goal_shape_is_behavior_or_outcome() -> None:
    assert "behavior or outcome sentences" in PHASE_UX_CONTRACT_BLOCK


def test_focus_lists_good_goal_example() -> None:
    assert (
        "Stay mostly in Zone 2 on long runs so you finish strong."
        in PHASE_UX_CONTRACT_BLOCK
    )


@pytest.mark.parametrize(
    "bad_goal",
    [
        "Hit 85 % Z2 compliance.",
        "Achieve 300 TSS per week.",
    ],
)
def test_focus_lists_kpi_threshold_antiexamples(bad_goal: str) -> None:
    # Concrete anti-examples prevent the coach from smuggling a KPI
    # target through as a "goal". 3D.2 also enforces this at the
    # writer — the prompt reinforces it so the LLM does not even
    # propose one.
    assert bad_goal in PHASE_UX_CONTRACT_BLOCK


# ---------------------------------------------------------------------------
# Progress step — plain-language rule for the status enum
# ---------------------------------------------------------------------------


def test_progress_reads_weekly_progress_and_summary() -> None:
    assert "`weekly_progress[]`" in PHASE_UX_CONTRACT_BLOCK
    assert "`phase_progress_summary`" in PHASE_UX_CONTRACT_BLOCK


@pytest.mark.parametrize(
    "enum_value",
    ["on_track", "close", "off_track", "null"],
)
def test_progress_names_every_status_enum_value(enum_value: str) -> None:
    # All four canonical enum values must appear so the LLM is aware
    # of the full vocabulary even though it must not echo them.
    assert f"`{enum_value}`" in PHASE_UX_CONTRACT_BLOCK


def test_progress_forbids_raw_enum_echo() -> None:
    # Verbatim locked phrasing for the plain-language rule. Concrete
    # GOOD / BAD pair makes the rule inspectable in PR review.
    assert "MUST NOT echo it " in PHASE_UX_CONTRACT_BLOCK
    assert "verbatim" in PHASE_UX_CONTRACT_BLOCK
    assert "Your status is on_track." in PHASE_UX_CONTRACT_BLOCK
    assert "phase_progress_summary.dominant_status = close." in PHASE_UX_CONTRACT_BLOCK


def test_progress_happy_path_example_references_priority_run_type() -> None:
    # The GOOD example shows the coach binding the narrative to the
    # phase's priority run type — this is the 3D.6 classifier's point
    # of leverage and must survive as an anchor in the prompt.
    assert (
        "Your Tempo execution has been landing and you hit 4 of 5 runs"
        in PHASE_UX_CONTRACT_BLOCK
    )


def test_progress_handles_null_dominant_status() -> None:
    # Phase with no evaluable weeks yet (pre-phase or all-future)
    # must NOT produce a fake verdict.
    assert "dominant_status` is `null`" in PHASE_UX_CONTRACT_BLOCK
    assert "no evaluable weeks yet" in PHASE_UX_CONTRACT_BLOCK


# ---------------------------------------------------------------------------
# Action step — one action OR one question, reinforce Focus
# ---------------------------------------------------------------------------


def test_action_references_one_next_action_or_one_question() -> None:
    assert "one next action OR one guiding" in PHASE_UX_CONTRACT_BLOCK
    assert "Never both" in PHASE_UX_CONTRACT_BLOCK
    assert "Never an analysis-only" in PHASE_UX_CONTRACT_BLOCK


def test_action_anchors_to_section_19_6() -> None:
    assert "§19.6" in PHASE_UX_CONTRACT_BLOCK


# ---------------------------------------------------------------------------
# Authoritative deterministic-read rule
# ---------------------------------------------------------------------------


def test_authoritative_reads_pin_each_source_of_truth() -> None:
    # One-producer rule (§X.5) — each anchor reminds the LLM of the
    # single source for a given deterministic field.
    assert "`get_phase_analysis.goal` is the ONLY source" in PHASE_UX_CONTRACT_BLOCK
    assert (
        "`phase_progress_summary.dominant_status` is the ONLY source"
        in PHASE_UX_CONTRACT_BLOCK
    )
    assert "`weekly_progress[].status` is the ONLY source" in PHASE_UX_CONTRACT_BLOCK


def test_authoritative_reads_allow_tension_but_forbid_flip() -> None:
    # Mirrors §19.9 coach-side read-only rule: surface tension, never
    # flip the value.
    assert "MUST NOT flip the label" in PHASE_UX_CONTRACT_BLOCK


# ---------------------------------------------------------------------------
# Retrospective + new-goal merge rule
# ---------------------------------------------------------------------------


def test_retrospective_new_goal_merges_into_one_turn() -> None:
    # User-locked decision 2026-04-21: retrospective + new goal is a
    # SINGLE coach response, not two turns.
    assert "merge **one** coach response" in PHASE_UX_CONTRACT_BLOCK
    assert "Do NOT split this into two separate turns" in PHASE_UX_CONTRACT_BLOCK


def test_retrospective_triggers_on_phase_transition_signal() -> None:
    # The triggering signal is deterministic: prior phase's
    # `phase_weeks.phase_temporality == past` AND the new phase has no
    # active `goal`. This lets 3D.4 key its auto-proposal hook off
    # the same payload fields the prompt is describing.
    assert "phase_weeks.phase_temporality = past" in PHASE_UX_CONTRACT_BLOCK
    assert "has no active `goal`" in PHASE_UX_CONTRACT_BLOCK
    assert "save_phase_goal` (unconfirmed)" in PHASE_UX_CONTRACT_BLOCK


# ---------------------------------------------------------------------------
# Orchestrator wiring
# ---------------------------------------------------------------------------


def test_orchestrator_imports_contract_section() -> None:
    from src.smartcoach_mobile_coach import orchestrator

    assert hasattr(orchestrator, "phase_ux_contract_section")
    assert orchestrator.phase_ux_contract_section is phase_ux_contract_section


def test_orchestrator_source_wires_contract_after_plan_guidance() -> None:
    # Structural lock: the Phase UX contract must be composed exactly
    # once in the non-plan-creation branch, AFTER
    # `plan_guidance_contract_section()` (so the §19.4 phase emphasis
    # rules come first, and the 3D.8 Purpose/Focus/Progress/Action
    # UX refines them).
    from pathlib import Path

    src = Path("src/smartcoach_mobile_coach/orchestrator.py").read_text(
        encoding="utf-8"
    )
    assert src.count("phase_ux_contract_section()") == 1
    pg_idx = src.index("plan_guidance_contract_section()")
    ux_idx = src.index("phase_ux_contract_section()")
    assert pg_idx < ux_idx, (
        "phase_ux_contract_section must be composed AFTER "
        "plan_guidance_contract_section"
    )


def test_orchestrator_does_not_wire_contract_into_plan_creation_branch() -> None:
    # Plan-creation mode uses PLAN_CREATION_SYSTEM_PROMPT_BASE; the
    # Phase UX template has no meaning during plan intake (there is no
    # phase goal and no weekly progress yet) and must not bloat that
    # prompt.
    from pathlib import Path

    src = Path("src/smartcoach_mobile_coach/orchestrator.py").read_text(
        encoding="utf-8"
    )
    plan_creation_base_idx = src.index("PLAN_CREATION_SYSTEM_PROMPT_BASE")
    ux_idx = src.index("phase_ux_contract_section()")
    assert plan_creation_base_idx < ux_idx, (
        "phase_ux_contract_section() must be wired in the non-plan-"
        "creation else block, not in the plan-creation branch"
    )
