"""Threshold/Z4 segment pace from HR-qualified splits."""

from __future__ import annotations

from src.smartcoach_mobile_coach.execution_analytics.threshold_segment import (
    ThresholdHrZoneBounds,
    ThresholdSplitRow,
    aggregate_qualifying_threshold_splits,
    compute_run_threshold_segment_pace,
    select_qualifying_threshold_splits,
)

ZONES = ThresholdHrZoneBounds(
    z3_high=160.0,
    z4_low=161.0,
    z4_high=175.0,
    z5_low=176.0,
)


def _split(
    idx: int, hr: float, pace: float, distance: float = 1.0
) -> ThresholdSplitRow:
    return ThresholdSplitRow(
        split_index=idx,
        avg_hr=hr,
        pace_min_per_mi=pace,
        distance_mi=distance,
    )


def test_hr_z4_primary_qualification():
    splits = [_split(1, hr=165.0, pace=7.0)]
    qualifying = select_qualifying_threshold_splits(splits, ZONES)
    assert len(qualifying) == 1
    assert qualifying[0].tier == "z4"
    result = aggregate_qualifying_threshold_splits(qualifying)
    assert result.threshold_segment_pace_source == "splits_hr_z4"
    assert result.threshold_segment_confidence == "medium"


def test_hr_quality_fallback_when_no_z4_splits():
    splits = [
        _split(1, hr=160.5, pace=7.0),
        _split(2, hr=160.5, pace=7.1),
    ]
    qualifying = select_qualifying_threshold_splits(splits, ZONES)
    assert len(qualifying) == 2
    assert all(q.tier == "quality" for q in qualifying)
    result = aggregate_qualifying_threshold_splits(qualifying)
    assert result.threshold_segment_pace_source == "splits_hr_quality"
    assert result.threshold_segment_confidence == "medium"


def test_two_z4_splits_strong_evidence_high_confidence():
    splits = [
        _split(1, hr=125.0, pace=9.0),
        _split(2, hr=165.0, pace=7.0, distance=1.0),
        _split(3, hr=167.0, pace=7.1, distance=1.0),
        _split(4, hr=120.0, pace=9.5),
    ]
    qualifying = select_qualifying_threshold_splits(splits, ZONES)
    assert [q.split_index for q in qualifying] == [2, 3]
    result = aggregate_qualifying_threshold_splits(qualifying)
    assert result.threshold_segment_pace_source == "splits_hr_z4"
    assert result.threshold_segment_confidence == "high"
    assert result.threshold_segment_pace_min_per_mi == 7.05


def test_activity_avg_diagnostic_clears_chart_fields():
    splits = [_split(1, hr=130.0, pace=9.0)]
    result, qualifying = compute_run_threshold_segment_pace(
        splits, ZONES, activity_avg_pace_min_per_mi=8.0
    )
    assert result.threshold_segment_pace_source == "activity_avg"
    assert result.threshold_segment_pace_min_per_mi is None
    assert qualifying == []
