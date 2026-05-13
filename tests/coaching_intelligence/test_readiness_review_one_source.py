"""Wave 2: runner-review assessment_status matches plan_generation_readiness only."""

from __future__ import annotations

from src.coaching_intelligence.plan_generation_readiness import (
    evaluate_plan_generation_readiness,
)
from src.coaching_intelligence.pre_generation_runner_review import (
    STATUS_NEEDS_DECISION,
    STATUS_NEEDS_INFO,
    STATUS_READY,
    assessment_status_from_readiness,
    build_pre_generation_runner_review_v1,
    classify_assessment_status_v1,
)
from tests.coaching_intelligence.ambition_gap_fixtures import (
    synthetic_ambition_attributions,
)


def _plan_sub3_three_days() -> dict:
    return {
        "race_distance": "Marathon",
        "primary_goal": "Target Time",
        "target_time": "3:00:00",
        "training_days": ["Mon", "Wed", "Sat"],
        "race_date": "2027-01-01",
    }


def _assessment_coherent_established() -> dict:
    return {
        "activity_summary": {
            "activities_found": 5,
            "avg_miles_per_week_approx": 45.0,
            "longest_run_miles": 18.0,
            "lookback_weeks": 6,
            "completed_calendar_weeks_count": 4,
        },
        "ambition_gap": {
            "stance": "COHERENT",
            "baseline_band": "ESTABLISHED",
            "goal_demand": "TIME_TARGET",
            "thin_baseline_data": False,
            "attributions": synthetic_ambition_attributions(
                baseline_band="ESTABLISHED",
                goal_demand="TIME_TARGET",
                thin_baseline_data=False,
                longest_run_miles=18.0,
            ),
        },
        "intake_alignment_state": {
            "generation_ready": True,
            "unresolved_flags": [],
        },
    }


def test_classify_equals_mapping_of_evaluate_plan_generation_readiness():
    assessment = _assessment_coherent_established()
    plan = _plan_sub3_three_days()
    readiness = evaluate_plan_generation_readiness(
        plan_request=plan,
        assessment_api=assessment,
    )
    assert classify_assessment_status_v1(
        assessment_api=assessment,
        plan_request=plan,
    ) == assessment_status_from_readiness(readiness)
    assert assessment_status_from_readiness(readiness) == STATUS_NEEDS_DECISION


def test_build_review_assessment_status_matches_explicit_readiness():
    assessment = _assessment_coherent_established()
    plan = _plan_sub3_three_days()
    readiness = evaluate_plan_generation_readiness(
        plan_request=plan,
        assessment_api=assessment,
    )
    review = build_pre_generation_runner_review_v1(
        assessment_api=assessment,
        plan_request=plan,
        plan_generation_readiness=readiness,
    )
    assert review.assessment_status == assessment_status_from_readiness(readiness)


def test_alignment_unresolved_is_needs_more_info_via_readiness():
    assessment = {
        "activity_summary": {
            "activities_found": 4,
            "avg_miles_per_week_approx": 30.0,
            "lookback_weeks": 6,
            "completed_calendar_weeks_count": 4,
        },
        "intake_alignment_state": {
            "generation_ready": False,
            "unresolved_flags": ["frequency_flexibility"],
        },
        "ambition_gap": {
            "stance": "MANAGEABLE_TENSION",
            "baseline_band": "MODERATE",
            "goal_demand": "TIME_TARGET",
            "thin_baseline_data": False,
            "attributions": synthetic_ambition_attributions(
                baseline_band="MODERATE",
                goal_demand="TIME_TARGET",
                thin_baseline_data=False,
                longest_run_miles=10.0,
            ),
        },
    }
    plan = {
        "primary_goal": "Just Finish",
        "race_distance": "Marathon",
        "race_date": "2027-06-01",
        "training_days": ["Mon", "Wed", "Fri"],
    }
    readiness = evaluate_plan_generation_readiness(
        plan_request=plan,
        assessment_api=assessment,
    )
    assert assessment_status_from_readiness(readiness) == STATUS_NEEDS_INFO
    assert (
        classify_assessment_status_v1(
            assessment_api=assessment,
            plan_request=plan,
        )
        == STATUS_NEEDS_INFO
    )


def test_coherent_just_finish_ready_matches():
    assessment = {
        "activity_summary": {
            "activities_found": 8,
            "avg_miles_per_week_approx": 32.0,
            "lookback_weeks": 6,
            "completed_calendar_weeks_count": 4,
        },
        "intake_alignment_state": {
            "generation_ready": True,
            "unresolved_flags": [],
        },
        "ambition_gap": {
            "stance": "COHERENT",
            "baseline_band": "MODERATE",
            "goal_demand": "FINISH",
            "thin_baseline_data": False,
            "attributions": synthetic_ambition_attributions(
                baseline_band="MODERATE",
                goal_demand="FINISH",
                thin_baseline_data=False,
                longest_run_miles=10.0,
            ),
        },
    }
    plan = {
        "primary_goal": "Just Finish",
        "race_distance": "Marathon",
        "race_date": "2027-06-01",
        "training_days": ["Mon", "Wed"],
    }
    readiness = evaluate_plan_generation_readiness(
        plan_request=plan,
        assessment_api=assessment,
    )
    assert assessment_status_from_readiness(readiness) == STATUS_READY
    assert (
        classify_assessment_status_v1(
            assessment_api=assessment,
            plan_request=plan,
        )
        == STATUS_READY
    )
