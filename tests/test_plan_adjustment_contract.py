"""
V1.6 Phase E — plan-adjustment prompt contract tests.

Locks the coach-side "use the structured writer first" rule so the LLM
cannot drift back to text-only plan mutation promises.
"""

from __future__ import annotations

import pytest

from src.smartcoach_mobile_coach import plan_adjustment_contract
from src.smartcoach_mobile_coach.plan_adjustment_contract import (
    PLAN_ADJUSTMENT_CONTRACT_BLOCK,
    PLAN_ADJUSTMENT_CONTRACT_VERSION,
    plan_adjustment_contract_section,
)


def test_contract_version_is_int_and_v2() -> None:
    assert isinstance(PLAN_ADJUSTMENT_CONTRACT_VERSION, int)
    assert PLAN_ADJUSTMENT_CONTRACT_VERSION == 2


def test_version_tag_appears_in_block() -> None:
    assert (
        f"<!-- plan_adjustment_contract_version: {PLAN_ADJUSTMENT_CONTRACT_VERSION} -->"
        in PLAN_ADJUSTMENT_CONTRACT_BLOCK
    )


def test_section_fn_returns_the_block_verbatim() -> None:
    assert plan_adjustment_contract_section() is PLAN_ADJUSTMENT_CONTRACT_BLOCK


def test_module_surface_exports_expected_names() -> None:
    assert hasattr(plan_adjustment_contract, "PLAN_ADJUSTMENT_CONTRACT_BLOCK")
    assert hasattr(plan_adjustment_contract, "PLAN_ADJUSTMENT_CONTRACT_VERSION")
    assert hasattr(plan_adjustment_contract, "plan_adjustment_contract_section")


def test_contract_block_is_non_empty_string() -> None:
    assert isinstance(PLAN_ADJUSTMENT_CONTRACT_BLOCK, str)
    assert PLAN_ADJUSTMENT_CONTRACT_BLOCK.strip()


def test_contract_block_fits_prompt_budget_under_3kb() -> None:
    size = len(PLAN_ADJUSTMENT_CONTRACT_BLOCK.encode("utf-8"))
    assert size < 3072, f"contract grew to {size} bytes; trim before merging"


def test_section_header_anchor_is_present() -> None:
    assert (
        "## Plan Adjustment contract (V1.6 Phase E — structured operations)"
        in PLAN_ADJUSTMENT_CONTRACT_BLOCK
    )


@pytest.mark.parametrize(
    "subheader",
    [
        "### Scope gate (when this applies)",
        "### Required tool path",
        "### After-tool response rule",
        "### Forbidden",
    ],
)
def test_expected_subheaders_are_present(subheader: str) -> None:
    assert subheader in PLAN_ADJUSTMENT_CONTRACT_BLOCK


@pytest.mark.parametrize(
    "example",
    [
        "reduce next week",
        "this is too hard",
        "add another run",
        "cut volume",
    ],
)
def test_scope_gate_lists_locked_intent_examples(example: str) -> None:
    assert example in PLAN_ADJUSTMENT_CONTRACT_BLOCK


def test_required_tool_path_names_apply_plan_adjustments() -> None:
    assert "`apply_plan_adjustments`" in PLAN_ADJUSTMENT_CONTRACT_BLOCK


def test_required_tool_path_forbids_describing_changes_without_tool() -> None:
    assert "MUST use `apply_plan_adjustments`" in PLAN_ADJUSTMENT_CONTRACT_BLOCK
    assert "MUST NOT describe plan changes" in PLAN_ADJUSTMENT_CONTRACT_BLOCK


def test_translation_rule_requires_structured_operations() -> None:
    assert "structured operations" in PLAN_ADJUSTMENT_CONTRACT_BLOCK
    assert "`operations[]`" in PLAN_ADJUSTMENT_CONTRACT_BLOCK


def test_backend_authority_rule_is_present() -> None:
    assert "backend is the ONLY authority" in PLAN_ADJUSTMENT_CONTRACT_BLOCK


def test_after_tool_response_rule_requires_post_tool_explanation() -> None:
    assert "Explain the result only AFTER `apply_plan_adjustments` returns." in (
        PLAN_ADJUSTMENT_CONTRACT_BLOCK
    )
    assert "ONLY source of truth" in PLAN_ADJUSTMENT_CONTRACT_BLOCK


def test_after_tool_rule_requires_requested_vs_applied_when_capped() -> None:
    assert "what the user asked for" in PLAN_ADJUSTMENT_CONTRACT_BLOCK
    assert "what was actually applied" in PLAN_ADJUSTMENT_CONTRACT_BLOCK
    assert "Do not blur the two." in PLAN_ADJUSTMENT_CONTRACT_BLOCK


def test_after_tool_rule_forbids_restating_rejected_change_as_applied() -> None:
    assert "do NOT restate the original change as if it went through" in (
        PLAN_ADJUSTMENT_CONTRACT_BLOCK
    )
    assert "blocking constraint" in PLAN_ADJUSTMENT_CONTRACT_BLOCK
    assert "consistent with the tool output" in PLAN_ADJUSTMENT_CONTRACT_BLOCK


def test_contract_allows_single_clarifying_question_when_ambiguous() -> None:
    assert "ask ONE clarifying question" in PLAN_ADJUSTMENT_CONTRACT_BLOCK


@pytest.mark.parametrize(
    "forbidden_phrase",
    [
        "MUST NOT apply changes directly in text.",
        "MUST NOT bypass backend constraints",
        "MUST NOT invent updated miles",
        "MUST NOT narrate a requested change as completed before the tool returns.",
    ],
)
def test_forbidden_rules_are_explicit(forbidden_phrase: str) -> None:
    assert forbidden_phrase in PLAN_ADJUSTMENT_CONTRACT_BLOCK


def test_orchestrator_imports_contract_section() -> None:
    from src.smartcoach_mobile_coach import orchestrator

    assert hasattr(orchestrator, "plan_adjustment_contract_section")
    assert (
        orchestrator.plan_adjustment_contract_section
        is plan_adjustment_contract_section
    )


def test_orchestrator_source_wires_contract_after_phase_ux_and_before_tone() -> None:
    from pathlib import Path

    src = Path("src/smartcoach_mobile_coach/orchestrator.py").read_text(
        encoding="utf-8"
    )
    assert src.count("plan_adjustment_contract_section()") == 1
    phase_ux_idx = src.index("phase_ux_contract_section()")
    adjustment_idx = src.index("plan_adjustment_contract_section()")
    tone_idx = src.index("coach_tone_contract_section()")
    prose_idx = src.index("coach_turn_prose_shape_section()")
    assert phase_ux_idx < adjustment_idx < tone_idx < prose_idx


def test_orchestrator_does_not_wire_contract_into_plan_creation_branch() -> None:
    from pathlib import Path

    src = Path("src/smartcoach_mobile_coach/orchestrator.py").read_text(
        encoding="utf-8"
    )
    plan_creation_base_idx = src.index("PLAN_CREATION_SYSTEM_PROMPT_BASE")
    contract_idx = src.index("plan_adjustment_contract_section()")
    assert plan_creation_base_idx < contract_idx
