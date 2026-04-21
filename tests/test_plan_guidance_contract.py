"""
V1.6 Phase C 3C.3 + 3C.4 — phase emphasis + future-week contract tests.

Locks the §§19.4–19.5 prompt section against
``docs/SMARTCOACH_SYSTEM_SPEC_V1.md``. Scope:

* version tag wiring,
* spec-header anchor,
* every row of the §19.4 per-phase emphasis table
  (Base / Build / Peak / Taper with their ``emphasize`` and
  ``de-emphasize`` items),
* `phase_kpi_priority` authoritative-over-table rule,
* §19.5 three-part "may" allow-list (intent / progression / phase
  transitions),
* §19.5 four-part "must not" deny-list (predict outcomes, infer
  difficulty, reference absent ``actual.*``, invent numbers),
* payload budget (< 2 KB),
* orchestrator wiring (non-plan-creation branch, after
  :func:`plan_vs_actual_contract_section`, not in plan_creation_mode).
"""

from __future__ import annotations

import pytest

from src.smartcoach_mobile_coach import plan_guidance_contract
from src.smartcoach_mobile_coach.plan_guidance_contract import (
    PLAN_GUIDANCE_CONTRACT_BLOCK,
    PLAN_GUIDANCE_CONTRACT_VERSION,
    plan_guidance_contract_section,
)


# ---------------------------------------------------------------------------
# Version tag & module surface
# ---------------------------------------------------------------------------


def test_contract_version_is_int_and_v1() -> None:
    assert isinstance(PLAN_GUIDANCE_CONTRACT_VERSION, int)
    assert PLAN_GUIDANCE_CONTRACT_VERSION == 1


def test_version_tag_appears_in_block() -> None:
    assert (
        f"<!-- plan_guidance_contract_version: {PLAN_GUIDANCE_CONTRACT_VERSION} -->"
        in PLAN_GUIDANCE_CONTRACT_BLOCK
    )


def test_section_fn_returns_the_block_verbatim() -> None:
    assert plan_guidance_contract_section() is PLAN_GUIDANCE_CONTRACT_BLOCK


def test_module_surface_exports_the_expected_names() -> None:
    assert hasattr(plan_guidance_contract, "PLAN_GUIDANCE_CONTRACT_BLOCK")
    assert hasattr(plan_guidance_contract, "PLAN_GUIDANCE_CONTRACT_VERSION")
    assert hasattr(plan_guidance_contract, "plan_guidance_contract_section")


# ---------------------------------------------------------------------------
# Payload budget
# ---------------------------------------------------------------------------


def test_contract_block_is_non_empty_string() -> None:
    assert isinstance(PLAN_GUIDANCE_CONTRACT_BLOCK, str)
    assert PLAN_GUIDANCE_CONTRACT_BLOCK.strip()


def test_contract_block_fits_prompt_budget_under_2kb() -> None:
    size = len(PLAN_GUIDANCE_CONTRACT_BLOCK.encode("utf-8"))
    assert size < 2048, f"contract grew to {size} bytes; trim before merging"


# ---------------------------------------------------------------------------
# Section headers
# ---------------------------------------------------------------------------


def test_section_header_anchors_19_4_and_19_5() -> None:
    assert (
        "## Phase emphasis & future-week contract (V1.6 §§19.4–19.5)"
        in PLAN_GUIDANCE_CONTRACT_BLOCK
    )


def test_phase_subheader_is_present() -> None:
    assert "### §19.4 Phase-aware KPI emphasis" in PLAN_GUIDANCE_CONTRACT_BLOCK


def test_future_week_subheader_is_present() -> None:
    assert "### §19.5 Future-week contract" in PLAN_GUIDANCE_CONTRACT_BLOCK


# ---------------------------------------------------------------------------
# §19.4 — phase emphasis rules
# ---------------------------------------------------------------------------


def test_top_1_2_priority_rule_anchored() -> None:
    assert "top 1–2 entries" in PLAN_GUIDANCE_CONTRACT_BLOCK
    assert "`phase_kpi_priority`" in PLAN_GUIDANCE_CONTRACT_BLOCK


def test_drill_down_only_carve_out_present() -> None:
    # Full KPI set stays available in the payload; other KPIs surface
    # only on drill-down. Prevents the coach from dropping KPIs entirely
    # when they're outside the priority list.
    assert "drill-down" in PLAN_GUIDANCE_CONTRACT_BLOCK


@pytest.mark.parametrize(
    "phase,emphasize,deemphasize",
    [
        (
            "Base",
            ["HR Drift", "Aerobic Efficiency", "Easy compliance"],
            ["Tempo consistency"],
        ),
        (
            "Build",
            ["Pace Consistency", "Quality compliance"],
            ["Maintenance framing"],
        ),
        (
            "Peak",
            ["Execution", "Fatigue consistency"],
            ["capacity-building language"],
        ),
        (
            "Taper",
            ["Maintenance", "Recovery"],
            ["progression pushing"],
        ),
    ],
)
def test_phase_emphasis_table_row_is_verbatim(
    phase: str, emphasize: list[str], deemphasize: list[str]
) -> None:
    # Each phase must appear with BOTH its emphasize items and its
    # de-emphasize rationale so the coach knows what to lean into AND
    # what phase-inappropriate framing to avoid.
    assert f"**{phase}**" in PLAN_GUIDANCE_CONTRACT_BLOCK
    for item in emphasize:
        assert (
            item in PLAN_GUIDANCE_CONTRACT_BLOCK
        ), f"{phase}: emphasis anchor {item!r} missing from block"
    for item in deemphasize:
        assert (
            item in PLAN_GUIDANCE_CONTRACT_BLOCK
        ), f"{phase}: de-emphasis anchor {item!r} missing from block"


def test_all_four_canonical_phases_are_listed() -> None:
    # V1 locks the plan into exactly these four training phases (§11).
    # Dropping any one from the emphasis block would leave the coach
    # without guidance for a real plan window.
    for phase in ("Base", "Build", "Peak", "Taper"):
        assert f"**{phase}**" in PLAN_GUIDANCE_CONTRACT_BLOCK


def test_phase_kpi_priority_list_is_authoritative() -> None:
    # If the per-phase narrative table and the runtime list disagree
    # (e.g. due to frequency scaling §14 or adaptation §16), the list
    # wins. The coach must not hard-code to the table in the prompt.
    assert "authoritative" in PLAN_GUIDANCE_CONTRACT_BLOCK


# ---------------------------------------------------------------------------
# §19.5 — future-week contract
# ---------------------------------------------------------------------------


def test_future_week_temporality_anchor() -> None:
    assert "`week_temporality = future`" in PLAN_GUIDANCE_CONTRACT_BLOCK


@pytest.mark.parametrize(
    "allow_item",
    [
        "**Intent**",
        "**Progression**",
        "**Phase transitions**",
    ],
)
def test_future_week_allow_list_items(allow_item: str) -> None:
    assert allow_item in PLAN_GUIDANCE_CONTRACT_BLOCK


def test_future_week_must_not_header_present() -> None:
    assert "must not" in PLAN_GUIDANCE_CONTRACT_BLOCK


def test_future_week_forbids_outcome_prediction() -> None:
    assert "Predict outcomes" in PLAN_GUIDANCE_CONTRACT_BLOCK
    # The concrete anti-example from §19.5 is kept verbatim so the LLM
    # knows what the rule looks like in practice.
    assert "you'll probably hit Tuesday's Tempo" in PLAN_GUIDANCE_CONTRACT_BLOCK


def test_future_week_forbids_difficulty_inference() -> None:
    assert "Infer difficulty" in PLAN_GUIDANCE_CONTRACT_BLOCK
    assert "this is going to feel hard" in PLAN_GUIDANCE_CONTRACT_BLOCK


def test_future_week_forbids_referencing_absent_actuals() -> None:
    # §6 future-week payload contract guarantees `actual.*` is absent;
    # the coach must not invent them.
    assert "`actual.*`" in PLAN_GUIDANCE_CONTRACT_BLOCK
    assert "§6 future-week payload" in PLAN_GUIDANCE_CONTRACT_BLOCK


def test_future_week_forbids_numbers_not_in_payload() -> None:
    assert (
        "pace or HR numbers that are not in the payload" in PLAN_GUIDANCE_CONTRACT_BLOCK
    )


# ---------------------------------------------------------------------------
# Orchestrator wiring
# ---------------------------------------------------------------------------


def test_orchestrator_imports_contract_section() -> None:
    from src.smartcoach_mobile_coach import orchestrator

    assert hasattr(orchestrator, "plan_guidance_contract_section")
    assert orchestrator.plan_guidance_contract_section is plan_guidance_contract_section


def test_orchestrator_source_wires_contract_into_non_plan_creation_branch() -> None:
    # Structural lock mirroring the 3C.1 + 3C.2 integration test: the
    # plan-guidance contract must be composed exactly once in the
    # non-plan-creation branch, AFTER plan_vs_actual_contract_section
    # (so the reasoning order / language rules come first, and the
    # phase emphasis + future-week rules refine them).
    from pathlib import Path

    src = Path("src/smartcoach_mobile_coach/orchestrator.py").read_text(
        encoding="utf-8"
    )
    assert src.count("plan_guidance_contract_section()") == 1
    pva_idx = src.index("plan_vs_actual_contract_section()")
    pg_idx = src.index("plan_guidance_contract_section()")
    assert pva_idx < pg_idx, (
        "plan_guidance_contract_section must be composed AFTER "
        "plan_vs_actual_contract_section"
    )


def test_orchestrator_does_not_wire_contract_into_plan_creation_branch() -> None:
    # Plan-creation mode uses PLAN_CREATION_SYSTEM_PROMPT_BASE; phase
    # emphasis + future-week rules have no meaning during intake and
    # should not bloat that prompt.
    from pathlib import Path

    src = Path("src/smartcoach_mobile_coach/orchestrator.py").read_text(
        encoding="utf-8"
    )
    plan_creation_base_idx = src.index("PLAN_CREATION_SYSTEM_PROMPT_BASE")
    pg_idx = src.index("plan_guidance_contract_section()")
    assert plan_creation_base_idx < pg_idx, (
        "plan_guidance_contract_section() must be wired in the non-plan-"
        "creation else block, not in the plan-creation branch"
    )
