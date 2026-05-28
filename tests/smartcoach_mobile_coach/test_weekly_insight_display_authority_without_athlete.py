"""Display authority on weekly-history when chart history is unavailable."""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.smartcoach_mobile_coach.runner_profile.models import (
    HrZoneBand,
    PaceZoneBand,
    RunnerZoneProfileData,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.training_phase_resolver import (
    TrainingPhaseResolution,
)
from src.smartcoach_mobile_coach.weekly_insights_service import (
    get_weekly_insight_history,
)

USER_ID = "00000000-0000-0000-0000-000000000001"
TARGET_TIME = "3:40:00"


def _calibrated_profile_with_paces() -> RunnerZoneProfileData:
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


def _plan_with_target() -> SimpleNamespace:
    return SimpleNamespace(target_time=TARGET_TIME, race_distance="Marathon")


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
    return_value=_calibrated_profile_with_paces(),
)
@patch(
    "src.smartcoach_mobile_coach.insights_chart_authority.get_active_or_most_recent_plan",
    return_value=_plan_with_target(),
)
@patch(
    "src.smartcoach_mobile_coach.weekly_insights_service.get_primary_athlete_id",
    return_value=None,
)
def test_weekly_history_includes_display_authority_without_athlete(
    _mock_athlete,
    _mock_plan,
    _mock_profile,
    _mock_phase,
):
    session = MagicMock()
    out = get_weekly_insight_history(session, USER_ID, weeks=1)

    assert out["has_history"] is False
    assert out["systems"]["easy"]["pace_target_display"] is not None
    assert out["systems"]["easy"]["hr_target_display"] is not None
    assert out["systems"]["easy"]["hr_drift_target_display"] is not None
    assert out["systems"]["easy"]["efficiency_goal_display"] is not None
    assert out["systems"]["tempo"]["pace_target_display"] is not None
    assert out["systems"]["tempo"]["insights_tempo_banner"] is not None
