from __future__ import annotations

from src.coaching_intelligence.pre_generation_runner_review import (
    SCHEMA_VERSION,
    STATUS_NEEDS_DECISION,
    STATUS_NEEDS_INFO,
    STATUS_READY,
    build_pre_generation_runner_review_v1,
    classify_assessment_status_v1,
    pre_generation_runner_review_system_section,
)


def _marathon_target_time_plan(
    *, target_time: str, training_days: list[str], race_date: str = "2027-01-01"
) -> dict:
    return {
        "race_distance": "Marathon",
        "primary_goal": "Target Time",
        "target_time": target_time,
        "training_days": training_days,
        "race_date": race_date,
    }


def _coherent_marathon_target_time_assessment() -> dict:
    return {
        "activity_summary": {
            "activities_found": 5,
            "avg_miles_per_week_approx": 45.0,
            "longest_run_miles": 18.0,
        },
        "ambition_gap": {
            "stance": "COHERENT",
            "baseline_band": "ESTABLISHED",
            "goal_demand": "TIME_TARGET",
        },
        "intake_alignment_state": {
            "generation_ready": True,
            "unresolved_flags": [],
        },
    }


def _base_plan_request() -> dict:
    return {
        "primary_goal": "Just Finish",
        "race_distance": "Marathon",
    }


def test_classify_empty_activity_is_needs_user_decision():
    assessment_api = {
        "activity_summary": {
            "activities_found": 0,
            "avg_miles_per_week_approx": 0.0,
        },
        "intake_alignment_state": {
            "generation_ready": True,
            "unresolved_flags": [],
        },
        "ambition_gap": {
            "stance": "COHERENT",
            "thin_baseline_data": False,
        },
    }
    assert (
        classify_assessment_status_v1(
            assessment_api=assessment_api,
            plan_request=_base_plan_request(),
        )
        == STATUS_NEEDS_DECISION
    )


def test_classify_unresolved_alignment_flags_is_needs_more_info():
    assessment_api = {
        "activity_summary": {
            "activities_found": 4,
            "avg_miles_per_week_approx": 30.0,
        },
        "intake_alignment_state": {
            "generation_ready": False,
            "unresolved_flags": ["frequency_flexibility"],
        },
        "ambition_gap": {"stance": "MANAGEABLE_TENSION"},
    }
    assert (
        classify_assessment_status_v1(
            assessment_api=assessment_api,
            plan_request=_base_plan_request(),
        )
        == STATUS_NEEDS_INFO
    )


def test_marathon_three_hours_flat_three_days_needs_user_decision():
    """3:00:00 is sub-3-level for review; with ≤3 run days requires explicit tradeoff."""
    assert (
        classify_assessment_status_v1(
            assessment_api=_coherent_marathon_target_time_assessment(),
            plan_request=_marathon_target_time_plan(
                target_time="3:00:00",
                training_days=["Mon", "Wed", "Sat"],
            ),
        )
        == STATUS_NEEDS_DECISION
    )


def test_marathon_two_fifty_five_three_days_still_needs_user_decision():
    assert (
        classify_assessment_status_v1(
            assessment_api=_coherent_marathon_target_time_assessment(),
            plan_request=_marathon_target_time_plan(
                target_time="2:55:00",
                training_days=["Mon", "Wed", "Fri"],
            ),
        )
        == STATUS_NEEDS_DECISION
    )


def test_marathon_three_o_one_three_days_coherent_not_tradeoff_rule():
    """Slightly over 3:00 does not use the sub-3 + ≤3 days rule; coherent path is ready."""
    assert (
        classify_assessment_status_v1(
            assessment_api=_coherent_marathon_target_time_assessment(),
            plan_request=_marathon_target_time_plan(
                target_time="3:01:00",
                training_days=["Mon", "Wed", "Sat"],
            ),
        )
        == STATUS_READY
    )


def test_classify_coherent_path_ready_to_generate():
    assessment_api = {
        "activity_summary": {
            "activities_found": 8,
            "avg_miles_per_week_approx": 32.0,
        },
        "intake_alignment_state": {
            "generation_ready": True,
            "unresolved_flags": [],
        },
        "ambition_gap": {
            "stance": "COHERENT",
            "thin_baseline_data": False,
        },
    }
    assert (
        classify_assessment_status_v1(
            assessment_api=assessment_api,
            plan_request={
                "primary_goal": "Just Finish",
                "race_distance": "Marathon",
            },
        )
        == STATUS_READY
    )


def test_as_api_dict_shape():
    assessment_api = {
        "activity_summary": {"activities_found": 3, "avg_miles_per_week_approx": 28.0},
        "intake_alignment_state": {
            "generation_ready": True,
            "unresolved_flags": [],
        },
        "ambition_gap": {"stance": "COHERENT"},
    }
    review = build_pre_generation_runner_review_v1(
        assessment_api=assessment_api,
        plan_request=_base_plan_request(),
    )
    d = review.as_api_dict()
    assert d["schema_version"] == SCHEMA_VERSION
    for key in (
        "computed_at",
        "assessment_status",
        "summary_lines",
        "concerns",
        "recommended_next_step",
        "allowed_user_actions",
    ):
        assert key in d


def test_pre_generation_runner_review_system_section_non_empty():
    assessment_api = {
        "activity_summary": {"activities_found": 2, "avg_miles_per_week_approx": 25.0},
        "intake_alignment_state": {
            "generation_ready": True,
            "unresolved_flags": [],
        },
        "ambition_gap": {"stance": "COHERENT"},
    }
    review = build_pre_generation_runner_review_v1(
        assessment_api=assessment_api,
        plan_request=_base_plan_request(),
    )
    section = pre_generation_runner_review_system_section(review.as_api_dict())
    assert "Pre-generation runner review" in section
    assert "assessment_status" in section
