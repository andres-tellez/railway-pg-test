from __future__ import annotations

from datetime import date, timedelta

from src.coaching_intelligence.plan_generation_readiness import (
    DECISION_ALLOW,
    DECISION_BLOCK,
    DECISION_DEFER,
    LEVEL_CURRENTLY_UNREALISTIC,
    LEVEL_HIGH_RISK,
    LEVEL_INSUFFICIENT_DATA,
    LEVEL_READY,
    LEVEL_STRETCH,
    evaluate_plan_generation_readiness,
)


def _race_date(weeks: int = 24) -> str:
    return (date.today() + timedelta(weeks=weeks)).isoformat()


def _plan(**overrides) -> dict:
    base = {
        "race_distance": "Marathon",
        "race_date": _race_date(),
        "primary_goal": "Target Time",
        "target_time": "3:00:00",
        "training_days": ["Mon", "Wed", "Sat"],
    }
    base.update(overrides)
    return base


def _assessment(
    *,
    avg_mpw: float = 12.0,
    longest: float = 8.0,
    activities_found: int = 8,
    baseline_band: str = "THIN",
    stance: str = "HIGH_TENSION",
    goal_demand: str = "TIME_TARGET",
    alignment_ready: bool = True,
    unresolved_flags: list[str] | None = None,
) -> dict:
    return {
        "schema_version": "pre_generation_runner_assessment.v1",
        "activity_summary": {
            "avg_miles_per_week_approx": avg_mpw,
            "longest_run_miles": longest,
            "activities_found": activities_found,
        },
        "ambition_gap": {
            "stance": stance,
            "baseline_band": baseline_band,
            "goal_demand": goal_demand,
            "thin_baseline_data": avg_mpw <= 0,
            "attributions": [],
        },
        "intake_alignment_state": {
            "generation_ready": alignment_ready,
            "unresolved_flags": unresolved_flags or [],
        },
    }


def test_sub3_three_days_defers_high_risk():
    out = evaluate_plan_generation_readiness(
        plan_request=_plan(training_days=["Mon", "Wed", "Sat"]),
        assessment_api=_assessment(
            avg_mpw=24.0, longest=12.0, baseline_band="MODERATE"
        ),
    )

    assert out["decision"] == DECISION_DEFER
    assert out["readiness_level"] == LEVEL_HIGH_RISK
    assert "RULE_SUB3_THREE_DAYS_HIGH_RISK" in out["reason_codes"]
    assert "create_plan" not in out["allowed_user_actions"]
    assert "add_running_day" in out["allowed_user_actions"]


def test_sub3_four_days_with_weak_baseline_defers_high_risk():
    out = evaluate_plan_generation_readiness(
        plan_request=_plan(training_days=["Mon", "Tue", "Thu", "Sat"]),
        assessment_api=_assessment(
            avg_mpw=24.0, longest=12.0, baseline_band="MODERATE"
        ),
    )

    assert out["decision"] == DECISION_DEFER
    assert out["readiness_level"] == LEVEL_HIGH_RISK
    assert "RULE_SUB3_FOUR_DAYS_WEAK_BASELINE" in out["reason_codes"]
    assert "continue_with_warning" not in out["allowed_user_actions"]


def test_sub3_very_low_mileage_and_short_long_run_is_currently_unrealistic_but_deferred():
    out = evaluate_plan_generation_readiness(
        plan_request=_plan(training_days=["Mon", "Wed", "Sat"]),
        assessment_api=_assessment(avg_mpw=12.0, longest=8.0, baseline_band="THIN"),
    )

    assert out["decision"] == DECISION_DEFER
    assert out["readiness_level"] == LEVEL_CURRENTLY_UNREALISTIC
    assert "RULE_SUB3_VERY_LOW_MILEAGE_AND_SHORT_LONG_RUN" in out["reason_codes"]
    assert out["allowed_user_actions"] == [
        "add_running_day",
        "adjust_goal",
        "adjust_timeline",
        "build_base_first",
    ]
    assert out["recommended_path"]["type"] == "build_base_first"


def test_sub3_established_profile_allows_with_stretch_warning():
    out = evaluate_plan_generation_readiness(
        plan_request=_plan(training_days=["Mon", "Tue", "Thu", "Sat", "Sun"]),
        assessment_api=_assessment(
            avg_mpw=42.0,
            longest=16.0,
            activities_found=20,
            baseline_band="ESTABLISHED",
            stance="COHERENT",
        ),
    )

    assert out["decision"] == DECISION_ALLOW
    assert out["readiness_level"] == LEVEL_STRETCH
    assert "RULE_SUB3_ESTABLISHED_BASELINE" in out["reason_codes"]
    assert "create_plan" in out["allowed_user_actions"]


def test_unresolved_alignment_defers_for_missing_alignment_answer():
    out = evaluate_plan_generation_readiness(
        plan_request=_plan(),
        assessment_api=_assessment(
            alignment_ready=False,
            unresolved_flags=["frequency_flexibility"],
        ),
    )

    assert out["decision"] == DECISION_DEFER
    assert out["readiness_level"] == LEVEL_INSUFFICIENT_DATA
    assert out["required_changes"] == ["complete_alignment_questions"]
    assert out["allowed_user_actions"] == ["provide_alignment_answers"]


def test_no_activities_defers_insufficient_data():
    out = evaluate_plan_generation_readiness(
        plan_request=_plan(race_distance="Half Marathon", target_time="1:45:00"),
        assessment_api=_assessment(
            avg_mpw=0,
            longest=0,
            activities_found=0,
            baseline_band="THIN",
        ),
    )

    assert out["decision"] == DECISION_DEFER
    assert out["readiness_level"] == LEVEL_INSUFFICIENT_DATA
    assert out["confidence"] == "low"
    assert out["allowed_user_actions"] == ["ingest_more_activity"]


def test_missing_required_field_blocks_invalid_ready_state():
    out = evaluate_plan_generation_readiness(
        plan_request=_plan(training_days=[]),
        assessment_api=_assessment(),
    )

    assert out["decision"] == DECISION_BLOCK
    assert out["readiness_level"] == LEVEL_INSUFFICIENT_DATA
    assert "RULE_REQUIRED_PLAN_FIELDS_MISSING" in out["reason_codes"]
    assert "missing_training_days" in out["limiting_factors"]


def test_coherent_established_finish_goal_is_ready():
    out = evaluate_plan_generation_readiness(
        plan_request=_plan(
            primary_goal="Just Finish",
            target_time="",
            training_days=["Tue", "Thu", "Sat", "Sun"],
        ),
        assessment_api=_assessment(
            avg_mpw=34,
            longest=14,
            activities_found=16,
            baseline_band="ESTABLISHED",
            stance="COHERENT",
            goal_demand="FINISH",
        ),
    )

    assert out["decision"] == DECISION_ALLOW
    assert out["readiness_level"] == LEVEL_READY
    assert out["allowed_user_actions"] == ["create_plan"]


def test_policy_output_is_stable_for_same_inputs():
    plan = _plan(training_days=["Mon", "Wed", "Fri", "Sat"])
    assessment = _assessment(avg_mpw=28, longest=13, baseline_band="MODERATE")

    assert evaluate_plan_generation_readiness(
        plan_request=plan,
        assessment_api=assessment,
    ) == evaluate_plan_generation_readiness(
        plan_request=plan,
        assessment_api=assessment,
    )
