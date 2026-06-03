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
from src.smartcoach_mobile_coach.execution_analytics.threshold_segment import (
    ThresholdSplitRow,
)
from src.smartcoach_mobile_coach.execution_analytics.tempo_segment import TempoSplitRow


def _split(idx: int, hr: float, pace: float) -> TempoSplitRow:
    return TempoSplitRow(
        split_index=idx,
        avg_hr=hr,
        pace_min_per_mi=pace,
        distance_mi=1.0,
    )


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


def test_tempo_takes_priority_over_threshold_when_z3_present():
    splits = [
        _split(1, 125.0, 9.0),
        _split(2, 155.0, 7.5),
        _split(3, 157.0, 7.3),
        _split(4, 165.0, 7.0),
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
    assert kpis.n_z3_splits >= 2
    assert kpis.n_z4_splits >= 1
    system = classify_insights_system(
        moving_time_seconds=3600,
        avg_hr=155.0,
        z2_high=145.0,
        z3_high=160.0,
        kpis=kpis,
    )
    assert system == "tempo"
