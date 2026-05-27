"""Unit tests for executed Tempo/Z3 segment pace (HR-qualified splits)."""

from __future__ import annotations

from src.smartcoach_mobile_coach.tempo_kpi.tempo_segment_pace import (
    TempoHrZoneBounds,
    TempoSplitRow,
    aggregate_qualifying_tempo_splits,
    combine_weekly_tempo_segment_pace,
    compute_run_tempo_segment_pace,
    select_qualifying_tempo_splits,
)

ZONES = TempoHrZoneBounds(
    z2_high=145.0,
    z3_low=146.0,
    z3_high=160.0,
    z4_low=161.0,
)


def _split(
    idx: int,
    *,
    hr: float,
    pace: float,
    distance: float = 1.0,
) -> TempoSplitRow:
    return TempoSplitRow(
        split_index=idx,
        avg_hr=hr,
        pace_min_per_mi=pace,
        distance_mi=distance,
    )


def test_warmup_tempo_cooldown_uses_only_hr_qualified_middle_splits():
    """5-mile W/T/C: only Z3 HR miles count — not a blind middle average."""
    splits = [
        _split(1, hr=125.0, pace=9.5),
        _split(2, hr=155.0, pace=7.5),
        _split(3, hr=157.0, pace=7.3),
        _split(4, hr=130.0, pace=9.0),
        _split(5, hr=120.0, pace=10.0),
    ]
    qualifying = select_qualifying_tempo_splits(splits, ZONES)
    assert [q.split_index for q in qualifying] == [2, 3]
    result, _ = compute_run_tempo_segment_pace(splits, ZONES)
    assert result.tempo_segment_pace_source == "splits_hr_z3"
    assert result.tempo_segment_confidence == "high"
    assert result.tempo_segment_pace_min_per_mi == 7.4


def test_does_not_average_middle_without_hr_qualification():
    """Trimmed middle miles with easy HR must not produce segment pace."""
    splits = [
        _split(1, hr=120.0, pace=9.0),
        _split(2, hr=130.0, pace=8.5),
        _split(3, hr=132.0, pace=8.4),
        _split(4, hr=133.0, pace=8.3),
        _split(5, hr=118.0, pace=9.2),
    ]
    qualifying = select_qualifying_tempo_splits(splits, ZONES)
    assert qualifying == []
    result, _ = compute_run_tempo_segment_pace(
        splits,
        ZONES,
        activity_avg_pace_min_per_mi=8.6,
    )
    assert result.tempo_segment_pace_min_per_mi is None
    assert result.tempo_segment_pace_source == "activity_avg"
    assert result.allows_full_gyor() is False


def test_hr_z3_primary_qualification():
    splits = [_split(1, hr=150.0, pace=7.0)]
    qualifying = select_qualifying_tempo_splits(splits, ZONES)
    assert len(qualifying) == 1
    assert qualifying[0].tier == "z3"
    result = aggregate_qualifying_tempo_splits(qualifying)
    assert result.tempo_segment_pace_source == "splits_hr_z3"
    assert result.tempo_segment_confidence == "medium"


def test_hr_quality_fallback_when_no_z3_splits():
    splits = [
        _split(1, hr=161.0, pace=7.0),
        _split(2, hr=161.0, pace=7.1),
    ]
    qualifying = select_qualifying_tempo_splits(splits, ZONES)
    assert len(qualifying) == 2
    assert all(q.tier == "quality" for q in qualifying)
    result = aggregate_qualifying_tempo_splits(qualifying)
    assert result.tempo_segment_pace_source == "splits_hr_quality"
    assert result.tempo_segment_confidence == "medium"


def test_first_and_last_split_excluded_when_enough_splits():
    splits = [
        _split(1, hr=155.0, pace=6.5),
        _split(2, hr=156.0, pace=7.0),
        _split(3, hr=157.0, pace=7.1),
    ]
    qualifying = select_qualifying_tempo_splits(splits, ZONES)
    assert [q.split_index for q in qualifying] == [2]
    result = aggregate_qualifying_tempo_splits(qualifying)
    assert result.tempo_segment_pace_source == "splits_hr_z3"
    assert result.tempo_segment_split_count == 1
    assert result.tempo_segment_confidence == "medium"
    assert result.allows_full_gyor() is True


def test_three_split_run_single_z3_middle_mile_is_medium_not_high():
    splits = [
        _split(1, hr=125.0, pace=9.0),
        _split(2, hr=155.0, pace=7.0),
        _split(3, hr=120.0, pace=9.5),
    ]
    result, _ = compute_run_tempo_segment_pace(splits, ZONES)
    assert result.tempo_segment_pace_source == "splits_hr_z3"
    assert result.tempo_segment_split_count == 1
    assert result.tempo_segment_confidence == "medium"


def test_z3_two_splits_under_one_point_five_miles_is_medium():
    qualifying = select_qualifying_tempo_splits(
        [
            _split(1, hr=150.0, pace=7.0, distance=0.7),
            _split(2, hr=152.0, pace=6.8, distance=0.7),
        ],
        ZONES,
    )
    result = aggregate_qualifying_tempo_splits(qualifying)
    assert result.tempo_segment_pace_source == "splits_hr_z3"
    assert result.tempo_segment_confidence == "medium"


def test_distance_weighted_average():
    qualifying = select_qualifying_tempo_splits(
        [
            _split(1, hr=150.0, pace=7.0, distance=2.0),
            _split(2, hr=152.0, pace=6.0, distance=1.0),
        ],
        ZONES,
    )
    result = aggregate_qualifying_tempo_splits(qualifying)
    assert result.tempo_segment_pace_min_per_mi == 6.6667
    assert result.tempo_segment_avg_hr_bpm == 150.67


def test_segment_hr_matches_same_qualifying_splits_as_pace():
    splits = [
        _split(1, hr=125.0, pace=9.5),
        _split(2, hr=155.0, pace=7.5),
        _split(3, hr=157.0, pace=7.3),
        _split(4, hr=130.0, pace=9.0),
    ]
    result, qualifying = compute_run_tempo_segment_pace(splits, ZONES)
    assert len(qualifying) == 2
    assert result.tempo_segment_avg_hr_bpm == 156.0
    assert result.tempo_segment_pace_min_per_mi == 7.4


def test_no_qualifying_splits_returns_null_not_activity_avg_on_chart():
    splits = [_split(1, hr=120.0, pace=8.0)]
    result, qualifying = compute_run_tempo_segment_pace(
        splits,
        ZONES,
        activity_avg_pace_min_per_mi=8.5,
    )
    assert qualifying == []
    assert result.tempo_segment_pace_min_per_mi is None
    assert result.tempo_segment_pace_source == "activity_avg"
    assert result.activity_avg_pace_min_per_mi == 8.5
    assert result.allows_full_gyor() is False


def test_activity_avg_does_not_get_strong_gyor():
    result, _ = compute_run_tempo_segment_pace(
        [_split(1, hr=120.0, pace=8.0)],
        ZONES,
        activity_avg_pace_min_per_mi=7.0,
    )
    assert result.tempo_segment_pace_min_per_mi is None
    assert result.tempo_segment_confidence is None


def test_single_quality_split_is_low_confidence():
    splits = [_split(1, hr=161.0, pace=7.0)]
    result = aggregate_qualifying_tempo_splits(
        select_qualifying_tempo_splits(splits, ZONES)
    )
    assert result.tempo_segment_pace_source == "splits_hr_quality"
    assert result.tempo_segment_confidence == "low"
    assert result.allows_full_gyor() is False


def test_weekly_aggregation_across_multiple_tempo_runs():
    run_a = select_qualifying_tempo_splits(
        [
            _split(1, hr=150.0, pace=7.0, distance=2.0),
            _split(2, hr=151.0, pace=6.0, distance=1.0),
        ],
        ZONES,
    )
    run_b = select_qualifying_tempo_splits(
        [_split(1, hr=152.0, pace=8.0, distance=1.0)],
        ZONES,
    )
    weekly = combine_weekly_tempo_segment_pace([run_a, run_b])
    assert weekly.tempo_segment_split_count == 3
    assert weekly.tempo_segment_pace_source == "splits_hr_z3"
    assert weekly.tempo_segment_confidence == "high"
    assert weekly.tempo_segment_pace_min_per_mi == 7.0
