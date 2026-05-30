"""Runner profile JSON payload shape for mobile clients."""

from __future__ import annotations

from datetime import datetime, timezone

from src.smartcoach_mobile_coach.runner_profile.api_schema import (
    INSIGHTS_EASY_BANNER_SUBTITLE,
    INSIGHTS_TEMPO_BANNER_SUBTITLE,
    runner_zone_profile_payload,
)
from src.smartcoach_mobile_coach.runner_profile.models import (
    HrZoneBand,
    PaceZoneBand,
    RunnerZoneProfileData,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.training_pace_recommendations import (
    build_training_pace_recommendations,
)


def test_pace_zones_partial_includes_only_present_bands():
    """pace_zones must expose z2 even when z3/z4 pace columns are absent."""
    hr_z2 = HrZoneBand(low=120, high=145)
    pace_z2 = PaceZoneBand(
        low_sec=600,
        high_sec=630,
        display="10:00-10:30/mi",
    )
    profile = RunnerZoneProfileData(
        user_id="u",
        calibrated=True,
        computed_at=datetime.now(timezone.utc),
        hrmax_used=185,
        resting_hr_used=50,
        zone_method="karvonen",
        hr_z1=HrZoneBand(100, 115),
        hr_z2=hr_z2,
        hr_z3=HrZoneBand(146, 160),
        hr_z4=HrZoneBand(161, 175),
        hr_z5=HrZoneBand(176, 185),
        pace_z2=pace_z2,
        pace_z3=None,
        pace_z4=None,
        pace_source="calibration",
        pace_computed_at=datetime.now(timezone.utc),
    )
    payload = runner_zone_profile_payload(profile)
    pz = payload["pace_zones"]
    assert pz is not None
    assert set(pz.keys()) == {"z2"}
    assert pz["z2"]["display"] == pace_z2.display

    assert payload.get("insights_easy_banner") is None


def test_payload_includes_training_pace_recommendations_when_provided():
    profile = RunnerZoneProfileData(
        user_id="u",
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
    recs = build_training_pace_recommendations(
        profile=profile,
        target_time="3:40:00",
        race_distance="Marathon",
        phase="Base",
        phase_source="plan_workouts_current_week",
        phase_week_start="2026-05-18",
    )
    assert recs is not None

    payload = runner_zone_profile_payload(
        profile,
        training_pace_recommendations=recs,
        target_time="3:40:00",
        race_distance="Marathon",
    )
    inputs = payload.get("inputs")
    assert inputs is not None
    assert inputs["hrmax"] == 185
    assert inputs["resting_hr"] == 50
    assert inputs["target_time"] == "3:40:00"
    assert inputs["race_distance"] == "Marathon"
    assert inputs["goal_aligned_status"] == "active"
    tp = payload.get("training_pace_recommendations")
    assert tp is not None
    assert tp["phase"] == "Base"
    assert tp["phase_source"] == "plan_workouts_current_week"
    assert tp["phase_week_start"] == "2026-05-18"
    assert tp["source_target_time"] == "3:40:00"
    assert (
        tp["goal_aligned_easy_pace"]["display"] == recs.goal_aligned_easy_pace.display
    )
    assert "recommended_easy_pace" not in tp
    assert tp["easy_gyor"] is not None
    assert tp["easy_gyor"]["policy"] == "hr_priority_v1"
    assert tp["easy_gyor"]["hr_target_z2"] == {"low": 120, "high": 145}
    assert "goal_aligned_easy_pace" not in tp["easy_gyor"]
    assert "pace_progress_target_easy_pace" not in tp["easy_gyor"]
    assert "pace_zones_chart" not in tp["easy_gyor"]
    assert tp["pace_progress"] is not None
    assert (
        tp["pace_progress"]["target_easy_pace"]["low_sec"]
        == recs.pace_progress.target_easy_pace.low_sec
    )
    assert len(tp["pace_progress"]["pace_zones_chart"]) >= 4
    assert tp["tempo_pace_progress"] is not None
    assert (
        tp["tempo_pace_progress"]["target_tempo_pace"]["low_sec"]
        == recs.tempo_pace_progress.target_tempo_pace.low_sec
    )
    assert tp["tempo_pace_progress"]["target_display"] == (
        recs.tempo_pace_progress.target_display
    )
    assert len(tp["tempo_pace_progress"]["pace_zones_chart"]) >= 5
    assert "threshold_pace_progress" not in tp
    assert tp["tempo_hr_progress"] is not None
    assert tp["tempo_hr_progress"]["target_hr_z3"] == {"low": 146, "high": 160}
    assert tp["tempo_hr_progress"]["target_display"] == "146–160 bpm"
    assert len(tp["tempo_hr_progress"]["hr_zones_chart"]) >= 5
    assert tp["hr_progress"] is not None
    assert tp["hr_progress"]["target_hr_z2"] == {"low": 120, "high": 145}
    assert tp["hr_progress"]["target_display"] == "≤145 bpm"
    assert len(tp["hr_progress"]["hr_zones_chart"]) >= 4

    banner = payload.get("insights_easy_banner")
    assert banner is not None
    assert banner["subtitle"] == INSIGHTS_EASY_BANNER_SUBTITLE

    tempo_banner = payload.get("insights_tempo_banner")
    assert tempo_banner is not None
    assert tempo_banner["subtitle"] == INSIGHTS_TEMPO_BANNER_SUBTITLE

    registry = payload.get("run_type_registry")
    assert registry is not None
    threshold = next(e for e in registry if e["key"] == "threshold")
    assert threshold["pace_zone_key"] == "z4"
    assert threshold["insights_system"] == "threshold"
    assert threshold["tier"] == "primary"

    taxonomy = payload.get("plan_workout_taxonomy")
    assert taxonomy is not None
    tempo = next(entry for entry in taxonomy if entry["key"] == "tempo")
    assert tempo["display_name"] == "Tempo"
    threshold_tax = next(entry for entry in taxonomy if entry["key"] == "threshold")
    assert threshold_tax["display_name"] == "Threshold"
    assert threshold_tax["canonical_run_type_key"] == "threshold"

    authorities = payload.get("pace_authorities")
    assert authorities is not None
    assert authorities["plan"]["source"] == "activity_median"
    assert authorities["insights"]["source"] == "marathon_goal"
    assert authorities["insights"]["target_time"] == "3:40:00"
