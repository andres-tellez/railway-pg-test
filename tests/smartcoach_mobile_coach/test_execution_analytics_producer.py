"""Unit tests for execution_analytics producer."""

from __future__ import annotations

from types import SimpleNamespace

from src.smartcoach_mobile_coach.execution_analytics.producer import (
    compute_activity_execution,
)
from src.smartcoach_mobile_coach.execution_analytics.tempo_segment import (
    TempoHrZoneBounds,
    TempoSplitRow,
)
from src.smartcoach_mobile_coach.execution_analytics.thresholds import (
    COMPUTE_STATUS_COMPLETE,
    COMPUTE_STATUS_SKIPPED_NOT_RUN,
)
from src.smartcoach_mobile_coach.runner_profile.models import (
    HrZoneBand,
    RunnerZoneProfileData,
)

ZONES = TempoHrZoneBounds(
    z2_high=145.0,
    z3_low=146.0,
    z3_high=160.0,
    z4_low=161.0,
)


def _profile() -> RunnerZoneProfileData:
    return RunnerZoneProfileData(
        user_id="test-user",
        calibrated=True,
        computed_at=None,
        hrmax_used=190,
        resting_hr_used=50,
        zone_method="karvonen",
        hr_z1=HrZoneBand(95, 114),
        hr_z2=HrZoneBand(115, 145),
        hr_z3=HrZoneBand(146, 160),
        hr_z4=HrZoneBand(161, 180),
        hr_z5=HrZoneBand(181, 190),
        pace_z2=None,
        pace_z3=None,
        pace_z4=None,
        pace_source=None,
        pace_computed_at=None,
    )


def _split(idx: int, hr: float, pace: float) -> TempoSplitRow:
    return TempoSplitRow(
        split_index=idx,
        avg_hr=hr,
        pace_min_per_mi=pace,
        distance_mi=1.0,
    )


def _split_model(idx: int, hr: float, pace: float) -> SimpleNamespace:
    return SimpleNamespace(
        split=idx,
        lap_index=idx,
        average_heartrate=hr,
        conv_avg_speed=pace,
        conv_distance=1.0,
        distance=None,
        moving_time=600,
    )


def test_non_run_skipped():
    activity = SimpleNamespace(type="Ride", moving_time=3600, average_heartrate=140.0)
    result = compute_activity_execution(activity, [], _profile())
    assert result.execution_compute_status == COMPUTE_STATUS_SKIPPED_NOT_RUN
    assert result.insights_system is None
    assert result.tempo_segment_pace_min_per_mi is None


def test_easy_run_has_null_tempo_segment_fields():
    activity = SimpleNamespace(
        type="Run",
        moving_time=3600,
        average_heartrate=130.0,
        conv_avg_speed=9.5,
    )
    splits = [_split_model(i, 130.0, 9.5) for i in range(1, 7)]
    result = compute_activity_execution(activity, splits, _profile())
    assert result.execution_compute_status == COMPUTE_STATUS_COMPLETE
    assert result.insights_system == "easy"
    assert result.tempo_segment_pace_min_per_mi is None
    assert result.tempo_segment_pace_source is None
    assert result.tempo_segment_confidence is None


def test_tempo_run_populates_segment_fields():
    activity = SimpleNamespace(
        type="Run",
        moving_time=3600,
        average_heartrate=155.0,
        conv_avg_speed=8.0,
    )
    splits = [
        _split_model(1, 125.0, 9.5),
        _split_model(2, 155.0, 7.5),
        _split_model(3, 157.0, 7.3),
        _split_model(4, 130.0, 9.0),
    ]
    result = compute_activity_execution(activity, splits, _profile())
    assert result.insights_system == "tempo"
    assert result.tempo_segment_pace_source == "splits_hr_z3"
    assert result.tempo_segment_pace_min_per_mi is not None
    assert result.tempo_segment_avg_hr_bpm is not None
    assert result.tempo_qualifying_distance_mi is not None


def test_z4_splits_classify_as_threshold_before_tempo():
    activity = SimpleNamespace(
        type="Run",
        moving_time=3600,
        average_heartrate=150.0,
        conv_avg_speed=8.0,
    )
    splits = [
        _split_model(1, 130.0, 9.0),
        _split_model(2, 165.0, 8.0),
        _split_model(3, 165.0, 8.0),
        _split_model(4, 165.0, 8.0),
        _split_model(5, 130.0, 9.0),
    ]
    result = compute_activity_execution(activity, splits, _profile())
    assert result.insights_system == "threshold"
    assert result.threshold_segment_pace_source == "splits_hr_z4"
    assert result.tempo_segment_pace_min_per_mi is None


def test_activity_avg_diagnostic_does_not_populate_chart_fields():
    activity = SimpleNamespace(
        type="Run",
        moving_time=3600,
        average_heartrate=155.0,
        conv_avg_speed=8.0,
    )
    splits = [_split_model(1, 162.0, 9.0)]
    result = compute_activity_execution(activity, splits, _profile())
    assert result.insights_system == "tempo"
    assert result.tempo_segment_pace_source == "activity_avg"
    assert result.tempo_segment_pace_min_per_mi is None
    assert result.tempo_segment_confidence is None


def test_threshold_activity_avg_diagnostic_clears_chart_fields():
    activity = SimpleNamespace(
        type="Run",
        moving_time=3600,
        average_heartrate=168.0,
        conv_avg_speed=8.0,
    )
    splits = [
        _split_model(1, 145.5, 9.0),
        _split_model(2, 145.5, 9.0),
    ]
    result = compute_activity_execution(activity, splits, _profile())
    assert result.insights_system == "threshold"
    assert result.threshold_segment_pace_source == "activity_avg"
    assert result.threshold_segment_pace_min_per_mi is None
    assert result.threshold_segment_confidence is None
