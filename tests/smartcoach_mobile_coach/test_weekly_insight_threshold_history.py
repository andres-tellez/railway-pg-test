"""Weekly-history ``systems.threshold`` pace-only slice (A1)."""

from __future__ import annotations

import json
from src.smartcoach_mobile_coach.insights_systems import InsightsSystem
from src.smartcoach_mobile_coach.runner_profile.models import PaceZoneBand
from src.smartcoach_mobile_coach.runner_profile.recommendations.models import (
    GoalAlignedPaceBands,
    TrainingPaceRecommendations,
)
from src.smartcoach_mobile_coach.weekly_insights_service import (
    _attach_threshold_segment_history_point,
    _build_threshold_system_slice,
)

USER_ID = "e3362637-9045-4aac-83ed-92bc1f2643b9"


def _pace_recs() -> TrainingPaceRecommendations:
    z4 = PaceZoneBand(low_sec=420, high_sec=450, display="7:00–7:30 /mi")
    goal = GoalAlignedPaceBands(
        easy=PaceZoneBand(540, 600, "9:00–10:00 /mi"),
        z3=PaceZoneBand(480, 510, "8:00–8:30 /mi"),
        z4=z4,
        marathon=PaceZoneBand(400, 430, "6:40–7:10 /mi"),
        marathon_sec=420 * 60,
        source_target_time="3:30:00",
    )
    return TrainingPaceRecommendations(
        phase="build",
        source_target_time="3:30:00",
        activity_easy_pace=None,
        activity_z3_pace=None,
        activity_z4_pace=None,
        goal_aligned_easy_pace=goal.easy,
        goal_aligned_z3_pace=goal.z3,
        goal_aligned_z4_pace=goal.z4,
        goal_aligned_marathon_pace=goal.marathon,
    )


def test_sample_systems_threshold_weekly_data_point():
    """Document expected pace-only ``systems.threshold.weekly_data`` shape."""
    from src.smartcoach_mobile_coach.execution_analytics.threshold_segment import (
        ThresholdSegmentPaceResult,
    )

    segment = ThresholdSegmentPaceResult(
        threshold_segment_pace_min_per_mi=7.05,
        threshold_segment_avg_hr_bpm=166.0,
        threshold_segment_pace_source="splits_hr_z4",
        threshold_segment_split_count=2,
        threshold_segment_confidence="high",
    )
    point = _attach_threshold_segment_history_point(
        {"label": "5/18", "value": None, "band": None},
        target_threshold_pace=_pace_recs().goal_aligned_z4_pace,
        segment=segment,
    )
    sample = {
        "systems": {
            "threshold": {
                "weekly_data": [point],
                "pace_zones": [{"color": "green", "min": 6.5, "max": 8.0}],
                "hr_zones": [],
                "pace_target_display": "7:00–7:30 /mi",
            }
        }
    }
    assert (
        sample["systems"]["threshold"]["weekly_data"][0][
            "threshold_segment_pace_min_per_mi"
        ]
        == 7.05
    )
    assert (
        sample["systems"]["threshold"]["weekly_data"][0][
            "threshold_segment_pace_source"
        ]
        == "splits_hr_z4"
    )
    assert (
        "threshold_hr_progress_band"
        not in sample["systems"]["threshold"]["weekly_data"][0]
    )
    json.dumps(sample)


def test_build_threshold_system_slice_pace_only():
    slice_payload = _build_threshold_system_slice(
        pace_recs=_pace_recs(),
        weekly_data=[],
        pace_zones=[{"color": "green", "min": 6.0, "max": 8.0}],
    )
    assert slice_payload["hr_zones"] == []
    assert slice_payload["pace_target_display"] == "7:00–7:30 /mi"


def test_threshold_history_point_attached_with_pace_band():
    from src.smartcoach_mobile_coach.execution_analytics.threshold_segment import (
        ThresholdSegmentPaceResult,
    )

    segment = ThresholdSegmentPaceResult(
        threshold_segment_pace_min_per_mi=7.1,
        threshold_segment_avg_hr_bpm=166.0,
        threshold_segment_pace_source="splits_hr_z4",
        threshold_segment_split_count=2,
        threshold_segment_confidence="high",
    )
    point = _attach_threshold_segment_history_point(
        {"label": "5/18", "value": None, "band": None},
        target_threshold_pace=_pace_recs().goal_aligned_z4_pace,
        segment=segment,
    )
    assert point["threshold_segment_pace_source"] == "splits_hr_z4"
    assert point["threshold_pace_progress_band"] is not None
    assert point["value"] == 7.1
