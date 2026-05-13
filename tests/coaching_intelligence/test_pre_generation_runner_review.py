from __future__ import annotations

from src.coaching_intelligence.plan_generation_readiness import (
    evaluate_plan_generation_readiness,
)
from src.coaching_intelligence.pre_generation_runner_review import (
    SCHEMA_VERSION,
    STATUS_NEEDS_DECISION,
    STATUS_READY,
    build_pre_generation_runner_review_v1,
    classify_assessment_status_v1,
    pre_generation_runner_review_system_section,
)
from tests.coaching_intelligence.ambition_gap_fixtures import (
    synthetic_ambition_attributions,
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


def _base_plan_request() -> dict:
    return {
        "primary_goal": "Just Finish",
        "race_distance": "Marathon",
        "race_date": "2027-06-01",
        "training_days": ["Mon", "Wed", "Sat"],
    }


def test_classify_empty_activity_is_needs_user_decision_insufficient_data():
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
            "baseline_band": "THIN",
            "goal_demand": "FINISH",
            "thin_baseline_data": True,
            "attributions": synthetic_ambition_attributions(
                baseline_band="THIN",
                goal_demand="FINISH",
                thin_baseline_data=True,
                longest_run_miles=0.0,
            ),
        },
    }
    assert (
        classify_assessment_status_v1(
            assessment_api=assessment_api,
            plan_request=_base_plan_request(),
        )
        == STATUS_NEEDS_DECISION
    )


def test_classify_unresolved_alignment_flags_is_needs_user_decision_with_alignment_action():
    assessment_api = {
        "activity_summary": {
            "activities_found": 4,
            "avg_miles_per_week_approx": 30.0,
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
    assert (
        classify_assessment_status_v1(
            assessment_api=assessment_api,
            plan_request=_base_plan_request(),
        )
        == STATUS_NEEDS_DECISION
    )
    readiness = evaluate_plan_generation_readiness(
        plan_request=_base_plan_request(),
        assessment_api=assessment_api,
    )
    assert "provide_alignment_answers" in readiness["allowed_user_actions"]


def test_marathon_three_hours_three_days_review_names_structural_tradeoff():
    """Goal-realism path uses concrete goal + run-day count in summary/concerns."""
    assessment_api = _coherent_marathon_target_time_assessment()
    plan_request = _marathon_target_time_plan(
        target_time="3:00:00",
        training_days=["Mon", "Wed", "Sat"],
    )
    review = build_pre_generation_runner_review_v1(
        assessment_api=assessment_api,
        plan_request=plan_request,
    )
    blob = " ".join(review.summary_lines + review.concerns).lower()
    assert "3:00" in blob
    assert "running day" in blob or "day(s)" in blob
    assert review.assessment_status == STATUS_NEEDS_DECISION


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
    assert (
        classify_assessment_status_v1(
            assessment_api=assessment_api,
            plan_request=_base_plan_request(),
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
        "ambition_gap": {
            "stance": "COHERENT",
            "baseline_band": "MODERATE",
            "goal_demand": "FINISH",
            "thin_baseline_data": False,
            "attributions": synthetic_ambition_attributions(
                baseline_band="MODERATE",
                goal_demand="FINISH",
                thin_baseline_data=False,
                longest_run_miles=8.0,
            ),
        },
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


def test_tension_after_alignment_summary_prefers_attribution_phrase():
    readiness = {
        "decision": "defer",
        "readiness_level": "stretch",
        "required_changes": [],
        "reason_codes": ["RULE_TENSION_AFTER_ALIGNMENT"],
    }
    assessment_api = {
        "activity_summary": {
            "activities_found": 4,
            "avg_miles_per_week_approx": 18.0,
        },
        "intake_alignment_state": {
            "generation_ready": True,
            "unresolved_flags": [],
        },
        "ambition_gap": {
            "stance": "HIGH_TENSION",
            "baseline_band": "THIN",
            "goal_demand": "TIME_TARGET",
            "attributions": [
                "RULE_BASELINE_BAND_THIN",
                "RULE_GOAL_DEMAND_TIME_TARGET",
                "STANCE_HIGH_TENSION_TIME_VS_THIN_BASELINE",
            ],
        },
    }
    plan_request = {
        "primary_goal": "Target Time",
        "race_distance": "Marathon",
        "race_date": "2027-06-01",
        "target_time": "3:30:00",
        "training_days": ["Mon", "Wed", "Fri", "Sat"],
    }
    review = build_pre_generation_runner_review_v1(
        assessment_api=assessment_api,
        plan_request=plan_request,
        plan_generation_readiness=readiness,
    )
    blob = " ".join(review.summary_lines).lower()
    assert "sharp mismatch between your time goal and a thin training baseline" in blob
    assert "thin training baseline" in blob


def test_tension_after_alignment_without_stance_codes_uses_baseline_band_copy():
    """Narrative does not paraphrase legacy ``stance`` when ``STANCE_*`` absent."""
    readiness = {
        "decision": "defer",
        "readiness_level": "stretch",
        "required_changes": [],
        "reason_codes": ["RULE_TENSION_AFTER_ALIGNMENT"],
    }
    assessment_api = {
        "activity_summary": {
            "activities_found": 4,
            "avg_miles_per_week_approx": 18.0,
        },
        "intake_alignment_state": {
            "generation_ready": True,
            "unresolved_flags": [],
        },
        "ambition_gap": {
            "stance": "HIGH_TENSION",
            "baseline_band": "THIN",
            "goal_demand": "TIME_TARGET",
            "attributions": [
                "RULE_BASELINE_BAND_THIN",
                "RULE_GOAL_DEMAND_TIME_TARGET",
            ],
        },
    }
    plan_request = {
        "primary_goal": "Target Time",
        "race_distance": "Marathon",
        "race_date": "2027-06-01",
        "target_time": "3:30:00",
        "training_days": ["Mon", "Wed", "Fri", "Sat"],
    }
    review = build_pre_generation_runner_review_v1(
        assessment_api=assessment_api,
        plan_request=plan_request,
        plan_generation_readiness=readiness,
    )
    blob = " ".join(review.summary_lines).lower()
    assert "stretched relative to baseline band" in blob
    assert "high tension between your time goal" not in blob


def test_pre_generation_runner_review_system_section_non_empty():
    assessment_api = {
        "activity_summary": {"activities_found": 2, "avg_miles_per_week_approx": 25.0},
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
                longest_run_miles=8.0,
            ),
        },
    }
    review = build_pre_generation_runner_review_v1(
        assessment_api=assessment_api,
        plan_request=_base_plan_request(),
    )
    api = review.as_api_dict()
    readiness = evaluate_plan_generation_readiness(
        plan_request=_base_plan_request(),
        assessment_api=assessment_api,
    )
    api["plan_generation_readiness"] = readiness
    section = pre_generation_runner_review_system_section(api)
    assert "Pre-generation runner review" in section
    assert "assessment_status" in section
    assert "runner_analysis_display (USER / UI" in section
    assert "coach_analysis_for_llm (LLM CONTEXT" in section
