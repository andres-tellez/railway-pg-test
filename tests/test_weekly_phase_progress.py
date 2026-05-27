"""
Tests for V1.6 Phase D 3D.6 — weekly phase-progress classifier.

Canonical producer: :mod:`src.services.phase.weekly_progress`. This
test file locks the spec-verbatim rule the user approved on 2026-04-21
against regressions:

* Priority-KPI execution aggregate thresholds (60 % / 50 %).
* Full status matrix over (AdherenceBand × PriorityKpiExecution).
* Fallback-to-all-runs when no priority-type runs exist this week.
* Phase → priority run type mapping (Base/Build/Peak/Taper).
* Edge cases: empty week, future week (all ``None`` inputs), Low
  band short-circuits independent of execution.
"""

from __future__ import annotations

import pytest

from src.services.phase.phase_priority import Phase
from src.services.phase.weekly_progress import (
    MOSTLY_OFF_MIN_FRACTION,
    MOSTLY_ON_TARGET_MIN_FRACTION,
    PHASE_PRIORITY_RUN_TYPE,
    PriorityKpiDeviation,
    PriorityKpiExecution,
    WeeklyPhaseProgress,
    aggregate_priority_kpi_for_phase,
    classify_priority_kpi_execution,
    classify_weekly_phase_progress,
    compute_weekly_phase_progress,
    priority_run_type_for_phase,
)
from src.services.scoring.adherence import AdherenceBand
from src.services.scoring.deviation import DeviationDirection
from src.smartcoach_mobile_coach.runner_profile.plan_run_type_registry import (
    RUN_TYPE_EASY,
    RUN_TYPE_LONG,
    RUN_TYPE_RECOVERY,
    RUN_TYPE_TEMPO,
)


# ---------------------------------------------------------------------
# Threshold contracts (lock the spec numbers)
# ---------------------------------------------------------------------


def test_thresholds_are_spec_locked():
    assert MOSTLY_ON_TARGET_MIN_FRACTION == 0.60
    assert MOSTLY_OFF_MIN_FRACTION == 0.50


# ---------------------------------------------------------------------
# Phase → priority run type mapping
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "phase,expected",
    [
        (Phase.BASE, RUN_TYPE_EASY),
        (Phase.BUILD, RUN_TYPE_TEMPO),
        (Phase.PEAK, RUN_TYPE_LONG),
        (Phase.TAPER, RUN_TYPE_LONG),
    ],
)
def test_priority_run_type_mapping(phase, expected):
    assert priority_run_type_for_phase(phase) == expected
    assert PHASE_PRIORITY_RUN_TYPE[phase] == expected


def test_priority_run_type_mapping_covers_all_v16_phases():
    assert set(PHASE_PRIORITY_RUN_TYPE.keys()) == set(Phase)


# ---------------------------------------------------------------------
# classify_priority_kpi_execution — threshold semantics
# ---------------------------------------------------------------------


def _ot(n):
    return [DeviationDirection.ON_TARGET] * n


def _th(n):
    return [DeviationDirection.TOO_HARD] * n


def _te(n):
    return [DeviationDirection.TOO_EASY] * n


def test_all_on_target_is_mostly_on_target():
    assert (
        classify_priority_kpi_execution(_ot(3)) == PriorityKpiExecution.MOSTLY_ON_TARGET
    )


def test_exactly_60_pct_on_target_is_mostly_on_target():
    # 3/5 = 0.60 → threshold is inclusive.
    samples = _ot(3) + _th(2)
    assert (
        classify_priority_kpi_execution(samples)
        == PriorityKpiExecution.MOSTLY_ON_TARGET
    )


def test_just_below_60_pct_is_not_mostly_on_target():
    # 2/5 = 0.40 → not enough for on_target; 3/5 = 0.60 off → mostly_off.
    samples = _ot(2) + _th(3)
    assert classify_priority_kpi_execution(samples) == PriorityKpiExecution.MOSTLY_OFF


def test_exactly_50_pct_off_is_mostly_off():
    # 2 off / 4 total = 0.50. 2 on / 4 = 0.50 on < 0.60 → MOSTLY_OFF.
    samples = _ot(2) + _th(2)
    assert classify_priority_kpi_execution(samples) == PriorityKpiExecution.MOSTLY_OFF


def test_too_easy_counts_as_off():
    # 1 on + 2 too_easy = 2/3 off = 0.67 ≥ 0.50 → MOSTLY_OFF.
    samples = _ot(1) + _te(2)
    assert classify_priority_kpi_execution(samples) == PriorityKpiExecution.MOSTLY_OFF


def test_too_easy_and_too_hard_are_unioned_into_off():
    # 1 on + 1 too_easy + 1 too_hard = 2/3 off → MOSTLY_OFF.
    samples = _ot(1) + _te(1) + _th(1)
    assert classify_priority_kpi_execution(samples) == PriorityKpiExecution.MOSTLY_OFF


def test_mixed_bucket_falls_between_thresholds():
    # 2 on + 1 too_hard + 2 None-ignored = 2/3 on = 0.67 — wait that's ≥0.60.
    # Use 3 on + 3 misc where neither threshold is hit.
    # 3 on / 7 = 0.43 < 0.60 on.  off = 2 / 7 = 0.286 < 0.50 → MIXED.
    samples = _ot(3) + _th(2) + [None, None]
    # None entries are dropped → n=5, 3 on / 5 = 0.60 → MOSTLY_ON_TARGET.
    # So redo with fewer None and more on-fraction just below 0.60.
    # 2 on + 2 too_hard + 1 None — filtered n=4; 2/4 = 0.50 on < 0.60.
    # off 2/4 = 0.50 → MOSTLY_OFF. Still not MIXED.
    # To land in MIXED we need 0.60 > on_frac AND 0.50 > off_frac simultaneously.
    # That requires on_count/n < 0.60 AND off_count/n < 0.50. E.g. n=7,
    # on=4 (0.571), off=3 (0.428) → neither threshold met → MIXED.
    samples = _ot(4) + _th(3)
    result = classify_priority_kpi_execution(samples)
    assert result == PriorityKpiExecution.MIXED


def test_none_entries_are_dropped_before_classification():
    # Only two non-None samples: both ON_TARGET → 100 % → MOSTLY_ON_TARGET.
    samples = [None, DeviationDirection.ON_TARGET, None, DeviationDirection.ON_TARGET]
    assert (
        classify_priority_kpi_execution(samples)
        == PriorityKpiExecution.MOSTLY_ON_TARGET
    )


def test_all_none_returns_none():
    assert classify_priority_kpi_execution([None, None, None]) is None


def test_empty_iterable_returns_none():
    assert classify_priority_kpi_execution([]) is None


# ---------------------------------------------------------------------
# aggregate_priority_kpi_for_phase — priority filter + fallback
# ---------------------------------------------------------------------


def test_priority_filter_uses_phase_top_kpi_run_type():
    # Build → Tempo is the priority run type. Tempos all on_target;
    # other types all off. The aggregate must follow Tempo only.
    entries = [
        PriorityKpiDeviation(RUN_TYPE_TEMPO, DeviationDirection.ON_TARGET),
        PriorityKpiDeviation(RUN_TYPE_TEMPO, DeviationDirection.ON_TARGET),
        PriorityKpiDeviation(RUN_TYPE_EASY, DeviationDirection.TOO_HARD),
        PriorityKpiDeviation(RUN_TYPE_LONG, DeviationDirection.TOO_EASY),
    ]
    assert (
        aggregate_priority_kpi_for_phase(Phase.BUILD, entries)
        == PriorityKpiExecution.MOSTLY_ON_TARGET
    )


def test_fallback_to_all_runs_when_no_priority_type_this_week():
    # Build phase but no Tempos — must classify off full set.
    entries = [
        PriorityKpiDeviation(RUN_TYPE_EASY, DeviationDirection.ON_TARGET),
        PriorityKpiDeviation(RUN_TYPE_EASY, DeviationDirection.ON_TARGET),
        PriorityKpiDeviation(RUN_TYPE_LONG, DeviationDirection.ON_TARGET),
    ]
    # All 3 on_target across non-priority runs → MOSTLY_ON_TARGET.
    assert (
        aggregate_priority_kpi_for_phase(Phase.BUILD, entries)
        == PriorityKpiExecution.MOSTLY_ON_TARGET
    )


def test_fallback_respects_none_deviations_in_priority_type():
    # Priority runs all have ``deviation=None`` → same as "no priority
    # runs present" → fall back to full set.
    entries = [
        PriorityKpiDeviation(RUN_TYPE_TEMPO, None),
        PriorityKpiDeviation(RUN_TYPE_EASY, DeviationDirection.TOO_HARD),
        PriorityKpiDeviation(RUN_TYPE_EASY, DeviationDirection.TOO_HARD),
    ]
    # Full set: 2/2 off = 1.0 ≥ 0.50 → MOSTLY_OFF.
    assert (
        aggregate_priority_kpi_for_phase(Phase.BUILD, entries)
        == PriorityKpiExecution.MOSTLY_OFF
    )


def test_no_runs_at_all_returns_none():
    assert aggregate_priority_kpi_for_phase(Phase.BASE, []) is None


def test_phase_none_short_circuits_to_full_set():
    # ``phase is None`` skips filtering and aggregates across everything.
    entries = [
        PriorityKpiDeviation(RUN_TYPE_EASY, DeviationDirection.ON_TARGET),
        PriorityKpiDeviation(RUN_TYPE_LONG, DeviationDirection.TOO_HARD),
    ]
    # 1 on / 2 = 0.50 < 0.60 on.  off 1/2 = 0.50 ≥ 0.50 → MOSTLY_OFF.
    assert (
        aggregate_priority_kpi_for_phase(None, entries)
        == PriorityKpiExecution.MOSTLY_OFF
    )


# ---------------------------------------------------------------------
# classify_weekly_phase_progress — full matrix
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "band,aggregate,expected",
    [
        # High row
        (
            AdherenceBand.HIGH,
            PriorityKpiExecution.MOSTLY_ON_TARGET,
            WeeklyPhaseProgress.ON_TRACK,
        ),
        (AdherenceBand.HIGH, PriorityKpiExecution.MIXED, WeeklyPhaseProgress.ON_TRACK),
        (
            AdherenceBand.HIGH,
            PriorityKpiExecution.MOSTLY_OFF,
            WeeklyPhaseProgress.CLOSE,
        ),
        # Medium row
        (
            AdherenceBand.MEDIUM,
            PriorityKpiExecution.MOSTLY_ON_TARGET,
            WeeklyPhaseProgress.CLOSE,
        ),
        (AdherenceBand.MEDIUM, PriorityKpiExecution.MIXED, WeeklyPhaseProgress.CLOSE),
        (
            AdherenceBand.MEDIUM,
            PriorityKpiExecution.MOSTLY_OFF,
            WeeklyPhaseProgress.OFF_TRACK,
        ),
        # Low row — always off_track regardless of aggregate
        (
            AdherenceBand.LOW,
            PriorityKpiExecution.MOSTLY_ON_TARGET,
            WeeklyPhaseProgress.OFF_TRACK,
        ),
        (AdherenceBand.LOW, PriorityKpiExecution.MIXED, WeeklyPhaseProgress.OFF_TRACK),
        (
            AdherenceBand.LOW,
            PriorityKpiExecution.MOSTLY_OFF,
            WeeklyPhaseProgress.OFF_TRACK,
        ),
    ],
)
def test_status_matrix_exhaustive(band, aggregate, expected):
    assert classify_weekly_phase_progress(band, aggregate) == expected


@pytest.mark.parametrize("band", list(AdherenceBand))
def test_aggregate_none_returns_none(band):
    assert classify_weekly_phase_progress(band, None) is None


@pytest.mark.parametrize("aggregate", list(PriorityKpiExecution))
def test_band_none_returns_none(aggregate):
    # Future week / empty plan week contract.
    assert classify_weekly_phase_progress(None, aggregate) is None


def test_both_none_returns_none():
    assert classify_weekly_phase_progress(None, None) is None


# ---------------------------------------------------------------------
# compute_weekly_phase_progress — full composer contract
# ---------------------------------------------------------------------


def test_composer_wires_phase_filter_band_and_matrix():
    entries = [
        PriorityKpiDeviation(RUN_TYPE_EASY, DeviationDirection.ON_TARGET),
        PriorityKpiDeviation(RUN_TYPE_EASY, DeviationDirection.ON_TARGET),
        PriorityKpiDeviation(RUN_TYPE_EASY, DeviationDirection.TOO_HARD),
        PriorityKpiDeviation(RUN_TYPE_LONG, DeviationDirection.TOO_HARD),
    ]
    # Base priority = Easy. 2 on / 3 easy = 0.67 ≥ 0.60 → mostly_on_target.
    # High band + mostly_on_target → on_track.
    result = compute_weekly_phase_progress(Phase.BASE, AdherenceBand.HIGH, entries)
    assert result.status == WeeklyPhaseProgress.ON_TRACK
    assert result.band == AdherenceBand.HIGH
    assert result.aggregate == PriorityKpiExecution.MOSTLY_ON_TARGET
    assert result.priority_run_type == RUN_TYPE_EASY
    assert result.priority_run_count == 3
    assert result.total_run_count == 4


def test_composer_reports_none_status_for_future_or_empty_week():
    # Future-week pattern: caller passes band=None and entries=[].
    result = compute_weekly_phase_progress(Phase.BUILD, None, [])
    assert result.status is None
    assert result.band is None
    assert result.aggregate is None
    assert result.priority_run_count == 0
    assert result.total_run_count == 0


def test_composer_low_adherence_is_off_track_even_with_perfect_execution():
    # Locked spec: Low adherence → off_track, always.
    entries = [
        PriorityKpiDeviation(RUN_TYPE_EASY, DeviationDirection.ON_TARGET),
        PriorityKpiDeviation(RUN_TYPE_EASY, DeviationDirection.ON_TARGET),
    ]
    result = compute_weekly_phase_progress(Phase.BASE, AdherenceBand.LOW, entries)
    assert result.status == WeeklyPhaseProgress.OFF_TRACK
    # Aggregate still computed — transparency field.
    assert result.aggregate == PriorityKpiExecution.MOSTLY_ON_TARGET


def test_composer_fallback_to_full_set_when_no_priority_runs():
    # Build priority = Tempo, but user only did easy + long.
    entries = [
        PriorityKpiDeviation(RUN_TYPE_EASY, DeviationDirection.ON_TARGET),
        PriorityKpiDeviation(RUN_TYPE_LONG, DeviationDirection.ON_TARGET),
    ]
    result = compute_weekly_phase_progress(Phase.BUILD, AdherenceBand.MEDIUM, entries)
    # Fallback aggregate: 2/2 on_target → mostly_on_target.
    # Medium + mostly_on_target → close.
    assert result.status == WeeklyPhaseProgress.CLOSE
    assert result.priority_run_type == RUN_TYPE_TEMPO
    assert result.priority_run_count == 0
    assert result.total_run_count == 2


def test_composer_phase_none_means_no_priority_type_reported():
    entries = [
        PriorityKpiDeviation(RUN_TYPE_RECOVERY, DeviationDirection.ON_TARGET),
    ]
    result = compute_weekly_phase_progress(None, AdherenceBand.HIGH, entries)
    assert result.priority_run_type is None
    assert result.priority_run_count == 0
    assert result.status == WeeklyPhaseProgress.ON_TRACK


# ---------------------------------------------------------------------
# JSON wire-compatibility
# ---------------------------------------------------------------------


def test_enum_wire_values_are_spec_exact():
    assert WeeklyPhaseProgress.ON_TRACK.value == "on_track"
    assert WeeklyPhaseProgress.CLOSE.value == "close"
    assert WeeklyPhaseProgress.OFF_TRACK.value == "off_track"
    assert PriorityKpiExecution.MOSTLY_ON_TARGET.value == "mostly_on_target"
    assert PriorityKpiExecution.MOSTLY_OFF.value == "mostly_off"
    assert PriorityKpiExecution.MIXED.value == "mixed"
