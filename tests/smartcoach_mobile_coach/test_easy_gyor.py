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
from src.smartcoach_mobile_coach.runner_profile.recommendations.gyor.easy import (
    build_easy_gyor_reference,
    build_easy_pace_progress_zones_chart,
    classify_easy_gyor,
    classify_easy_pace_progress,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.pace_progress_easy import (
    compute_pace_progress_easy_corridor,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.gyor.fusion import (
    fuse_gyor_hr_priority,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.gyor.models import (
    GyorPacePosition,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.gyor.pace_position import (
    classify_pace_position,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.training_pace_recommendations import (
    build_training_pace_recommendations,
)


def _reference():
    bands = compute_goal_aligned_pace_bands("3:40:00")
    assert bands is not None
    return build_easy_gyor_reference(
        hr_target_z2=HrZoneBand(120, 145),
        goal_aligned_easy_pace=bands.easy,
        target_time="3:40:00",
    )


def _pace_progress_corridor():
    corridor = compute_pace_progress_easy_corridor("3:40:00")
    assert corridor is not None
    return corridor


def test_fast_pace_stays_green_when_hr_is_easy():
    ref = _reference()
    assert ref is not None
    # 8:45/mi is faster than ~9:18–9:48 goal corridor; HR in Z2.
    result = classify_easy_gyor(
        pace_sec_per_mi=525.0,
        avg_hr_bpm=132.0,
        reference=ref,
    )
    assert result is not None
    assert result.band_pace in ("yellow", "orange", "red")
    assert result.band_hr == "green"
    assert result.band == "green"
    assert result.pace_direction == "fast"


def test_fast_pace_downgrades_when_hr_is_elevated():
    ref = _reference()
    assert ref is not None
    result = classify_easy_gyor(
        pace_sec_per_mi=525.0,
        avg_hr_bpm=148.0,
        reference=ref,
    )
    assert result is not None
    assert result.band_hr == "yellow"
    assert result.band == "yellow"


def test_hr_red_wins_over_easy_pace():
    ref = _reference()
    assert ref is not None
    result = classify_easy_gyor(
        pace_sec_per_mi=630.0,
        avg_hr_bpm=170.0,
        reference=ref,
    )
    assert result is not None
    assert result.band_hr == "red"
    assert result.band == "red"


def test_slow_pace_capped_at_yellow_with_green_hr():
    ref = _reference()
    assert ref is not None
    pace_position = classify_pace_position(
        700.0,
        goal_aligned_easy_pace=ref.goal_aligned_easy_pace,
    )
    assert pace_position is not None
    assert pace_position.direction == "slow"
    assert pace_position.band == "yellow"
    result = classify_easy_gyor(
        pace_sec_per_mi=700.0,
        avg_hr_bpm=130.0,
        reference=ref,
    )
    assert result is not None
    assert result.band == "yellow"


def test_fusion_hr_priority_v1_direct_cases():
    assert (
        fuse_gyor_hr_priority(
            band_hr="green",
            pace_position=GyorPacePosition(band="orange", direction="fast"),
        )
        == "green"
    )
    assert (
        fuse_gyor_hr_priority(
            band_hr="yellow",
            pace_position=GyorPacePosition(band="green", direction="inside"),
        )
        == "yellow"
    )
    assert (
        fuse_gyor_hr_priority(
            band_hr=None,
            pace_position=GyorPacePosition(band="red", direction="fast"),
        )
        == "orange"
    )


def test_pace_progress_faster_than_goal_is_ahead():
    corridor = _pace_progress_corridor()
    # Faster than pace-progress fast edge.
    assert (
        classify_easy_pace_progress(
            pace_sec_per_mi=float(corridor.low_sec) - 10.0,
            pace_progress_corridor=corridor,
        )
        == "ahead"
    )


def test_pace_progress_inside_corridor_is_green():
    corridor = _pace_progress_corridor()
    mid = (float(corridor.low_sec) + float(corridor.high_sec)) / 2.0
    assert (
        classify_easy_pace_progress(
            pace_sec_per_mi=mid,
            pace_progress_corridor=corridor,
        )
        == "green"
    )


def test_pace_progress_slow_tiers_vs_goal():
    corridor = _pace_progress_corridor()
    hi = float(corridor.high_sec)
    assert (
        classify_easy_pace_progress(
            pace_sec_per_mi=hi + 10.0, pace_progress_corridor=corridor
        )
        == "yellow"
    )
    assert (
        classify_easy_pace_progress(
            pace_sec_per_mi=hi + 25.0, pace_progress_corridor=corridor
        )
        == "orange"
    )
    assert (
        classify_easy_pace_progress(
            pace_sec_per_mi=hi + 50.0, pace_progress_corridor=corridor
        )
        == "red"
    )


def test_easy_pace_progress_zones_separate_ahead_and_target():
    corridor = _pace_progress_corridor()
    z = build_easy_pace_progress_zones_chart(corridor)
    colors = [x["color"] for x in z]
    assert colors[0] == "ahead"
    assert "green" in colors
    assert colors.count("green") == 1
    assert "yellow" in colors
    assert "red" in colors
    green = next(x for x in z if x["color"] == "green")
    ahead = next(x for x in z if x["color"] == "ahead")
    assert float(ahead["max"]) == float(green["min"])
    assert float(green["max"]) == float(corridor.high_sec) / 60.0


def test_training_pace_recommendations_includes_easy_gyor():
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
        pace_z2=PaceZoneBand(540, 570, display="9:00–9:30/mi"),
        pace_z3=PaceZoneBand(510, 525, display="8:30–8:45/mi"),
        pace_z4=PaceZoneBand(465, 475, display="7:45–7:55/mi"),
        pace_source="performance",
        pace_computed_at=datetime.now(timezone.utc),
    )
    recs = build_training_pace_recommendations(
        profile=profile,
        target_time="3:40:00",
        phase="Base",
    )
    assert recs is not None
    assert recs.easy_gyor is not None
    assert recs.easy_gyor.policy == "hr_priority_v1"
    assert len(recs.easy_gyor.pace_zones_chart) >= 5
    assert recs.easy_gyor.pace_progress_easy_corridor is not None
    assert (
        recs.easy_gyor.goal_aligned_easy_pace.low_sec
        == recs.goal_aligned_easy_pace.low_sec
    )
    green = next(z for z in recs.easy_gyor.pace_zones_chart if z["color"] == "green")
    assert (
        float(green["max"])
        == float(recs.easy_gyor.pace_progress_easy_corridor.high_sec) / 60.0
    )
    assert (
        recs.easy_gyor.pace_progress_easy_corridor.high_sec
        < recs.goal_aligned_easy_pace.high_sec
    )
