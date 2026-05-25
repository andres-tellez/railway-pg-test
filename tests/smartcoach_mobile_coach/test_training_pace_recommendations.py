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


def test_easy_gyor_anchors_to_goal_aligned_easy_pace():
    recs = build_training_pace_recommendations(
        profile=_sample_profile(),
        target_time="3:40:00",
        phase="Base",
    )
    assert recs is not None
    assert recs.goal_aligned_easy_pace is not None
    assert recs.easy_gyor is not None
    assert (
        recs.easy_gyor.goal_aligned_easy_pace.low_sec
        == recs.goal_aligned_easy_pace.low_sec
    )
    assert (
        recs.easy_gyor.goal_aligned_easy_pace.high_sec
        == recs.goal_aligned_easy_pace.high_sec
    )
    assert recs.easy_gyor.pace_progress_target_easy_pace is not None
    assert (
        recs.easy_gyor.pace_progress_target_easy_pace.low_sec
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
    assert recs.easy_gyor is None
