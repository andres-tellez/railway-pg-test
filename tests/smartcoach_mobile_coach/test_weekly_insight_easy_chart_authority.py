"""Easy display authority on /weekly-history matches /zones recommendation builders."""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.smartcoach_mobile_coach.runner_profile.api_schema import (
    INSIGHTS_EASY_BANNER_SUBTITLE,
    build_insights_easy_chart_authority_payload,
    build_insights_easy_global_kpi_chart_authority_payload,
    runner_zone_profile_payload,
)
from src.utils.hr_zone_constants import (
    aerobic_efficiency_band_zones_chart,
    hr_drift_band_zones_chart,
)
from src.smartcoach_mobile_coach.runner_profile.models import (
    HrZoneBand,
    PaceZoneBand,
    RunnerZoneProfileData,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.training_pace_recommendations import (
    build_training_pace_recommendations,
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


def _expected_easy_authority_from_recs(profile: RunnerZoneProfileData):
    recs = build_training_pace_recommendations(
        profile=profile,
        target_time=TARGET_TIME,
        race_distance="Marathon",
        phase="Base",
    )
    assert recs is not None
    authority = build_insights_easy_chart_authority_payload(recs)
    zones_payload = runner_zone_profile_payload(
        profile,
        training_pace_recommendations=recs,
        target_time=TARGET_TIME,
        race_distance="Marathon",
    )
    tp = zones_payload["training_pace_recommendations"]
    assert tp is not None
    assert (
        authority["pace_target_display"]
        == tp["pace_progress"]["target_easy_pace"]["display"]
    )
    assert authority["hr_target_display"] == tp["hr_progress"]["target_display"]
    z2 = tp["hr_progress"]["target_hr_z2"]
    assert authority["hr_progress_z2_range_display"] == f"{z2['low']}–{z2['high']} bpm"
    assert authority["insights_easy_banner"] == zones_payload["insights_easy_banner"]
    assert (
        authority["insights_easy_banner"]["subtitle"] == INSIGHTS_EASY_BANNER_SUBTITLE
    )
    return authority


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
def test_easy_chart_authority_payload_matches_zones(
    _mock_plan, _mock_profile, _mock_phase
):
    profile = _calibrated_profile_with_paces()
    _expected_easy_authority_from_recs(profile)


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
    return_value=_calibrated_profile_with_paces(),
)
@patch(
    "src.smartcoach_mobile_coach.insights_chart_authority.get_active_or_most_recent_plan",
    return_value=_plan_with_target(),
)
@patch(
    "src.smartcoach_mobile_coach.weekly_insights_service.get_primary_athlete_id",
    return_value=12345,
)
def test_weekly_history_easy_authority_matches_zones_with_history(
    _mock_athlete,
    _mock_plan,
    _mock_profile,
    _mock_phase,
    _mock_tempo_batch,
):
    profile = _calibrated_profile_with_paces()
    expected = _expected_easy_authority_from_recs(profile)
    global_kpi = build_insights_easy_global_kpi_chart_authority_payload()

    session = MagicMock()
    session.execute.return_value.fetchall.return_value = []

    out = get_weekly_insight_history(session, USER_ID, weeks=1)

    assert out["has_history"] is False
    easy = out["systems"]["easy"]
    assert easy["pace_target_display"] == expected["pace_target_display"]
    assert easy["hr_target_display"] == expected["hr_target_display"]
    assert (
        easy["hr_progress_z2_range_display"] == expected["hr_progress_z2_range_display"]
    )
    assert easy["insights_easy_banner"] == expected["insights_easy_banner"]
    assert easy["hr_drift_target_display"] == global_kpi["hr_drift_target_display"]
    assert easy["efficiency_goal_display"] == global_kpi["efficiency_goal_display"]
    assert easy["zones"] == global_kpi["zones"]
    assert easy["efficiency_zones"] == global_kpi["efficiency_zones"]
    assert len(easy["weekly_data"]) == 1
    assert easy["weekly_data"][0]["value"] is None


@patch(
    "src.smartcoach_mobile_coach.weekly_insights_service._fetch_long_run_candidates_by_week",
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
    return_value=_calibrated_profile_with_paces(),
)
@patch(
    "src.smartcoach_mobile_coach.insights_chart_authority.get_active_or_most_recent_plan",
    return_value=_plan_with_target(),
)
@patch(
    "src.smartcoach_mobile_coach.weekly_insights_service.get_primary_athlete_id",
    return_value=12345,
)
def test_weekly_history_includes_easy_authority_when_has_history(
    _mock_athlete,
    _mock_plan,
    _mock_profile,
    _mock_phase,
    _mock_tempo_batch,
    _mock_long_candidates,
):
    from src.smartcoach_mobile_coach.long_run_insights_selection import LongRunCandidate
    from src.smartcoach_mobile_coach.weekly_insights_service import (
        calendar_week_containing,
    )

    profile = _calibrated_profile_with_paces()
    expected = _expected_easy_authority_from_recs(profile)
    global_kpi = build_insights_easy_global_kpi_chart_authority_payload()
    cal_week_start, _ = calendar_week_containing(date.today())

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
    session = MagicMock()
    session.execute.return_value.fetchone.return_value = None

    out = get_weekly_insight_history(session, USER_ID, weeks=1)

    assert out["has_history"] is True
    easy = out["systems"]["easy"]
    assert easy["pace_target_display"] == expected["pace_target_display"]
    assert easy["hr_target_display"] == expected["hr_target_display"]
    assert (
        easy["hr_progress_z2_range_display"] == expected["hr_progress_z2_range_display"]
    )
    assert easy["insights_easy_banner"] == expected["insights_easy_banner"]
    assert easy["hr_drift_target_display"] == global_kpi["hr_drift_target_display"]
    assert easy["efficiency_goal_display"] == global_kpi["efficiency_goal_display"]
    assert easy["zones"] == global_kpi["zones"]
    assert easy["efficiency_zones"] == global_kpi["efficiency_zones"]
    assert "weekly_data" not in out


def test_global_kpi_authority_payload_matches_hr_zone_constants():
    expected = build_insights_easy_global_kpi_chart_authority_payload()
    assert expected["zones"] == hr_drift_band_zones_chart()
    assert expected["efficiency_zones"] == aerobic_efficiency_band_zones_chart()
    assert (
        expected["hr_drift_target_display"] == "under 2.5% ideal, under 5% acceptable"
    )
    assert expected["efficiency_goal_display"] == "higher is better at the same effort"


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
    return_value=_calibrated_profile_with_paces(),
)
@patch(
    "src.smartcoach_mobile_coach.insights_chart_authority.get_active_or_most_recent_plan",
    return_value=_plan_with_target(),
)
@patch(
    "src.smartcoach_mobile_coach.weekly_insights_service.get_primary_athlete_id",
    return_value=12345,
)
def test_weekly_history_includes_global_kpi_authority(
    _mock_athlete,
    _mock_plan,
    _mock_profile,
    _mock_phase,
    _mock_tempo_batch,
):
    global_kpi = build_insights_easy_global_kpi_chart_authority_payload()
    session = MagicMock()
    session.execute.return_value.fetchall.return_value = []

    out = get_weekly_insight_history(session, USER_ID, weeks=1)
    easy = out["systems"]["easy"]

    assert easy["hr_drift_target_display"] == global_kpi["hr_drift_target_display"]
    assert easy["efficiency_goal_display"] == global_kpi["efficiency_goal_display"]
    assert easy["zones"] == global_kpi["zones"]
    assert easy["efficiency_zones"] == global_kpi["efficiency_zones"]


def test_build_easy_system_slice_always_includes_global_kpi():
    from src.smartcoach_mobile_coach.weekly_insights_service import (
        _build_easy_system_slice,
    )

    global_kpi = build_insights_easy_global_kpi_chart_authority_payload()
    easy_slice = _build_easy_system_slice(
        pace_recs=None,
        pace_zones=[],
        hr_zones=[],
    )

    assert (
        easy_slice["hr_drift_target_display"] == global_kpi["hr_drift_target_display"]
    )
    assert (
        easy_slice["efficiency_goal_display"] == global_kpi["efficiency_goal_display"]
    )
    assert easy_slice["zones"] == global_kpi["zones"]
    assert easy_slice["efficiency_zones"] == global_kpi["efficiency_zones"]
    assert easy_slice["pace_target_display"] is None
    assert easy_slice["hr_target_display"] is None
