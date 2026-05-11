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
