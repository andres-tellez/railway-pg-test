"""Producer persistence for threshold segment facts."""

from __future__ import annotations

from types import SimpleNamespace

from src.smartcoach_mobile_coach.execution_analytics.producer import (
    compute_activity_execution,
)
from src.smartcoach_mobile_coach.execution_analytics.thresholds import (
    COMPUTE_STATUS_COMPLETE,
)
from src.smartcoach_mobile_coach.runner_profile.models import (
    HrZoneBand,
    RunnerZoneProfileData,
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
        hr_z4=HrZoneBand(161, 175),
        hr_z5=HrZoneBand(176, 190),
        pace_z2=None,
        pace_z3=None,
        pace_z4=None,
        pace_source=None,
        pace_computed_at=None,
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


def test_threshold_run_populates_segment_fields():
    activity = SimpleNamespace(
        type="Run",
        moving_time=3600,
        average_heartrate=168.0,
        conv_avg_speed=7.5,
    )
    splits = [
        _split_model(1, 125.0, 9.5),
        _split_model(2, 165.0, 7.0),
        _split_model(3, 167.0, 7.1),
        _split_model(4, 130.0, 9.0),
    ]
    result = compute_activity_execution(activity, splits, _profile())
    assert result.execution_compute_status == COMPUTE_STATUS_COMPLETE
    assert result.insights_system == "threshold"
    assert result.threshold_segment_pace_source == "splits_hr_z4"
    assert result.threshold_segment_pace_min_per_mi is not None
    assert result.threshold_qualifying_distance_mi is not None
    assert result.tempo_segment_pace_min_per_mi is None


def test_tempo_run_has_null_threshold_fields():
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
    assert result.threshold_segment_pace_min_per_mi is None
    assert result.threshold_segment_pace_source is None
