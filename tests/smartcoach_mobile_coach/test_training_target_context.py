"""Tests for training_target_context read-model composer."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.smartcoach_mobile_coach.runner_profile.models import (
    HrZoneBand,
    PaceZoneBand,
    RunnerZoneProfileData,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.goal_aligned_pace import (
    GOAL_ALIGNED_STATUS_ACTIVE,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.training_phase_resolver import (
    TrainingPhaseResolution,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.training_pace_recommendations import (
    build_training_pace_recommendations,
)
from src.smartcoach_mobile_coach.runner_profile.training_target_context import (
    SCHEMA_VERSION,
    build_training_target_context,
)


def _sample_profile() -> RunnerZoneProfileData:
    return RunnerZoneProfileData(
        user_id="u-test",
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


@patch(
    "src.smartcoach_mobile_coach.runner_profile.training_target_context.get_user_profile"
)
@patch(
    "src.smartcoach_mobile_coach.runner_profile.training_target_context.compute_baseline_status_for_athlete"
)
@patch(
    "src.smartcoach_mobile_coach.runner_profile.training_target_context.get_primary_athlete_id"
)
@patch(
    "src.smartcoach_mobile_coach.runner_profile.training_target_context.get_weekly_fitness_from_materialized_view"
)
@patch(
    "src.smartcoach_mobile_coach.runner_profile.training_target_context.resolve_current_training_phase"
)
@patch(
    "src.smartcoach_mobile_coach.runner_profile.training_target_context.get_runner_training_pace_recommendations"
)
@patch(
    "src.smartcoach_mobile_coach.runner_profile.training_target_context.get_runner_profile"
)
@patch(
    "src.smartcoach_mobile_coach.runner_profile.training_target_context.get_active_or_most_recent_plan"
)
def test_build_training_target_context_keys_and_goal_bands(
    mock_plan,
    mock_profile,
    mock_recs_fn,
    mock_phase,
    mock_fitness,
    mock_athlete,
    mock_baseline,
    mock_user_profile,
):
    profile = _sample_profile()
    mock_plan.return_value = None
    mock_profile.return_value = profile
    recs = build_training_pace_recommendations(
        profile=profile,
        target_time="3:40:00",
        race_distance="Marathon",
        phase="Base",
    )
    mock_recs_fn.return_value = recs
    mock_phase.return_value = TrainingPhaseResolution(
        phase="Base",
        source="plan_span",
        week_start=None,
    )
    mock_fitness.return_value = (32.0, 14.0)
    mock_athlete.return_value = 1
    mock_baseline.return_value = MagicMock(value="strong")
    mock_user_profile.return_value = {"max_hr_active": "manual", "max_hr_manual": 185}

    session = MagicMock()
    ctx = build_training_target_context(
        session,
        "u-test",
        target_time="3:40:00",
        race_distance="Marathon",
        primary_goal="Target Time",
    )

    assert ctx["schema_version"] == SCHEMA_VERSION
    assert ctx["inputs"]["goal_aligned_status"] == GOAL_ALIGNED_STATUS_ACTIVE
    assert ctx["training_pace_recommendations"] is not None
    assert (
        ctx["training_pace_recommendations"]["goal_aligned_marathon_pace"] is not None
    )
    assert ctx["pace_authorities"]["plan"]["source"] == "activity_median"
    assert ctx["pace_authorities"]["insights"]["source"] == "marathon_goal"
    assert ctx["current_fitness"]["pace_source"] == "performance"
    assert ctx["gap_summary"]["goal_marathon_pace_sec_per_mi"] == float(
        recs.goal_aligned_marathon_pace.low_sec
    )
    assert "product_principle" in ctx
