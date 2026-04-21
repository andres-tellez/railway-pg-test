"""
Unit tests for ``src.services.phase.phase_priority`` (V1.6 §7
transition rule + §8 phase_kpi_priority table, Phase A item 6).

Locks the deterministic phase-emphasis contract so:
  * the four-phase enum wire values cannot silently drift,
  * the §8 per-phase ordered KPI list cannot be reordered or have
    entries added / removed without an explicit test update,
  * the §7 majority-of-days rule correctly prefers the later phase
    on ties (Base < Build < Peak < Taper),
  * the resolver degrades gracefully (``None``) on empty / unknown
    input rather than crashing the coach tier.
"""

from __future__ import annotations

import pytest

from src.services.phase.phase_priority import (
    Phase,
    PhaseKpi,
    PhaseKpiPriorityResult,
    compute_phase_kpi_priority_for_week,
    phase_kpi_priority_for_phase,
    resolve_week_phase,
)


# ---------------------------------------------------------------------------
# Enum wire contract.
# ---------------------------------------------------------------------------


class TestEnumContract:
    def test_enum_wire_values_match_plan_workouts_column(self):
        """``plan_workouts.phase`` stores these exact strings; the enum
        must round-trip with no translation layer."""
        assert Phase.BASE.value == "Base"
        assert Phase.BUILD.value == "Build"
        assert Phase.PEAK.value == "Peak"
        assert Phase.TAPER.value == "Taper"

    def test_exactly_four_phases(self):
        """V1.6 mandates exactly four phases. A fifth silently added
        would reshape §8 emphasis and §19.4 coach priority."""
        assert len(list(Phase)) == 4

    def test_enum_is_str_based_for_json(self):
        import json

        assert json.dumps(Phase.PEAK.value) == '"Peak"'


# ---------------------------------------------------------------------------
# §8 per-phase KPI priority table.
# ---------------------------------------------------------------------------


class TestPhaseKpiPriorityTable:
    """The §8 ordered lists. Each assertion locks both ``kpi_id`` and
    ``label`` — the ids drive validators / mobile surfaces; the labels
    mirror spec wording verbatim so the LLM prompt reads naturally."""

    def test_base_priority_matches_spec(self):
        priority = phase_kpi_priority_for_phase(Phase.BASE)
        assert priority == (
            PhaseKpi("hr_drift", "HR Drift"),
            PhaseKpi("aerobic_efficiency", "Aerobic Efficiency"),
            PhaseKpi("easy_zone_compliance", "Easy zone compliance"),
        )

    def test_build_priority_matches_spec(self):
        priority = phase_kpi_priority_for_phase(Phase.BUILD)
        assert priority == (
            PhaseKpi("pace_consistency_tempo", "Pace Consistency (Tempo)"),
            PhaseKpi("quality_zone_compliance", "Quality zone compliance"),
            PhaseKpi("hr_drift", "HR Drift"),
        )

    def test_peak_priority_matches_spec(self):
        priority = phase_kpi_priority_for_phase(Phase.PEAK)
        assert priority == (
            PhaseKpi(
                "execution_zone_compliance",
                "Execution (zone compliance across Tempo + Long)",
            ),
            PhaseKpi(
                "fatigue_consistency",
                "Fatigue consistency (HR drift across the week)",
            ),
            PhaseKpi("pace_consistency", "Pace Consistency"),
        )

    def test_taper_priority_matches_spec(self):
        priority = phase_kpi_priority_for_phase(Phase.TAPER)
        assert priority == (
            PhaseKpi("maintenance", "Maintenance (maintain not improve)"),
            PhaseKpi("recovery_signals", "Recovery signals"),
            PhaseKpi("zone_compliance", "Zone compliance"),
        )

    @pytest.mark.parametrize("phase", list(Phase))
    def test_every_phase_has_three_entries_in_v1_6(self, phase):
        """Contract for V1.6: all four phases ship with exactly three
        priority entries. The implementation is allowed to grow this
        in a future spec version, but any change should be explicit
        so this test is the gate."""
        assert len(phase_kpi_priority_for_phase(phase)) == 3

    def test_priority_is_immutable_tuple(self):
        """Callers must not mutate the canonical table."""
        assert isinstance(phase_kpi_priority_for_phase(Phase.BASE), tuple)

    def test_all_kpi_ids_are_snake_case_machine_readable(self):
        """§19.1 validator keys on the kpi_id; a space / uppercase
        would break it. Lock the convention across all phases."""
        for phase in Phase:
            for entry in phase_kpi_priority_for_phase(phase):
                assert (
                    entry.kpi_id.isidentifier()
                ), f"{phase.value} -> {entry.kpi_id} not a valid identifier"
                assert (
                    entry.kpi_id == entry.kpi_id.lower()
                ), f"{phase.value} -> {entry.kpi_id} must be lowercase"


# ---------------------------------------------------------------------------
# §7 majority-of-days + later-phase tie-break rule.
# ---------------------------------------------------------------------------


class TestResolveWeekPhaseStraightforward:
    def test_all_same_phase_resolves_to_that_phase(self):
        assert resolve_week_phase(["Base"] * 4) is Phase.BASE
        assert resolve_week_phase(["Build"] * 5) is Phase.BUILD
        assert resolve_week_phase(["Peak"] * 7) is Phase.PEAK
        assert resolve_week_phase(["Taper"] * 3) is Phase.TAPER

    def test_single_workout_resolves_to_its_phase(self):
        assert resolve_week_phase(["Peak"]) is Phase.PEAK

    def test_majority_wins_over_minority(self):
        """5/2 split — majority phase wins unambiguously."""
        assert resolve_week_phase(["Build"] * 5 + ["Base"] * 2) is Phase.BUILD

    def test_four_of_seven_wins_per_spec_majority_rule(self):
        """§7 wording: 'the phase that owns 4 or more of the 7
        calendar days... is the phase used'. Base owns 4 → Base wins
        even though Build is the later phase."""
        phases = ["Base"] * 4 + ["Build"] * 3
        assert resolve_week_phase(phases) is Phase.BASE


class TestResolveWeekPhaseTieBreaks:
    """§7 "resolve to the later phase to prepare the athlete for
    what's coming next" — Base < Build < Peak < Taper."""

    def test_base_build_tie_resolves_to_build(self):
        phases = ["Base"] * 3 + ["Build"] * 3
        assert resolve_week_phase(phases) is Phase.BUILD

    def test_build_peak_tie_resolves_to_peak(self):
        phases = ["Build"] * 3 + ["Peak"] * 3
        assert resolve_week_phase(phases) is Phase.PEAK

    def test_peak_taper_tie_resolves_to_taper(self):
        phases = ["Peak"] * 3 + ["Taper"] * 3
        assert resolve_week_phase(phases) is Phase.TAPER

    def test_three_way_tie_resolves_to_latest_phase(self):
        """3/3/1 sliver: Build + Peak tie at top, Base sliver. Winner
        is Peak (latest of the tied pair)."""
        phases = ["Base"] + ["Build"] * 3 + ["Peak"] * 3
        assert resolve_week_phase(phases) is Phase.PEAK

    def test_base_taper_tie_resolves_to_taper(self):
        """Non-adjacent tie still respects the Base < Taper order."""
        phases = ["Base"] * 2 + ["Taper"] * 2
        assert resolve_week_phase(phases) is Phase.TAPER


class TestResolveWeekPhaseDegenerate:
    def test_empty_iterable_returns_none(self):
        assert resolve_week_phase([]) is None

    def test_all_none_entries_returns_none(self):
        """A week with no phase evidence (rest-only, e.g. a deload
        stub) yields None — coach must omit the emphasis block
        rather than fabricate one."""
        assert resolve_week_phase([None, None, None]) is None

    def test_unknown_phase_strings_are_skipped(self):
        """Legacy / bad DB values must not crash the coach tier. The
        resolver treats them as no-evidence entries."""
        assert resolve_week_phase(["Hypertrophy", "Recovery-week"]) is None

    def test_mixed_valid_and_invalid_uses_valid_only(self):
        """Two valid Base workouts + one garbage label → Base."""
        assert resolve_week_phase(["Base", "Base", "Hypertrophy", None]) is Phase.BASE


# ---------------------------------------------------------------------------
# Composed entry point — compute_phase_kpi_priority_for_week.
# ---------------------------------------------------------------------------


class TestComposedResult:
    def test_returns_named_tuple_with_expected_fields(self):
        """Lock the public wire contract — Phase B consumers and
        mobile types rely on these names."""
        result = compute_phase_kpi_priority_for_week([])
        assert isinstance(result, PhaseKpiPriorityResult)
        assert set(result._fields) == {"phase", "priority", "day_counts"}

    def test_empty_week_returns_none_phase_and_empty_priority(self):
        result = compute_phase_kpi_priority_for_week([])
        assert result.phase is None
        assert result.priority == ()
        assert result.day_counts == {}

    def test_happy_path_all_build_week(self):
        result = compute_phase_kpi_priority_for_week(["Build"] * 4)
        assert result.phase is Phase.BUILD
        assert result.priority == phase_kpi_priority_for_phase(Phase.BUILD)
        assert result.day_counts == {"Build": 4}

    def test_transition_week_day_counts_mirror_input(self):
        """The ``day_counts`` breakdown feeds §19.4 narrative
        ("5 of your 6 sessions are Build this week")."""
        result = compute_phase_kpi_priority_for_week(
            ["Base", "Build", "Build", "Build", None, None]
        )
        assert result.phase is Phase.BUILD
        assert result.day_counts == {"Base": 1, "Build": 3}

    def test_transition_week_tie_goes_to_later_phase(self):
        """2 Base + 2 Build = tie → Build wins; priority reflects Build."""
        result = compute_phase_kpi_priority_for_week(["Base", "Base", "Build", "Build"])
        assert result.phase is Phase.BUILD
        assert result.priority[0].kpi_id == "pace_consistency_tempo"

    def test_unknown_phases_excluded_from_day_counts(self):
        """``day_counts`` reflects only canonical phases — garbage
        values must not leak into the coach narrative."""
        result = compute_phase_kpi_priority_for_week(
            ["Peak", "Peak", "Hypertrophy", None]
        )
        assert result.phase is Phase.PEAK
        assert result.day_counts == {"Peak": 2}

    def test_iterator_input_is_consumed_once(self):
        """Callers may pass a generator; internal materialization
        must handle it correctly."""
        gen = (p for p in ["Taper", "Taper", "Taper"])
        result = compute_phase_kpi_priority_for_week(gen)
        assert result.phase is Phase.TAPER
        assert result.day_counts == {"Taper": 3}
