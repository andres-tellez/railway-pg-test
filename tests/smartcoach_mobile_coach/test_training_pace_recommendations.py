from __future__ import annotations

from datetime import datetime, timezone

from src.smartcoach_mobile_coach.runner_profile.models import (
    HrZoneBand,
    PaceZoneBand,
    RunnerZoneProfileData,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.goal_aligned_pace import (
    compute_goal_aligned_pace_bands,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.training_pace_recommendations import (
    build_training_pace_recommendations,
)


def _sample_profile() -> RunnerZoneProfileData:
    return RunnerZoneProfileData(
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
        pace_z2=PaceZoneBand(low_sec=540, high_sec=570, display="9:00–9:30/mi"),
        pace_z3=PaceZoneBand(low_sec=510, high_sec=525, display="8:30–8:45/mi"),
        pace_z4=PaceZoneBand(low_sec=465, high_sec=475, display="7:45–7:55/mi"),
        pace_source="performance",
        pace_computed_at=datetime.now(timezone.utc),
    )


def test_goal_aligned_pace_bands_from_target_time():
    bands = compute_goal_aligned_pace_bands("3:40:00")
    assert bands is not None
    assert bands.marathon.display.endswith("/mi")
    assert 558 <= bands.easy.low_sec <= 560
    assert 588 <= bands.easy.high_sec <= 590


def test_goal_aligned_z3_tempo_corridor_340_marathon():
    """Z3 / Tempo: MP −15 to +10 sec/mi (~8:09–8:34 for a 3:40 marathon)."""
    bands = compute_goal_aligned_pace_bands("3:40:00")
    assert bands is not None
    mp = bands.marathon_sec
    assert bands.z3.low_sec == int(round(mp - 15.0))
    assert bands.z3.high_sec == int(round(mp + 10.0))
    assert 488 <= bands.z3.low_sec <= 490
    assert 513 <= bands.z3.high_sec <= 515


def test_goal_aligned_z4_threshold_corridor_340_marathon():
    """Z4 / Threshold: MP −40 to −20 sec/mi (~7:44–8:04 for a 3:40 marathon)."""
    bands = compute_goal_aligned_pace_bands("3:40:00")
    assert bands is not None
    mp = bands.marathon_sec
    assert bands.z4.low_sec == int(round(mp - 40.0))
    assert bands.z4.high_sec == int(round(mp - 20.0))
    assert 463 <= bands.z4.low_sec <= 465
    assert 483 <= bands.z4.high_sec <= 485


def test_easy_gyor_includes_hr_reference_when_calibrated():
    recs = build_training_pace_recommendations(
        profile=_sample_profile(),
        target_time="3:40:00",
        phase="Base",
    )
    assert recs is not None
    assert recs.goal_aligned_easy_pace is not None
    assert recs.easy_gyor is not None
    assert recs.easy_gyor.policy == "hr_priority_v1"
    assert recs.easy_gyor.hr_target_z2.low == 120
    assert recs.easy_gyor.hr_target_z2.high == 145
    assert recs.pace_progress is not None
    assert (
        recs.pace_progress.target_easy_pace.low_sec
        == recs.goal_aligned_easy_pace.low_sec
    )


def test_no_easy_gyor_without_target_time():
    recs = build_training_pace_recommendations(
        profile=_sample_profile(),
        target_time=None,
        phase="Base",
    )
    assert recs is not None
    assert recs.goal_aligned_easy_pace is None
    assert recs.pace_progress is None
    assert recs.easy_gyor is None


def test_pace_progress_without_hr_calibration():
    profile = RunnerZoneProfileData(
        user_id="u",
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
    recs = build_training_pace_recommendations(
        profile=profile,
        target_time="3:40:00",
        phase="Base",
    )
    assert recs is not None
    assert recs.goal_aligned_easy_pace is not None
    assert recs.pace_progress is not None
    assert recs.easy_gyor is None
    assert (
        recs.pace_progress.target_easy_pace.low_sec
        == recs.goal_aligned_easy_pace.low_sec
    )
    assert len(recs.pace_progress.pace_zones_chart) >= 4


def test_hr_progress_without_marathon_goal():
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
        pace_z2=None,
        pace_z3=None,
        pace_z4=None,
        pace_source=None,
        pace_computed_at=None,
    )
    recs = build_training_pace_recommendations(
        profile=profile,
        target_time=None,
        phase="Base",
    )
    assert recs is not None
    assert recs.pace_progress is None
    assert recs.hr_progress is not None
    assert recs.hr_progress.target_hr_z2.low == 120
    assert len(recs.hr_progress.hr_zones_chart) >= 4
