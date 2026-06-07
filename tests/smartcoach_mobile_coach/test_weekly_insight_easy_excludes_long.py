"""Easy weekly history excludes the canonical Long run selected per week."""

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


def _candidate(
    *,
    activity_id: int,
    moving_time: int,
    hr_drift_pct: float,
    avg_pace_min_per_mi: float,
    avg_hr_bpm: float,
    matched_run_type_key: str | None = None,
) -> LongRunCandidate:
    return LongRunCandidate(
        activity_id=activity_id,
        moving_time=moving_time,
        insights_system="easy",
        matched_run_type_key=matched_run_type_key,
        date_plan_run_type_key=None,
        planned_type=None,
        executed_type=None,
        hr_drift_pct=hr_drift_pct,
        avg_pace_min_per_mi=avg_pace_min_per_mi,
        avg_hr_bpm=avg_hr_bpm,
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
def test_easy_includes_short_easy_runs_when_no_long_selected(
    _mock_athlete,
    _mock_plan,
    _mock_profile,
    _mock_phase,
    _mock_tempo_batch,
    _mock_threshold_batch,
    _mock_long_candidates,
):
    cal_week_start, _ = calendar_week_containing(date.today())
    _mock_long_candidates.return_value = {
        cal_week_start: [
            _candidate(
                activity_id=1,
                moving_time=24 * 60,
                hr_drift_pct=2.0,
                avg_pace_min_per_mi=10.0,
                avg_hr_bpm=140.0,
            ),
            _candidate(
                activity_id=2,
                moving_time=40 * 60,
                hr_drift_pct=4.0,
                avg_pace_min_per_mi=9.0,
                avg_hr_bpm=150.0,
            ),
        ]
    }
    session = MagicMock()
    session.execute.return_value.fetchone.return_value = None

    out = get_weekly_insight_history(session, USER_ID, weeks=1)
    easy_point = out["systems"]["easy"]["weekly_data"][0]
    long_point = out["systems"][LONG_INSIGHTS_SYSTEM_KEY]["weekly_data"][0]

    assert easy_point["value"] == 3.0
    assert easy_point["z2_pace_min_per_mi"] == 9.5
    assert long_point["value"] is None


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
def test_easy_excludes_selected_long_from_weekly_average(
    _mock_athlete,
    _mock_plan,
    _mock_profile,
    _mock_phase,
    _mock_tempo_batch,
    _mock_threshold_batch,
    _mock_long_candidates,
):
    cal_week_start, _ = calendar_week_containing(date.today())
    _mock_long_candidates.return_value = {
        cal_week_start: [
            _candidate(
                activity_id=1,
                moving_time=24 * 60,
                hr_drift_pct=2.0,
                avg_pace_min_per_mi=10.0,
                avg_hr_bpm=140.0,
            ),
            _candidate(
                activity_id=2,
                moving_time=30 * 60,
                hr_drift_pct=4.0,
                avg_pace_min_per_mi=9.0,
                avg_hr_bpm=150.0,
            ),
            _candidate(
                activity_id=3,
                moving_time=80 * 60,
                hr_drift_pct=6.0,
                avg_pace_min_per_mi=8.5,
                avg_hr_bpm=155.0,
                matched_run_type_key="long_run",
            ),
        ]
    }
    session = MagicMock()
    session.execute.return_value.fetchone.return_value = None

    out = get_weekly_insight_history(session, USER_ID, weeks=1)
    easy_point = out["systems"]["easy"]["weekly_data"][0]
    long_point = out["systems"][LONG_INSIGHTS_SYSTEM_KEY]["weekly_data"][0]

    assert easy_point["value"] == 3.0
    assert easy_point["z2_pace_min_per_mi"] == 9.5
    assert long_point["value"] == 6.0
    assert long_point["z2_pace_min_per_mi"] == 8.5


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
def test_long_only_week_has_history_without_easy_plottable_point(
    _mock_athlete,
    _mock_plan,
    _mock_profile,
    _mock_phase,
    _mock_tempo_batch,
    _mock_threshold_batch,
    _mock_long_candidates,
):
    cal_week_start, _ = calendar_week_containing(date.today())
    _mock_long_candidates.return_value = {
        cal_week_start: [
            _candidate(
                activity_id=9,
                moving_time=80 * 60,
                hr_drift_pct=3.1,
                avg_pace_min_per_mi=9.2,
                avg_hr_bpm=138.0,
                matched_run_type_key="long_run",
            )
        ]
    }
    session = MagicMock()
    session.execute.return_value.fetchone.return_value = None

    out = get_weekly_insight_history(session, USER_ID, weeks=1)
    easy_point = out["systems"]["easy"]["weekly_data"][0]
    long_point = out["systems"][LONG_INSIGHTS_SYSTEM_KEY]["weekly_data"][0]

    assert out["has_history"] is True
    assert easy_point["value"] is None
    assert long_point["value"] == 3.1


@patch(
    "src.smartcoach_mobile_coach.weekly_insights_service.select_long_run_for_week",
)
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
def test_easy_exclusion_uses_select_long_run_for_week_ssot(
    _mock_athlete,
    _mock_plan,
    _mock_profile,
    _mock_phase,
    _mock_tempo_batch,
    _mock_threshold_batch,
    _mock_long_candidates,
    _mock_select_long,
):
    cal_week_start, _ = calendar_week_containing(date.today())
    short = _candidate(
        activity_id=1,
        moving_time=30 * 60,
        hr_drift_pct=2.0,
        avg_pace_min_per_mi=10.0,
        avg_hr_bpm=140.0,
    )
    long_run = _candidate(
        activity_id=2,
        moving_time=80 * 60,
        hr_drift_pct=8.0,
        avg_pace_min_per_mi=8.0,
        avg_hr_bpm=150.0,
    )
    week = [short, long_run]
    _mock_long_candidates.return_value = {cal_week_start: week}
    _mock_select_long.return_value = long_run

    session = MagicMock()
    session.execute.return_value.fetchone.return_value = None

    out = get_weekly_insight_history(session, USER_ID, weeks=1)
    easy_point = out["systems"]["easy"]["weekly_data"][0]

    _mock_select_long.assert_called()
    assert easy_point["value"] == 2.0
    assert easy_point["z2_pace_min_per_mi"] == 10.0
