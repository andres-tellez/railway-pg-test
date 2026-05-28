"""Weekly history chart bands use stored rollup columns (SSOT at write time)."""

from __future__ import annotations

from datetime import date
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
def test_weekly_history_easy_bands_use_stored_rollup_columns(
    _mock_athlete,
    _mock_plan,
    _mock_profile,
    _mock_phase,
    _mock_tempo_batch,
):
    """Stored bands win over on-read reclassification when targets would differ."""
    cal_week_start, _ = calendar_week_containing(date.today())
    session = MagicMock()
    session.execute.return_value.fetchall.return_value = [
        SimpleNamespace(
            week_start=cal_week_start,
            hr_drift_pct=2.5,
            hr_drift_band="green",
            z2_pace_min_per_mi=9.5,
            z2_pace_band="red",
            efficiency=1.2,
            efficiency_band="orange",
            easy_avg_hr=142.0,
            easy_avg_hr_band="yellow",
        )
    ]

    out = get_weekly_insight_history(session, USER_ID, weeks=1)

    easy_points = out["systems"]["easy"]["weekly_data"]
    assert len(easy_points) == 1
    point = easy_points[0]
    assert point["band"] == "green"
    assert point["easy_pace_progress_band"] == "red"
    assert point["easy_hr_progress_band"] == "yellow"
    assert point["efficiency_band"] == "orange"
    assert "z2_pace_band" not in point
    assert "easy_avg_hr_band" not in point
