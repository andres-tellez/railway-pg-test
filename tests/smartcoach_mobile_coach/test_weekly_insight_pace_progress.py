"""Integration: weekly history pace zones share the pace_progress pipeline."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.smartcoach_mobile_coach.runner_profile.models import RunnerZoneProfileData
from src.smartcoach_mobile_coach.runner_profile.recommendations.pace_progress_easy import (
    pace_progress_zones_chart_api_payload,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.training_pace_recommendations import (
    TrainingPaceRecommendations,
    build_training_pace_recommendations,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.training_phase_resolver import (
    TrainingPhaseResolution,
)
from src.smartcoach_mobile_coach.weekly_insights_service import (
    _resolve_easy_pace_progress,
    calendar_week_containing,
    get_weekly_insight_history,
)

USER_ID = "00000000-0000-0000-0000-000000000001"
TARGET_TIME = "3:40:00"


def _uncalibrated_profile() -> RunnerZoneProfileData:
    return RunnerZoneProfileData(
        user_id=USER_ID,
        calibrated=False,
        computed_at=None,
        hrmax_used=None,
        resting_hr_used=None,
        zone_method=None,
        hr_z1=None,
        hr_z2=None,
        hr_z3=None,
        hr_z4=None,
        hr_z5=None,
        pace_z2=None,
        pace_z3=None,
        pace_z4=None,
        pace_source=None,
        pace_computed_at=None,
    )


def _expected_pace_zones_from_recs(
    recs: TrainingPaceRecommendations | None,
) -> list[dict[str, object]]:
    """Mirror weekly_insights_service._pace_zones_chart_payload serialization."""
    assert recs is not None and recs.pace_progress is not None
    zones: list[dict[str, object]] = []
    for zone in pace_progress_zones_chart_api_payload(
        recs.pace_progress.pace_zones_chart
    ):
        lo = float(zone["min"])
        hi = float(zone["max"])
        zones.append({"color": str(zone["color"]), "min": lo, "max": hi})
    return zones


def _history_row(*, week_start: date) -> SimpleNamespace:
    return SimpleNamespace(
        week_start=week_start,
        hr_drift_pct=2.5,
        hr_drift_band="green",
        z2_pace_min_per_mi=9.5,
        z2_pace_band="green",
        efficiency=1.2,
        efficiency_band="green",
        easy_avg_hr=142.0,
        easy_avg_hr_band="green",
    )


def _plan_with_target() -> SimpleNamespace:
    return SimpleNamespace(target_time=TARGET_TIME)


def _phase_resolution() -> TrainingPhaseResolution:
    return TrainingPhaseResolution(
        phase="Base",
        source="test",
        week_start=date(2026, 4, 7),
    )


@patch(
    "src.smartcoach_mobile_coach.runner_profile.service.resolve_current_training_phase",
    return_value=_phase_resolution(),
)
@patch(
    "src.smartcoach_mobile_coach.insights_chart_authority.get_runner_profile",
    return_value=_uncalibrated_profile(),
)
@patch(
    "src.smartcoach_mobile_coach.insights_chart_authority.get_active_or_most_recent_plan",
    return_value=_plan_with_target(),
)
def test_resolve_easy_pace_progress_matches_training_pace_recommendations(
    _mock_plan,
    _mock_profile,
    _mock_phase,
):
    """_resolve_easy_pace_progress uses the same pace_progress chart as recommendations."""
    recs = build_training_pace_recommendations(
        profile=_uncalibrated_profile(),
        target_time=TARGET_TIME,
        phase="Base",
    )
    expected_zones = _expected_pace_zones_from_recs(recs)

    session = MagicMock()
    target_easy_pace, pace_zones = _resolve_easy_pace_progress(session, USER_ID)

    assert recs is not None and recs.pace_progress is not None
    assert target_easy_pace is not None
    assert target_easy_pace.low_sec == recs.pace_progress.target_easy_pace.low_sec
    assert pace_zones == expected_zones


@patch(
    "src.smartcoach_mobile_coach.weekly_insights_service._fetch_week_kpis",
    return_value={"threshold_run_count": 0},
)
@patch(
    "src.smartcoach_mobile_coach.runner_profile.service.resolve_current_training_phase",
    return_value=_phase_resolution(),
)
@patch(
    "src.smartcoach_mobile_coach.insights_chart_authority.get_runner_profile",
    return_value=_uncalibrated_profile(),
)
@patch(
    "src.smartcoach_mobile_coach.insights_chart_authority.get_active_or_most_recent_plan",
    return_value=_plan_with_target(),
)
@patch(
    "src.smartcoach_mobile_coach.weekly_insights_service.get_primary_athlete_id",
    return_value=12345,
)
def test_weekly_history_pace_zones_match_pace_progress(
    _mock_athlete,
    _mock_plan,
    _mock_profile,
    _mock_phase,
    _mock_week_kpis,
):
    """get_weekly_insight_history pace_zones must match build_training_pace_recommendations."""
    cal_week_start, _ = calendar_week_containing(date.today())
    session = MagicMock()
    session.execute.return_value.fetchall.return_value = [
        _history_row(week_start=cal_week_start)
    ]

    recs = build_training_pace_recommendations(
        profile=_uncalibrated_profile(),
        target_time=TARGET_TIME,
        phase="Base",
    )
    expected_zones = _expected_pace_zones_from_recs(recs)

    out = get_weekly_insight_history(session, USER_ID, weeks=1)

    assert out["has_history"] is True
    easy = out["systems"]["easy"]
    assert easy["pace_zones"] == expected_zones
    assert recs is not None and recs.pace_progress is not None
    assert recs.easy_gyor is None
    assert "pace_zones" not in out

    easy_points = easy["weekly_data"]
    assert len(easy_points) == 1
    assert easy_points[0]["easy_pace_progress_band"] is not None
    assert "z2_pace_band" not in easy_points[0]
