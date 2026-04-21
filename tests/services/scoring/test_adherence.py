"""
Unit tests for ``src.services.scoring.adherence`` (V1.6 §7, Phase A
item 5).

Lock the deterministic weekly adherence contract so:

  * the §7 thresholds (50 % completion, 70 / 90 bands) cannot drift,
  * the numerator / denominator semantics honor the §6 plan_status
    enum (unplanned excluded; matched-but-<50% does NOT count),
  * the band boundary wording "70 % – 90 %" (closed interval) is
    enforced — exactly 70.0 is Medium, exactly 90.0 is Medium,
  * the empty-week (``planned_runs == 0``) case returns None /
    None rather than dividing by zero.
"""

from __future__ import annotations

import pytest

from src.services.plan.plan_status import PlanStatus
from src.services.scoring.adherence import (
    ADHERENCE_HIGH_MIN_EXCLUSIVE_PCT,
    ADHERENCE_LOW_MAX_EXCLUSIVE_PCT,
    AdherenceBand,
    WeeklyAdherenceEntry,
    WeeklyAdherenceResult,
    classify_adherence_band,
    compute_weekly_adherence,
)
from src.services.scoring.completion import COMPLETION_THRESHOLD_PCT


# ---------------------------------------------------------------------------
# Constants + enum wire contract.
# ---------------------------------------------------------------------------


class TestEnumAndConstants:
    def test_enum_wire_values(self):
        assert AdherenceBand.LOW.value == "low"
        assert AdherenceBand.MEDIUM.value == "medium"
        assert AdherenceBand.HIGH.value == "high"

    def test_enum_is_str_based_for_json(self):
        import json

        assert json.dumps(AdherenceBand.HIGH.value) == '"high"'

    def test_enum_has_exactly_three_values(self):
        """Contract: §7 defines exactly Low / Medium / High. A fourth
        band would reshape §19.8 tone + §16 adaptation — lock it."""
        assert len(list(AdherenceBand)) == 3

    def test_band_thresholds_are_named_constants(self):
        """§X.5: no inlined ``70`` / ``90`` magic numbers at call sites."""
        assert ADHERENCE_LOW_MAX_EXCLUSIVE_PCT == 70.0
        assert ADHERENCE_HIGH_MIN_EXCLUSIVE_PCT == 90.0

    def test_completion_threshold_matches_spec(self):
        """Sanity: the 50 % rule we import from ``completion`` is the
        single-source-of-truth threshold §7 anchors to."""
        assert COMPLETION_THRESHOLD_PCT == 50.0


# ---------------------------------------------------------------------------
# Band classifier — boundary + out-of-range behavior.
# ---------------------------------------------------------------------------


class TestClassifyAdherenceBand:
    def test_none_input_returns_none(self):
        """Empty-week / undefined adherence must not get a band."""
        assert classify_adherence_band(None) is None

    def test_zero_is_low(self):
        assert classify_adherence_band(0.0) is AdherenceBand.LOW

    def test_just_below_70_is_low(self):
        assert classify_adherence_band(69.999) is AdherenceBand.LOW

    def test_exactly_70_is_medium(self):
        """§7 wording '70 % – 90 %' is closed — 70 is Medium."""
        assert classify_adherence_band(70.0) is AdherenceBand.MEDIUM

    def test_midrange_is_medium(self):
        assert classify_adherence_band(80.0) is AdherenceBand.MEDIUM

    def test_exactly_90_is_medium_not_high(self):
        """High starts strictly above 90 — lock the endpoint."""
        assert classify_adherence_band(90.0) is AdherenceBand.MEDIUM

    def test_just_above_90_is_high(self):
        assert classify_adherence_band(90.001) is AdherenceBand.HIGH

    def test_100_is_high(self):
        assert classify_adherence_band(100.0) is AdherenceBand.HIGH

    def test_above_100_still_classifies_high(self):
        """Overshoot (shouldn't happen given numerator ≤ denominator,
        but defensive) must not crash the classifier."""
        assert classify_adherence_band(125.0) is AdherenceBand.HIGH

    def test_negative_input_classifies_low(self):
        """Defensive: a buggy caller passing a negative must not
        surface as Medium/High. Low is the safe band for 'signal
        malformed'."""
        assert classify_adherence_band(-10.0) is AdherenceBand.LOW


# ---------------------------------------------------------------------------
# Weekly aggregator — numerator / denominator rules.
# ---------------------------------------------------------------------------


class TestComputeWeeklyAdherenceEmptyCases:
    def test_no_entries_returns_none_ratio_none_band(self):
        """Empty week → undefined adherence, not zero."""
        result = compute_weekly_adherence([])
        assert result.adherence_runs_pct is None
        assert result.band is None
        assert result.completed_runs == 0
        assert result.planned_runs == 0

    def test_only_unplanned_entries_returns_none_ratio(self):
        """§7 unplanned exclusion: if the whole week is unplanned
        runs, there is no plan to adhere to → None, not 0."""
        entries = [
            WeeklyAdherenceEntry(
                plan_status=PlanStatus.UNPLANNED,
                completion_pct=None,
                planned_miles=None,
                actual_miles=5.0,
            ),
            WeeklyAdherenceEntry(
                plan_status=PlanStatus.UNPLANNED,
                completion_pct=None,
                planned_miles=None,
                actual_miles=3.0,
            ),
        ]
        result = compute_weekly_adherence(entries)
        assert result.adherence_runs_pct is None
        assert result.completed_runs == 0
        assert result.planned_runs == 0
        assert result.band is None
        assert result.actual_miles_matched_total == 0.0


class TestComputeWeeklyAdherenceNumerator:
    """What counts toward ``completed_runs``."""

    def test_executed_above_threshold_counts_as_completed(self):
        entries = [
            WeeklyAdherenceEntry(
                plan_status=PlanStatus.EXECUTED,
                completion_pct=85.0,
                planned_miles=6.0,
                actual_miles=5.1,
            ),
        ]
        result = compute_weekly_adherence(entries)
        assert result.completed_runs == 1
        assert result.planned_runs == 1
        assert result.adherence_runs_pct == 100.0

    def test_executed_at_exactly_50_counts_as_completed(self):
        """§7 threshold is ≥ 50 (from :mod:`completion`), inclusive."""
        entries = [
            WeeklyAdherenceEntry(
                plan_status=PlanStatus.EXECUTED,
                completion_pct=50.0,
                planned_miles=10.0,
                actual_miles=5.0,
            ),
        ]
        result = compute_weekly_adherence(entries)
        assert result.completed_runs == 1

    def test_executed_below_threshold_does_not_count(self):
        """Spec: 2-mi attempt on 10-mi Long Run ≠ completed Long Run."""
        entries = [
            WeeklyAdherenceEntry(
                plan_status=PlanStatus.EXECUTED,
                completion_pct=20.0,
                planned_miles=10.0,
                actual_miles=2.0,
            ),
        ]
        result = compute_weekly_adherence(entries)
        assert result.completed_runs == 0
        assert result.planned_runs == 1
        assert result.adherence_runs_pct == 0.0

    def test_executed_with_none_completion_does_not_count(self):
        """Matched but completion undefined (zero planned, etc.) →
        conservative: does NOT count. Consistent with
        ``is_run_completed(None) == False``."""
        entries = [
            WeeklyAdherenceEntry(
                plan_status=PlanStatus.EXECUTED,
                completion_pct=None,
                planned_miles=None,
                actual_miles=5.0,
            ),
        ]
        result = compute_weekly_adherence(entries)
        assert result.completed_runs == 0
        assert result.planned_runs == 1

    def test_in_progress_at_threshold_counts(self):
        """IN_PROGRESS with a matched activity ≥ 50 % counts — gives
        a faithful 'so-far' adherence snapshot mid-week."""
        entries = [
            WeeklyAdherenceEntry(
                plan_status=PlanStatus.IN_PROGRESS,
                completion_pct=75.0,
                planned_miles=4.0,
                actual_miles=3.0,
            ),
        ]
        result = compute_weekly_adherence(entries)
        assert result.completed_runs == 1

    def test_missed_never_counts_even_with_nonnull_completion(self):
        """MISSED has no matched activity by definition; even a
        stray ``completion_pct`` payload must not flip it into the
        numerator (defensive — single path through the gate)."""
        entries = [
            WeeklyAdherenceEntry(
                plan_status=PlanStatus.MISSED,
                completion_pct=99.0,
                planned_miles=6.0,
                actual_miles=None,
            ),
        ]
        result = compute_weekly_adherence(entries)
        assert result.completed_runs == 0
        assert result.planned_runs == 1

    def test_planned_only_never_counts(self):
        entries = [
            WeeklyAdherenceEntry(
                plan_status=PlanStatus.PLANNED_ONLY,
                completion_pct=None,
                planned_miles=8.0,
                actual_miles=None,
            ),
        ]
        result = compute_weekly_adherence(entries)
        assert result.completed_runs == 0
        assert result.planned_runs == 1


class TestComputeWeeklyAdherenceDenominator:
    """What counts toward ``planned_runs``."""

    def test_unplanned_is_excluded_from_both_sides(self):
        """§7 'Unplanned Runs and Adherence': unplanned contributes
        nothing to numerator OR denominator."""
        entries = [
            WeeklyAdherenceEntry(
                plan_status=PlanStatus.EXECUTED,
                completion_pct=90.0,
                planned_miles=5.0,
                actual_miles=4.5,
            ),
            WeeklyAdherenceEntry(
                plan_status=PlanStatus.UNPLANNED,
                completion_pct=None,
                planned_miles=None,
                actual_miles=3.0,
            ),
        ]
        result = compute_weekly_adherence(entries)
        assert result.completed_runs == 1
        assert result.planned_runs == 1
        assert result.adherence_runs_pct == 100.0

    def test_all_planned_statuses_are_denominator(self):
        """PLANNED_ONLY + IN_PROGRESS + EXECUTED + MISSED all count
        in the denominator; UNPLANNED does not."""
        entries = [
            WeeklyAdherenceEntry(plan_status=PlanStatus.PLANNED_ONLY),
            WeeklyAdherenceEntry(plan_status=PlanStatus.IN_PROGRESS),
            WeeklyAdherenceEntry(plan_status=PlanStatus.EXECUTED),
            WeeklyAdherenceEntry(plan_status=PlanStatus.MISSED),
            WeeklyAdherenceEntry(plan_status=PlanStatus.UNPLANNED),
        ]
        result = compute_weekly_adherence(entries)
        assert result.planned_runs == 4


# ---------------------------------------------------------------------------
# Full-week scenarios — ratio + band round-trip.
# ---------------------------------------------------------------------------


class TestComputeWeeklyAdherenceFullScenarios:
    @pytest.mark.parametrize(
        "completed,planned,expected_pct,expected_band",
        [
            (0, 4, 0.0, AdherenceBand.LOW),
            (2, 4, 50.0, AdherenceBand.LOW),
            (3, 5, 60.0, AdherenceBand.LOW),
            # exactly 70 → Medium.
            (7, 10, 70.0, AdherenceBand.MEDIUM),
            (4, 5, 80.0, AdherenceBand.MEDIUM),
            (9, 10, 90.0, AdherenceBand.MEDIUM),
            # strictly above 90 → High. 10/11 ≈ 90.909...
            (10, 11, pytest.approx(90.9090909, abs=1e-6), AdherenceBand.HIGH),
            (4, 4, 100.0, AdherenceBand.HIGH),
        ],
    )
    def test_ratio_and_band_matrix(
        self, completed, planned, expected_pct, expected_band
    ):
        entries: list[WeeklyAdherenceEntry] = []
        for _ in range(completed):
            entries.append(
                WeeklyAdherenceEntry(
                    plan_status=PlanStatus.EXECUTED,
                    completion_pct=90.0,
                    planned_miles=5.0,
                    actual_miles=5.0,
                )
            )
        for _ in range(planned - completed):
            entries.append(
                WeeklyAdherenceEntry(
                    plan_status=PlanStatus.MISSED,
                    completion_pct=None,
                    planned_miles=5.0,
                    actual_miles=None,
                )
            )
        result = compute_weekly_adherence(entries)
        assert result.completed_runs == completed
        assert result.planned_runs == planned
        assert result.adherence_runs_pct == expected_pct
        assert result.band is expected_band

    def test_below_50_executed_lowers_adherence_but_keeps_denominator(
        self,
    ):
        """Classic 'showed up, bailed early' scenario: 3 of 4 planned
        runs were started but one was <50%. Adherence = 2/4 = 50.0."""
        entries = [
            WeeklyAdherenceEntry(
                plan_status=PlanStatus.EXECUTED,
                completion_pct=95.0,
                planned_miles=5.0,
                actual_miles=5.0,
            ),
            WeeklyAdherenceEntry(
                plan_status=PlanStatus.EXECUTED,
                completion_pct=80.0,
                planned_miles=4.0,
                actual_miles=3.2,
            ),
            WeeklyAdherenceEntry(
                plan_status=PlanStatus.EXECUTED,
                completion_pct=30.0,  # below 50 → missed for adherence
                planned_miles=10.0,
                actual_miles=3.0,
            ),
            WeeklyAdherenceEntry(
                plan_status=PlanStatus.MISSED,
                completion_pct=None,
                planned_miles=6.0,
                actual_miles=None,
            ),
        ]
        result = compute_weekly_adherence(entries)
        assert result.completed_runs == 2
        assert result.planned_runs == 4
        assert result.adherence_runs_pct == 50.0
        assert result.band is AdherenceBand.LOW


# ---------------------------------------------------------------------------
# Weekly completion_miles_pct — supporting metric.
# ---------------------------------------------------------------------------


class TestComputeWeeklyAdherenceMilesAggregate:
    def test_miles_aggregate_matches_spec_formula(self):
        """§7: weekly completion_miles_pct = sum(actual_on_planned) /
        sum(planned_miles). 25 / 30 = 83.333..."""
        entries = [
            WeeklyAdherenceEntry(
                plan_status=PlanStatus.EXECUTED,
                completion_pct=100.0,
                planned_miles=10.0,
                actual_miles=10.0,
            ),
            WeeklyAdherenceEntry(
                plan_status=PlanStatus.EXECUTED,
                completion_pct=100.0,
                planned_miles=10.0,
                actual_miles=10.0,
            ),
            WeeklyAdherenceEntry(
                plan_status=PlanStatus.EXECUTED,
                completion_pct=50.0,
                planned_miles=10.0,
                actual_miles=5.0,
            ),
        ]
        result = compute_weekly_adherence(entries)
        assert result.planned_miles_total == 30.0
        assert result.actual_miles_matched_total == 25.0
        assert result.completion_miles_pct_weekly == pytest.approx(
            83.33333333, abs=1e-6
        )

    def test_missed_runs_reduce_weekly_miles_completion(self):
        """A dropped long run correctly lowers weekly mileage
        completion even if the executed shorter runs hit their own
        targets. Denominator = planned, not matched-planned."""
        entries = [
            WeeklyAdherenceEntry(
                plan_status=PlanStatus.EXECUTED,
                completion_pct=100.0,
                planned_miles=4.0,
                actual_miles=4.0,
            ),
            WeeklyAdherenceEntry(
                plan_status=PlanStatus.MISSED,
                completion_pct=None,
                planned_miles=16.0,
                actual_miles=None,
            ),
        ]
        result = compute_weekly_adherence(entries)
        # 4 / 20 = 20%
        assert result.completion_miles_pct_weekly == pytest.approx(20.0, abs=1e-6)

    def test_unplanned_miles_do_not_inflate_aggregate(self):
        """A 10-mi unplanned run must not count toward the weekly
        mileage numerator (§7 unplanned exclusion applies to both
        ratio and miles aggregate)."""
        entries = [
            WeeklyAdherenceEntry(
                plan_status=PlanStatus.EXECUTED,
                completion_pct=100.0,
                planned_miles=5.0,
                actual_miles=5.0,
            ),
            WeeklyAdherenceEntry(
                plan_status=PlanStatus.UNPLANNED,
                completion_pct=None,
                planned_miles=None,
                actual_miles=10.0,  # must not contribute
            ),
        ]
        result = compute_weekly_adherence(entries)
        assert result.completion_miles_pct_weekly == 100.0

    def test_no_planned_miles_returns_none(self):
        """A week with planned runs but no planned miles (degenerate
        DB state) → None, not division-by-zero."""
        entries = [
            WeeklyAdherenceEntry(
                plan_status=PlanStatus.MISSED,
                completion_pct=None,
                planned_miles=None,
                actual_miles=None,
            ),
        ]
        result = compute_weekly_adherence(entries)
        assert result.completion_miles_pct_weekly is None
        assert result.planned_miles_total == 0.0

    def test_zero_or_negative_planned_miles_is_ignored(self):
        """Defensive: 0-mile or negative planned (bad ETL data) must
        not inflate or negate the aggregate."""
        entries = [
            WeeklyAdherenceEntry(
                plan_status=PlanStatus.EXECUTED,
                completion_pct=100.0,
                planned_miles=5.0,
                actual_miles=5.0,
            ),
            WeeklyAdherenceEntry(
                plan_status=PlanStatus.EXECUTED,
                completion_pct=100.0,
                planned_miles=0.0,
                actual_miles=2.0,
            ),
            WeeklyAdherenceEntry(
                plan_status=PlanStatus.EXECUTED,
                completion_pct=100.0,
                planned_miles=-3.0,
                actual_miles=1.0,
            ),
        ]
        result = compute_weekly_adherence(entries)
        assert result.planned_miles_total == 5.0
        assert result.actual_miles_matched_total == 8.0  # raw sum, no clamp
        # 8/5 = 160% → a dangerously-overshot week. The aggregate
        # correctly reports it rather than clipping — the signal is
        # meaningful to the coach (§19 stronger emphasis).
        assert result.completion_miles_pct_weekly == pytest.approx(160.0)


# ---------------------------------------------------------------------------
# Return-type contract.
# ---------------------------------------------------------------------------


class TestResultShape:
    def test_result_is_named_tuple_with_expected_fields(self):
        """Lock the public wire contract — Phase B consumers (and
        mobile types) rely on field names."""
        result = compute_weekly_adherence([])
        assert isinstance(result, WeeklyAdherenceResult)
        assert set(result._fields) == {
            "adherence_runs_pct",
            "completed_runs",
            "planned_runs",
            "band",
            "completion_miles_pct_weekly",
            "planned_miles_total",
            "actual_miles_matched_total",
        }
