"""
V1.6 Phase B 3B.14–3B.16 — metric glossary contract tests.

The glossary is a **prompt-memory answer key** for bare concept
questions like "what is Z2?" or "what is HR drift?". This suite locks:

- The block is versioned (``glossary_version: N``) so the spec ↔ prompt
  relationship is traceable and A/B-able.
- Spec-anchored terms (Z1–Z5, the four KPIs, every ``deviation_direction``
  value, and all three adherence bands) are present.
- The block lands in the composed system prompt on non-plan-creation
  turns (i.e. the coach can actually see it).
- Cost posture: the glossary is compact (< 2 KB) so it fits alongside
  base prompt + directive + preferences without blowing the budget.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.smartcoach_mobile_coach.metric_glossary import (
    GLOSSARY_VERSION,
    METRIC_GLOSSARY_BLOCK,
    metric_glossary_section,
)


# ---------------------------------------------------------------------------
# Shape & version
# ---------------------------------------------------------------------------


def test_glossary_version_is_integer():
    assert isinstance(GLOSSARY_VERSION, int)
    assert GLOSSARY_VERSION >= 1


def test_glossary_block_embeds_version_tag():
    """3B.16: the rendered block must advertise its version."""
    block = metric_glossary_section()
    assert f"glossary_version: {GLOSSARY_VERSION}" in block


def test_glossary_section_is_nonempty_string_identity():
    """Helper returns the module-level constant verbatim (no runtime drift)."""
    assert metric_glossary_section() == METRIC_GLOSSARY_BLOCK
    assert metric_glossary_section().strip()


# ---------------------------------------------------------------------------
# Size budget (Topic 4)
# ---------------------------------------------------------------------------


def test_glossary_fits_cost_budget_under_2kb():
    """Glossary is shipped every non-plan-creation turn; keep it cheap."""
    size = len(metric_glossary_section().encode("utf-8"))
    assert size < 2048, f"glossary grew to {size} bytes; trim before merging"


# ---------------------------------------------------------------------------
# Spec-anchored content (3B.15) — locks wording the coach relies on.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("zone_label", ["Z1", "Z2", "Z3", "Z4", "Z5"])
def test_glossary_defines_every_hr_zone(zone_label):
    """3B.14: a user asking 'what is Z2?' must find it in prompt memory."""
    assert zone_label in METRIC_GLOSSARY_BLOCK


def test_z2_anchor_phrasing_matches_spec():
    """
    3B.15: Z2 specifically is the single most-asked concept. The spec
    describes Easy as 'Zone 1-2' / 'conversational'; lock those anchors
    so the coach can answer without a tool.
    """
    block = METRIC_GLOSSARY_BLOCK
    assert "Aerobic base" in block or "aerobic base" in block
    assert "onversational" in block  # "conversational" / "Conversational"
    assert "Easy" in block


@pytest.mark.parametrize(
    "kpi",
    ["Zone Compliance", "HR Drift", "Aerobic Efficiency", "Pace Consistency"],
)
def test_glossary_defines_every_v1_kpi(kpi):
    """3B.14: core + type-specific KPIs must be present (§7)."""
    assert kpi in METRIC_GLOSSARY_BLOCK


def test_zone_compliance_is_labeled_primary_driver():
    """Spec §9: Zone Compliance is the primary scoring driver."""
    block = METRIC_GLOSSARY_BLOCK.lower()
    assert "primary" in block and "scoring" in block


def test_hr_drift_defined_as_rate_of_hr_rise():
    assert "rise" in METRIC_GLOSSARY_BLOCK.lower()
    assert "HR Drift" in METRIC_GLOSSARY_BLOCK


def test_pace_consistency_scoped_to_main_block():
    """Spec §7/§9: Pace Consistency is measured on the main block."""
    assert "main block" in METRIC_GLOSSARY_BLOCK


# ---------------------------------------------------------------------------
# deviation_direction enum coverage (§5)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "enum_value",
    ["too_hard", "too_easy", "on_target", "null"],
)
def test_glossary_enumerates_every_deviation_direction_value(enum_value):
    assert enum_value in METRIC_GLOSSARY_BLOCK


def test_deviation_direction_guardrails_reference_llm_contract():
    """
    Spec §5 + §19: LLM must not compute/override `deviation_direction`.
    The glossary reminds the model of that contract inline.
    """
    block = METRIC_GLOSSARY_BLOCK.lower()
    assert "must not" in block
    assert "deterministic" in block


def test_null_deviation_includes_steady_and_short_run_carveouts():
    """Null branch (§5) is the trickiest and most easily hallucinated."""
    block = METRIC_GLOSSARY_BLOCK
    assert "Steady" in block
    assert "600" in block  # duration_seconds < 600
    assert "HR stream" in block or "HR data" in block


# ---------------------------------------------------------------------------
# Adherence bands (§7)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("band", ["Low", "Medium", "High"])
def test_glossary_enumerates_every_adherence_band(band):
    assert f"**{band}**" in METRIC_GLOSSARY_BLOCK


def test_adherence_bands_include_numeric_anchors():
    """Spec §7 Low/Medium/High thresholds must be present verbatim."""
    assert "70 %" in METRIC_GLOSSARY_BLOCK
    assert "90 %" in METRIC_GLOSSARY_BLOCK


def test_adherence_scope_is_adaptation_not_scoring():
    """Spec §7: adherence influences adaptation, not per-run scoring."""
    block = METRIC_GLOSSARY_BLOCK.lower()
    assert "adaptation" in block
    # Make sure we don't accidentally say adherence drives run score
    assert "adherence drives" not in block


def test_glossary_preserves_tool_first_rule_for_user_numbers():
    """
    Prompt-memory answers are for *concepts*. For the user's own run
    data we must still call a tool — lock that carve-out so the model
    doesn't free-text numbers.
    """
    block = METRIC_GLOSSARY_BLOCK.lower()
    assert "tool" in block and "never replace" in block


# ---------------------------------------------------------------------------
# Orchestrator integration — glossary actually reaches the model.
# ---------------------------------------------------------------------------


@dataclass
class _StubDirective:
    """Minimal directive compatible with the orchestrator join helper."""


def test_glossary_is_joined_into_system_sections():
    """
    ``_join_nonempty_system_sections`` is the single place prompt
    sections concatenate. Ensure the glossary helper returns a value
    the join accepts (non-empty string with its own header).
    """
    from src.smartcoach_mobile_coach.orchestrator import (
        _join_nonempty_system_sections,
    )

    out = _join_nonempty_system_sections(
        "## Base prompt placeholder", metric_glossary_section()
    )
    assert "Metric glossary" in out
    assert f"glossary_version: {GLOSSARY_VERSION}" in out


def test_glossary_answers_z2_style_question_without_tool_reference():
    """
    3B.14 success criterion: 'what is Z2?' is answerable from prompt
    memory. Lock that the Z2 definition line does not point the coach
    at a tool (which would defeat the cost savings).
    """
    z2_context = ""
    for line in METRIC_GLOSSARY_BLOCK.splitlines():
        if "Z2" in line and "Aerobic base" in line:
            z2_context = line
            break
    assert z2_context, "Z2 definition line missing"
    assert "get_" not in z2_context, (
        "Z2 definition must not route the coach to a tool — "
        "the whole point of the glossary is prompt-memory answers."
    )
