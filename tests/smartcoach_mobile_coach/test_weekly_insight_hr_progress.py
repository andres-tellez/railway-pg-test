"""Integration: weekly history hr zones share the hr_progress pipeline."""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.smartcoach_mobile_coach.runner_profile.models import (
    HrZoneBand,
    RunnerZoneProfileData,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.hr_progress_easy import (
    hr_progress_zones_chart_api_payload,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.training_pace_recommendations import (
    TrainingPaceRecommendations,
    build_training_pace_recommendations,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.training_phase_resolver import (
    TrainingPhaseResolution,
)
from src.smartcoach_mobile_coach.weekly_insights_service import (
    _resolve_easy_hr_progress,
    calendar_week_containing,
    get_weekly_insight_history,
)

USER_ID = "00000000-0000-0000-0000-000000000001"


def _calibrated_profile() -> RunnerZoneProfileData:
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
        pace_z2=None,
        pace_z3=None,
        pace_z4=None,
        pace_source=None,
        pace_computed_at=None,
    )


def _expected_hr_zones_from_recs(
    recs: TrainingPaceRecommendations | None,
) -> list[dict[str, object]]:
    assert recs is not None and recs.hr_progress is not None
    zones: list[dict[str, object]] = []
    for zone in hr_progress_zones_chart_api_payload(recs.hr_progress.hr_zones_chart):
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
    return_value=_calibrated_profile(),
)
@patch(
    "src.smartcoach_mobile_coach.insights_chart_authority.get_active_or_most_recent_plan",
    return_value=None,
)
def test_resolve_easy_hr_progress_matches_training_pace_recommendations(
    _mock_plan,
    _mock_profile,
    _mock_phase,
):
    recs = build_training_pace_recommendations(
        profile=_calibrated_profile(),
        target_time=None,
        phase="Base",
    )
    expected_zones = _expected_hr_zones_from_recs(recs)

    session = MagicMock()
    target_hr_z2, hr_zones = _resolve_easy_hr_progress(session, USER_ID)

    assert recs is not None and recs.hr_progress is not None
    assert target_hr_z2 is not None
    assert target_hr_z2.low == recs.hr_progress.target_hr_z2.low
    assert hr_zones == expected_zones


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
def test_weekly_history_hr_zones_match_hr_progress(
    _mock_athlete,
    _mock_plan,
    _mock_profile,
    _mock_phase,
    _mock_week_kpis,
):
    cal_week_start, _ = calendar_week_containing(date.today())
    session = MagicMock()
    session.execute.return_value.fetchall.return_value = [
        _history_row(week_start=cal_week_start)
    ]

    recs = build_training_pace_recommendations(
        profile=_calibrated_profile(),
        target_time=None,
        phase="Base",
    )
    expected_zones = _expected_hr_zones_from_recs(recs)

    out = get_weekly_insight_history(session, USER_ID, weeks=1)

    assert out["has_history"] is True
    assert out["hr_zones"] == expected_zones
    assert out["systems"]["easy"]["hr_zones"] == expected_zones
    assert out["hr_drift_target_display"] == "under 2.5% ideal, under 5% acceptable"
    assert out["efficiency_goal_display"] == "higher is better at the same effort"
    assert (
        out["systems"]["easy"]["hr_drift_target_display"]
        == out["hr_drift_target_display"]
    )
    assert (
        out["systems"]["easy"]["efficiency_goal_display"]
        == out["efficiency_goal_display"]
    )

    easy_points = out["weekly_data"]
    assert len(easy_points) == 1
    assert easy_points[0]["easy_hr_progress_band"] == "green"
    assert "easy_avg_hr_band" not in easy_points[0]
