"""Integration-style tests for live tempo segment pace computation."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.smartcoach_mobile_coach.runner_profile.models import (
    HrZoneBand,
    RunnerZoneProfileData,
)
from src.smartcoach_mobile_coach.weekly_insights_service import (
    _WEEK_TEMPO_RUN_SPLITS_SQL,
    _compute_week_tempo_segment_pace,
)


USER_ID = "e3362637-9045-4aac-83ed-92bc1f2643b9"


def _profile_with_z3() -> RunnerZoneProfileData:
    return RunnerZoneProfileData(
        user_id=USER_ID,
        calibrated=True,
        computed_at=None,
        hrmax_used=174,
        resting_hr_used=50,
        zone_method="karvonen",
        hr_z1=HrZoneBand(110, 123),
        hr_z2=HrZoneBand(124, 143),
        hr_z3=HrZoneBand(143, 155),
        hr_z4=HrZoneBand(155, 168),
        hr_z5=HrZoneBand(169, 174),
        pace_z2=None,
        pace_z3=None,
        pace_z4=None,
        pace_source=None,
        pace_computed_at=None,
    )


def _z3_run_split_rows() -> list[SimpleNamespace]:
    """Mirrors activity 18568950855 mile splits (Z3 laps 2–4 qualify after trim)."""
    specs = [
        (1, 128.46, 9.12),
        (2, 145.27, 8.57),
        (3, 147.18, 8.88),
        (4, 151.18, 8.94),
        (5, 155.75, 9.12),
        (6, 142.19, 11.56),
    ]
    rows = []
    for lap, hr, pace in specs:
        rows.append(
            SimpleNamespace(
                activity_id=18568950855,
                activity_avg_pace=9.3,
                split=lap,
                lap_index=lap,
                average_heartrate=hr,
                conv_avg_speed=pace,
                conv_distance=1.0,
                distance=1606.0,
                moving_time=520,
                average_speed=2.95,
            )
        )
    return rows


def test_tempo_splits_sql_does_not_reference_user_hr_zones_table():
    assert "user_hr_zones" not in _WEEK_TEMPO_RUN_SPLITS_SQL


@patch(
    "src.smartcoach_mobile_coach.weekly_insights_service.get_runner_profile",
    return_value=_profile_with_z3(),
)
def test_compute_week_tempo_segment_pace_from_z3_mile_splits(_mock_profile):
    session = MagicMock()
    session.execute.return_value.fetchall.return_value = _z3_run_split_rows()

    result = _compute_week_tempo_segment_pace(
        session,
        USER_ID,
        date(2026, 5, 18),
        date(2026, 5, 24),
        athlete_id=347085,
    )

    assert result.tempo_segment_pace_min_per_mi == 8.7967
    assert result.tempo_segment_pace_source == "splits_hr_z3"
    assert result.tempo_segment_split_count == 3
    assert result.tempo_segment_confidence == "high"


@patch(
    "src.smartcoach_mobile_coach.weekly_insights_service.get_runner_profile",
    return_value=_profile_with_z3(),
)
def test_compute_week_tempo_segment_pace_empty_when_sql_returns_no_rows(_mock_profile):
    session = MagicMock()
    session.execute.return_value.fetchall.return_value = []

    result = _compute_week_tempo_segment_pace(
        session,
        USER_ID,
        date(2026, 5, 18),
        date(2026, 5, 24),
        athlete_id=347085,
    )

    assert result.tempo_segment_pace_min_per_mi is None
    assert result.tempo_segment_split_count == 0
