"""Threshold run classification (Z4 splits) via execution_analytics SSOT."""

from __future__ import annotations

from src.smartcoach_mobile_coach.execution_analytics.classification import (
    classify_insights_system,
)
from src.smartcoach_mobile_coach.execution_analytics.kpi_primitives import (
    compute_split_kpis,
)
from src.smartcoach_mobile_coach.execution_analytics.thresholds import (
    THRESHOLD_RUN_MIN_Z4_SPLITS,
)
from src.smartcoach_mobile_coach.execution_analytics.tempo_segment import TempoSplitRow

# Shared zone profile for precedence tests (integer Karvonen-style bounds).
_Z2_LOW = 115.0
_Z2_HIGH = 145.0
_Z3_LOW = 146.0
_Z3_HIGH = 160.0
_Z4_LOW = 161.0
_Z4_HIGH = 175.0
_Z5_LOW = 176.0


def _split(idx: int, hr: float, pace: float = 7.0) -> TempoSplitRow:
    return TempoSplitRow(
        split_index=idx,
        avg_hr=hr,
        pace_min_per_mi=pace,
        distance_mi=1.0,
    )


def _classify(splits: list[TempoSplitRow], *, avg_hr: float) -> str | None:
    kpis = compute_split_kpis(
        splits,
        z2_low=_Z2_LOW,
        z2_high=_Z2_HIGH,
        z3_low=_Z3_LOW,
        z3_high=_Z3_HIGH,
        z4_low=_Z4_LOW,
        z4_high=_Z4_HIGH,
        z5_low=_Z5_LOW,
    )
    return classify_insights_system(
        moving_time_seconds=3600,
        avg_hr=avg_hr,
        z2_high=_Z2_HIGH,
        z3_high=_Z3_HIGH,
        kpis=kpis,
    )


def test_single_z4_spike_does_not_classify_as_threshold():
    """One Z4 mile in a long mostly-easy run must not become Threshold."""
    splits = (
        [_split(i, 142.0, 9.0) for i in range(1, 6)]
        + [_split(6, 145.5, 8.5), _split(7, 145.5, 8.5)]
        + [_split(8, 165.0, 7.0)]
    )
    kpis = compute_split_kpis(
        splits,
        z2_low=_Z2_LOW,
        z2_high=_Z2_HIGH,
        z3_low=_Z3_LOW,
        z3_high=_Z3_HIGH,
        z4_low=_Z4_LOW,
        z4_high=_Z4_HIGH,
        z5_low=_Z5_LOW,
    )
    assert kpis.n_z4_splits == 1
    assert kpis.n_z4_splits < THRESHOLD_RUN_MIN_Z4_SPLITS
    assert _classify(splits, avg_hr=143.0) != "threshold"


def test_two_z4_splits_classify_as_threshold():
    """Two Z4 split miles meet THRESHOLD_RUN_MIN_Z4_SPLITS (Tempo split rules do not apply)."""
    splits = (
        [_split(1, 165.0, 7.0), _split(2, 167.0, 7.1)]
        + [_split(i, 145.5, 8.5) for i in range(3, 5)]
        + [_split(i, 176.0, 7.5) for i in range(5, 9)]
    )
    kpis = compute_split_kpis(
        splits,
        z2_low=_Z2_LOW,
        z2_high=_Z2_HIGH,
        z3_low=_Z3_LOW,
        z3_high=_Z3_HIGH,
        z4_low=_Z4_LOW,
        z4_high=_Z4_HIGH,
        z5_low=_Z5_LOW,
    )
    assert kpis.n_z4_splits == THRESHOLD_RUN_MIN_Z4_SPLITS
    assert kpis.n_z3_splits == 0
    assert kpis.n_quality_splits < 3
    assert _classify(splits, avg_hr=168.0) == "threshold"


def test_mixed_z3_and_z4_with_tempo_split_evidence_stays_tempo():
    """Tempo split rules run before Threshold when two or more Z3 miles are present."""
    splits = [
        _split(1, 125.0, 9.0),
        _split(2, 155.0, 7.5),
        _split(3, 157.0, 7.3),
        _split(4, 165.0, 7.0),
        _split(5, 120.0, 9.5),
    ]
    kpis = compute_split_kpis(
        splits,
        z2_low=_Z2_LOW,
        z2_high=_Z2_HIGH,
        z3_low=_Z3_LOW,
        z3_high=_Z3_HIGH,
        z4_low=_Z4_LOW,
        z4_high=_Z4_HIGH,
        z5_low=_Z5_LOW,
    )
    assert kpis.n_z3_splits >= 2
    assert kpis.n_z4_splits >= 1
    assert _classify(splits, avg_hr=155.0) == "tempo"


def test_threshold_classified_via_z4_split_count_not_tempo():
    splits = [
        _split(1, 125.0, 9.0),
        _split(2, 165.0, 7.0),
        _split(3, 167.0, 7.1),
        _split(4, 168.0, 7.2),
        _split(5, 120.0, 9.5),
    ]
    kpis = compute_split_kpis(
        splits,
        z2_low=115.0,
        z2_high=145.0,
        z3_low=146.0,
        z3_high=160.0,
        z4_low=161.0,
        z4_high=175.0,
        z5_low=176.0,
    )
    assert kpis.n_z4_splits >= THRESHOLD_RUN_MIN_Z4_SPLITS
    assert kpis.n_z3_splits == 0
    system = classify_insights_system(
        moving_time_seconds=3600,
        avg_hr=165.0,
        z2_high=145.0,
        z3_high=160.0,
        kpis=kpis,
    )
    assert system == "threshold"
