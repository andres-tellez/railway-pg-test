"""Weekly history exposes systems.long.weekly_data (Easy-shaped, on-read)."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.smartcoach_mobile_coach.long_run_insights_selection import LongRunCandidate
from src.smartcoach_mobile_coach.runner_profile.models import (
    HrZoneBand,
    PaceZoneBand,
    RunnerZoneProfileData,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.training_phase_resolver import (
    TrainingPhaseResolution,
)
from src.smartcoach_mobile_coach.weekly_insights_service import (
    LONG_INSIGHTS_SYSTEM_KEY,
    calendar_week_containing,
    get_weekly_insight_history,
)

USER_ID = "00000000-0000-0000-0000-000000000001"


def _calibrated_profile() -> RunnerZoneProfileData:
    from datetime import datetime, timezone

    return RunnerZoneProfileData(
        user_id=USER_ID,
        calibrated=True,
        computed_at=datetime.now(timezone.utc),
        hrmax_used=185,
        resting_hr_used=50,
        zone_method="karvonen",
        hr_z1=HrZoneBand(100, 115),
        hr_z2=HrZoneBand(120, 145),
        hr_z3=HrZoneBand(146, 160),
        hr_z4=HrZoneBand(161, 175),
        hr_z5=HrZoneBand(176, 185),
        pace_z2=PaceZoneBand(low_sec=600, high_sec=630, display="10:00-10:30/mi"),
        pace_z3=PaceZoneBand(low_sec=570, high_sec=590, display="9:30-9:50/mi"),
        pace_z4=PaceZoneBand(low_sec=530, high_sec=540, display="8:50-9:00/mi"),
        pace_source="performance",
        pace_computed_at=datetime.now(timezone.utc),
    )


def _phase_resolution() -> TrainingPhaseResolution:
    return TrainingPhaseResolution(
        phase="Base",
        source="test",
        week_start=date(2026, 4, 7),
    )


def _history_patches():
    return (
        patch(
            "src.smartcoach_mobile_coach.weekly_insights_service._fetch_tempo_week_rollups_batch",
            return_value={},
        ),
        patch(
            "src.smartcoach_mobile_coach.weekly_insights_service._fetch_threshold_week_rollups_batch",
            return_value={},
        ),
        patch(
            "src.smartcoach_mobile_coach.runner_profile.service.resolve_current_training_phase",
            return_value=_phase_resolution(),
        ),
        patch(
            "src.smartcoach_mobile_coach.insights_chart_authority.get_runner_profile",
            return_value=_calibrated_profile(),
        ),
        patch(
            "src.smartcoach_mobile_coach.insights_chart_authority.get_active_or_most_recent_plan",
            return_value=None,
        ),
        patch(
            "src.smartcoach_mobile_coach.weekly_insights_service.get_primary_athlete_id",
            return_value=12345,
        ),
    )


@patch(
    "src.smartcoach_mobile_coach.weekly_insights_service._fetch_long_run_candidates_by_week",
    return_value={},
)
@patch(
    "src.smartcoach_mobile_coach.weekly_insights_service._fetch_threshold_week_rollups_batch",
    return_value={},
)
@patch(
    "src.smartcoach_mobile_coach.weekly_insights_service._fetch_tempo_week_rollups_batch",
    return_value={},
)
@patch(
    "src.smartcoach_mobile_coach.runner_profile.service.resolve_current_training_phase",
    return_value=_phase_resolution(),
)
@patch(
    "src.smartcoach_mobile_coach.insights_chart_authority.get_runner_profile",
    return_value=_calibrated_profile(),
)
@patch(
    "src.smartcoach_mobile_coach.insights_chart_authority.get_active_or_most_recent_plan",
    return_value=None,
)
@patch(
    "src.smartcoach_mobile_coach.weekly_insights_service.get_primary_athlete_id",
    return_value=12345,
)
def test_weekly_history_includes_long_system_with_empty_week_point(
    _mock_athlete,
    _mock_plan,
    _mock_profile,
    _mock_phase,
    _mock_tempo_batch,
    _mock_threshold_batch,
    _mock_long_candidates,
):
    cal_week_start, _ = calendar_week_containing(date.today())
    session = MagicMock()
    session.execute.return_value.fetchone.return_value = None
    _mock_long_candidates.return_value = {
        cal_week_start: [
            LongRunCandidate(
                activity_id=1,
                moving_time=40 * 60,
                insights_system="easy",
                matched_run_type_key=None,
                date_plan_run_type_key=None,
                planned_type=None,
                executed_type=None,
                hr_drift_pct=2.5,
                avg_pace_min_per_mi=9.5,
                avg_hr_bpm=142.0,
            )
        ]
    }

    out = get_weekly_insight_history(session, USER_ID, weeks=1)

    assert LONG_INSIGHTS_SYSTEM_KEY in out["systems"]
    long_points = out["systems"][LONG_INSIGHTS_SYSTEM_KEY]["weekly_data"]
    assert len(long_points) == 1
    assert long_points[0]["value"] is None
    assert long_points[0]["z2_pace_min_per_mi"] is None


@patch(
    "src.smartcoach_mobile_coach.weekly_insights_service._fetch_long_run_candidates_by_week",
)
@patch(
    "src.smartcoach_mobile_coach.weekly_insights_service._fetch_threshold_week_rollups_batch",
    return_value={},
)
@patch(
    "src.smartcoach_mobile_coach.weekly_insights_service._fetch_tempo_week_rollups_batch",
    return_value={},
)
@patch(
    "src.smartcoach_mobile_coach.runner_profile.service.resolve_current_training_phase",
    return_value=_phase_resolution(),
)
@patch(
    "src.smartcoach_mobile_coach.insights_chart_authority.get_runner_profile",
    return_value=_calibrated_profile(),
)
@patch(
    "src.smartcoach_mobile_coach.insights_chart_authority.get_active_or_most_recent_plan",
    return_value=None,
)
@patch(
    "src.smartcoach_mobile_coach.weekly_insights_service.get_primary_athlete_id",
    return_value=12345,
)
def test_weekly_history_long_point_uses_easy_field_shape(
    _mock_athlete,
    _mock_plan,
    _mock_profile,
    _mock_phase,
    _mock_tempo_batch,
    _mock_threshold_batch,
    _mock_long_candidates,
):
    cal_week_start, _ = calendar_week_containing(date.today())
    session = MagicMock()
    session.execute.return_value.fetchone.return_value = None
    _mock_long_candidates.return_value = {
        cal_week_start: [
            LongRunCandidate(
                activity_id=99,
                moving_time=80 * 60,
                insights_system="easy",
                matched_run_type_key="long_run",
                date_plan_run_type_key=None,
                planned_type=None,
                executed_type=None,
                hr_drift_pct=3.1,
                avg_pace_min_per_mi=9.2,
                avg_hr_bpm=138.0,
            )
        ]
    }

    out = get_weekly_insight_history(session, USER_ID, weeks=1)
    point = out["systems"][LONG_INSIGHTS_SYSTEM_KEY]["weekly_data"][0]

    assert point["value"] == 3.1
    assert point["z2_pace_min_per_mi"] == 9.2
    assert point["easy_avg_hr"] == 138.0
    assert point["efficiency"] is not None
    assert "easy_pace_progress_band" in point
    assert "easy_hr_progress_band" in point
