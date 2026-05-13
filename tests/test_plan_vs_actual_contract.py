"""
V1.6 Phase C 3C.1 + 3C.2 — plan-vs-actual coaching contract tests.

The block injected into the system prompt by
``plan_vs_actual_contract_section()`` mirrors
``docs/SMARTCOACH_SYSTEM_SPEC_V1.md`` §§19.2–19.3. These contract tests
lock:

* version tag wiring,
* the canonical reasoning order phrase and every field of the
  PLAN / ACTUAL / GAP / ACTION table,
* the two special-case rewrites (``plan_status = missed`` /
  ``plan_status = unplanned``),
* the three forbidden language collapses,
* the payload fits the prompt budget,
* the orchestrator wires the section into non-plan-creation turns
  and suppresses it in plan-creation mode.
"""

from __future__ import annotations

import pytest

from src.smartcoach_mobile_coach import plan_vs_actual_contract
from src.smartcoach_mobile_coach.plan_vs_actual_contract import (
    PLAN_VS_ACTUAL_CONTRACT_BLOCK,
    PLAN_VS_ACTUAL_CONTRACT_VERSION,
    plan_vs_actual_contract_section,
)


# ---------------------------------------------------------------------------
# Version tag & module surface
# ---------------------------------------------------------------------------


def test_contract_version_is_int_and_v1() -> None:
    assert isinstance(PLAN_VS_ACTUAL_CONTRACT_VERSION, int)
    assert PLAN_VS_ACTUAL_CONTRACT_VERSION == 1


def test_version_tag_appears_in_block() -> None:
    assert (
        f"<!-- plan_vs_actual_contract_version: {PLAN_VS_ACTUAL_CONTRACT_VERSION} -->"
        in PLAN_VS_ACTUAL_CONTRACT_BLOCK
    )


def test_section_fn_returns_the_block_verbatim() -> None:
    assert plan_vs_actual_contract_section() is PLAN_VS_ACTUAL_CONTRACT_BLOCK


def test_module_has_no_side_effectful_imports() -> None:
    assert hasattr(plan_vs_actual_contract, "PLAN_VS_ACTUAL_CONTRACT_BLOCK")
    assert hasattr(plan_vs_actual_contract, "plan_vs_actual_contract_section")


# ---------------------------------------------------------------------------
# Payload budget
# ---------------------------------------------------------------------------


def test_contract_block_is_non_empty_string() -> None:
    assert isinstance(PLAN_VS_ACTUAL_CONTRACT_BLOCK, str)
    assert PLAN_VS_ACTUAL_CONTRACT_BLOCK.strip()


def test_contract_block_fits_prompt_budget_under_2kb() -> None:
    size = len(PLAN_VS_ACTUAL_CONTRACT_BLOCK.encode("utf-8"))
    assert size < 2048, f"contract grew to {size} bytes; trim before merging"


# ---------------------------------------------------------------------------
# §19.2 reasoning order anchors
# ---------------------------------------------------------------------------


def test_section_header_anchors_spec_19_2_and_19_3() -> None:
    assert (
        "## Plan vs actual coaching contract (V1.6 §§19.2–19.3)"
        in PLAN_VS_ACTUAL_CONTRACT_BLOCK
    )


def test_canonical_reasoning_order_string_is_present() -> None:
    assert (
        "**PLAN → ACTUAL (if present) → GAP → ACTION**" in PLAN_VS_ACTUAL_CONTRACT_BLOCK
    )


@pytest.mark.parametrize(
    "step",
    ["**PLAN**", "**ACTUAL**", "**GAP**", "**ACTION**"],
)
def test_every_reasoning_order_step_is_defined(step: str) -> None:
    assert step in PLAN_VS_ACTUAL_CONTRACT_BLOCK


def test_actual_step_ties_to_plan_status_executed_or_in_progress() -> None:
    # §19.2 table: ACTUAL included only when plan_status ∈ {executed, in_progress}
    assert "`executed`" in PLAN_VS_ACTUAL_CONTRACT_BLOCK
    assert "`in_progress`" in PLAN_VS_ACTUAL_CONTRACT_BLOCK


def test_action_step_cross_references_19_6() -> None:
    assert "§19.6" in PLAN_VS_ACTUAL_CONTRACT_BLOCK


# ---------------------------------------------------------------------------
# §19.2 special cases (plan_status = missed / unplanned)
# ---------------------------------------------------------------------------


def test_missed_special_case_anchors() -> None:
    # PLAN present, no ACTUAL, GAP = missed execution, ACTION
    assert "`plan_status = missed`" in PLAN_VS_ACTUAL_CONTRACT_BLOCK
    assert "*no ACTUAL*" in PLAN_VS_ACTUAL_CONTRACT_BLOCK
    assert "**GAP = missed execution**" in PLAN_VS_ACTUAL_CONTRACT_BLOCK


def test_unplanned_special_case_anchors() -> None:
    assert "`plan_status = unplanned`" in PLAN_VS_ACTUAL_CONTRACT_BLOCK
    assert "*no PLAN*" in PLAN_VS_ACTUAL_CONTRACT_BLOCK
    assert "**GAP replaced by CONTEXT**" in PLAN_VS_ACTUAL_CONTRACT_BLOCK
    # Keeps the first-sentence unplanned acknowledgment anchor (§19.7)
    # visible at this scope, so the coach sees it when reasoning about
    # plan_status = unplanned.
    assert "§19.7" in PLAN_VS_ACTUAL_CONTRACT_BLOCK


def test_anti_pattern_actual_only_opening_is_explicitly_forbidden() -> None:
    # §19.2 final paragraph: starting with actual alone violates the contract
    assert '*"Your run was' in PLAN_VS_ACTUAL_CONTRACT_BLOCK
    assert "**violates §19.2**" in PLAN_VS_ACTUAL_CONTRACT_BLOCK


# ---------------------------------------------------------------------------
# §19.3 language separation anchors
# ---------------------------------------------------------------------------


def test_language_separation_has_three_contexts() -> None:
    # Each context's required phrasing example from §19.3 appears verbatim.
    assert '*"This was scheduled as…"*' in PLAN_VS_ACTUAL_CONTRACT_BLOCK
    assert '*"Your Easy run today is planned for…"*' in PLAN_VS_ACTUAL_CONTRACT_BLOCK
    assert '*"You ran…"*' in PLAN_VS_ACTUAL_CONTRACT_BLOCK
    assert '*"Your execution was…"*' in PLAN_VS_ACTUAL_CONTRACT_BLOCK
    assert '*"Compared to plan…"*' in PLAN_VS_ACTUAL_CONTRACT_BLOCK
    assert '*"Versus the intended…"*' in PLAN_VS_ACTUAL_CONTRACT_BLOCK


def test_forbidden_actual_described_as_planned() -> None:
    assert '*"you planned a 5-mile run"*' in PLAN_VS_ACTUAL_CONTRACT_BLOCK
    assert "confuses intent with reality" in PLAN_VS_ACTUAL_CONTRACT_BLOCK


def test_forbidden_past_tense_for_future_week() -> None:
    assert '*"you ran an Easy on Tuesday"*' in PLAN_VS_ACTUAL_CONTRACT_BLOCK
    # Anchor to the §6 future-week contract
    assert "§6 future-week contract" in PLAN_VS_ACTUAL_CONTRACT_BLOCK


def test_forbidden_noun_phrase_collapse() -> None:
    assert '*"your 5-mile run"*' in PLAN_VS_ACTUAL_CONTRACT_BLOCK
    assert "hides the adherence gap" in PLAN_VS_ACTUAL_CONTRACT_BLOCK


# ---------------------------------------------------------------------------
# Orchestrator integration
# ---------------------------------------------------------------------------


def test_orchestrator_imports_contract_section() -> None:
    from src.smartcoach_mobile_coach import orchestrator

    assert hasattr(orchestrator, "plan_vs_actual_contract_section")
    assert (
        orchestrator.plan_vs_actual_contract_section is plan_vs_actual_contract_section
    )


def test_orchestrator_source_wires_contract_into_non_plan_creation_branch() -> None:
    # Structural lock: the contract section must be composed alongside
    # the metric glossary in the non-plan-creation ``_join_nonempty_system_sections``
    # call. A refactor that accidentally drops the wire would drop the
    # §§19.2–19.3 contract from every real coaching turn.
    from pathlib import Path

    src = Path("src/smartcoach_mobile_coach/orchestrator/__init__.py").read_text(
        encoding="utf-8"
    )
    # The call appears exactly once (non-plan-creation branch).
    assert src.count("plan_vs_actual_contract_section()") == 1
    # And it is adjacent to the metric glossary (ordered: glossary,
    # then the plan vs actual contract).
    glossary_idx = src.index("metric_glossary_section()")
    contract_idx = src.index("plan_vs_actual_contract_section()")
    assert (
        glossary_idx < contract_idx
    ), "plan_vs_actual_contract_section must be composed AFTER metric_glossary_section"


def test_orchestrator_does_not_wire_contract_into_plan_creation_branch() -> None:
    # The plan-creation branch uses its own restricted prompt; the
    # §§19.2–19.3 contract has no meaning during plan intake (no plan
    # vs actual yet) and should not bloat that prompt.
    from pathlib import Path

    src = Path("src/smartcoach_mobile_coach/orchestrator/__init__.py").read_text(
        encoding="utf-8"
    )
    # Confirm the contract wire is below the PLAN_CREATION_SYSTEM_PROMPT_BASE
    # wire (i.e., the "else" branch that runs for non-plan-creation turns).
    plan_creation_base_idx = src.index("PLAN_CREATION_SYSTEM_PROMPT_BASE")
    contract_idx = src.index("plan_vs_actual_contract_section()")
    assert plan_creation_base_idx < contract_idx, (
        "plan_vs_actual_contract_section() must be wired after the plan-"
        "creation branch, in the non-plan-creation else block"
    )
