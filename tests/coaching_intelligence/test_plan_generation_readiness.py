from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from src.coaching_intelligence.plan_generation_readiness import (
    CATEGORY_CONSISTENCY,
    CATEGORY_DATA_CONFIDENCE,
    CATEGORY_EFFORT_CONTROL,
    CATEGORY_GOAL_DEMAND,
    CATEGORY_LONG_RUN_DURABILITY,
    CATEGORY_ORDER,
    CATEGORY_TIMELINE,
    CATEGORY_TRAINING_AVAILABILITY,
    CATEGORY_VOLUME_BASELINE,
    DECISION_ALLOW,
    DECISION_BLOCK,
    DECISION_DEFER,
    GOAL_PROFILE_COMPLETION,
    GOAL_PROFILE_COMPETITIVE_PERFORMANCE,
    GOAL_PROFILE_MODERATE_PERFORMANCE,
    LEVEL_CURRENTLY_UNREALISTIC,
    LEVEL_HIGH_RISK,
    LEVEL_INSUFFICIENT_DATA,
    LEVEL_READY,
    LEVEL_STRETCH,
    SCHEMA_VERSION,
    STATUS_BAD,
    STATUS_OK,
    STATUS_WARN,
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
    act: dict = {
        "avg_miles_per_week_approx": avg_mpw,
        "longest_run_miles": longest,
        "activities_found": activities_found,
        "lookback_weeks": 6,
        "completed_calendar_weeks_count": 4 if activities_found > 0 else 0,
    }
    return {
        "schema_version": "pre_generation_runner_assessment.v1",
        "activity_summary": act,
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


def test_readiness_payload_json_serializable_when_plan_request_has_date_objects():
    """Regression: agent-messages persists assistant payload via json.dumps."""
    plan = _plan(race_date=date(2026, 10, 11))
    out = evaluate_plan_generation_readiness(
        plan_request=plan,
        assessment_api=_assessment(),
    )
    raw = json.dumps(out)
    assert "2026-10-11" in raw
    assert isinstance(json.loads(raw)["inputs_digest"]["race_date"], str)

    plan_dt = _plan(race_date=datetime(2026, 10, 11, 12, 30))
    out_dt = evaluate_plan_generation_readiness(
        plan_request=plan_dt,
        assessment_api=_assessment(),
    )
    assert isinstance(json.loads(json.dumps(out_dt))["inputs_digest"]["race_date"], str)


def test_readiness_nested_in_response_shape_json_serializable():
    plan = _plan(race_date=date(2026, 10, 11))
    readiness = evaluate_plan_generation_readiness(
        plan_request=plan,
        assessment_api=_assessment(),
    )
    payload = {
        "type": "text",
        "content": "x",
        "data": {
            "plan_intake_state": {"ux": {"plan_generation_readiness": readiness}},
            "pre_generation_runner_review": {
                "plan_generation_readiness": readiness,
                "assessment_status": "needs_user_decision",
            },
        },
    }
    json.dumps(payload)


def test_v2_schema_category_assessments_shape_and_order():
    out = evaluate_plan_generation_readiness(
        plan_request=_plan(),
        assessment_api=_assessment(),
    )
    assert out["schema_version"] == SCHEMA_VERSION
    assert SCHEMA_VERSION == "plan_generation_readiness.v2.1"
    assert out["goal_profile"] == GOAL_PROFILE_COMPETITIVE_PERFORMANCE
    cats = out.get("category_assessments")
    assert isinstance(cats, list)
    assert [c["category_id"] for c in cats] == list(CATEGORY_ORDER)
    for row in cats:
        assert row["status"] in (STATUS_OK, STATUS_WARN, STATUS_BAD)
        assert "applies_to_goal" in row
        assert isinstance(row.get("reason_codes"), list)
        assert isinstance(row.get("facts_used"), dict)


def test_sub3_three_days_marks_training_availability_bad():
    out = evaluate_plan_generation_readiness(
        plan_request=_plan(training_days=["Mon", "Wed", "Sat"]),
        assessment_api=_assessment(
            avg_mpw=24.0, longest=12.0, baseline_band="MODERATE"
        ),
    )
    by_id = {c["category_id"]: c for c in out["category_assessments"]}
    assert by_id[CATEGORY_TRAINING_AVAILABILITY]["status"] == STATUS_BAD
    assert (
        "RULE_SUB3_THREE_DAYS_HIGH_RISK"
        in by_id[CATEGORY_TRAINING_AVAILABILITY]["reason_codes"]
    )


def test_ready_coherent_finish_goal_marks_most_categories_ok():
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
    by_id = {c["category_id"]: c for c in out["category_assessments"]}
    assert out["decision"] == DECISION_ALLOW
    assert out["goal_profile"] == GOAL_PROFILE_COMPLETION
    for cid in (
        CATEGORY_GOAL_DEMAND,
        CATEGORY_TRAINING_AVAILABILITY,
        CATEGORY_VOLUME_BASELINE,
        CATEGORY_LONG_RUN_DURABILITY,
        CATEGORY_TIMELINE,
        CATEGORY_CONSISTENCY,
        CATEGORY_DATA_CONFIDENCE,
    ):
        assert by_id[cid]["status"] == STATUS_OK
    assert by_id[CATEGORY_EFFORT_CONTROL]["applies_to_goal"] is False
    assert by_id[CATEGORY_EFFORT_CONTROL]["status"] == STATUS_OK


def test_same_volume_finish_is_not_sub3_unrealistic():
    """Completion profile must not hit sub-3 currently_unrealistic for the same volume."""
    shared = dict(
        avg_mpw=12.0,
        longest=8.0,
        activities_found=10,
        baseline_band="THIN",
        stance="COHERENT",
        goal_demand="FINISH",
    )
    finish = evaluate_plan_generation_readiness(
        plan_request=_plan(
            primary_goal="Just Finish",
            target_time="",
            training_days=["Mon", "Tue", "Wed", "Sat"],
        ),
        assessment_api=_assessment(**shared),
    )
    assert finish["goal_profile"] == GOAL_PROFILE_COMPLETION
    assert finish["readiness_level"] != LEVEL_CURRENTLY_UNREALISTIC
    assert finish["decision"] == DECISION_ALLOW

    sub3 = evaluate_plan_generation_readiness(
        plan_request=_plan(
            primary_goal="Target Time",
            target_time="3:00:00",
            training_days=["Mon", "Tue", "Wed", "Sat"],
        ),
        assessment_api=_assessment(
            avg_mpw=12.0,
            longest=8.0,
            activities_found=10,
            baseline_band="THIN",
            stance="HIGH_TENSION",
            goal_demand="TIME_TARGET",
        ),
    )
    assert sub3["goal_profile"] == GOAL_PROFILE_COMPETITIVE_PERFORMANCE
    assert sub3["readiness_level"] == LEVEL_CURRENTLY_UNREALISTIC
    assert sub3["decision"] == DECISION_DEFER


def test_marathon_target_331_is_moderate_profile():
    out = evaluate_plan_generation_readiness(
        plan_request=_plan(target_time="3:31:00", primary_goal="Target Time"),
        assessment_api=_assessment(
            avg_mpw=40.0,
            longest=16.0,
            baseline_band="ESTABLISHED",
            stance="COHERENT",
            goal_demand="TIME_TARGET",
        ),
    )
    assert out["goal_profile"] == GOAL_PROFILE_MODERATE_PERFORMANCE


def test_marathon_target_330_is_competitive_profile():
    out = evaluate_plan_generation_readiness(
        plan_request=_plan(target_time="3:30:00", primary_goal="Target Time"),
        assessment_api=_assessment(
            avg_mpw=40.0,
            longest=16.0,
            baseline_band="ESTABLISHED",
            stance="COHERENT",
            goal_demand="TIME_TARGET",
        ),
    )
    assert out["goal_profile"] == GOAL_PROFILE_COMPETITIVE_PERFORMANCE


def test_high_tension_time_goal_marathon_is_competitive_despite_slow_target():
    out = evaluate_plan_generation_readiness(
        plan_request=_plan(target_time="4:15:00", primary_goal="Target Time"),
        assessment_api=_assessment(
            avg_mpw=20.0,
            longest=10.0,
            baseline_band="THIN",
            stance="HIGH_TENSION",
            goal_demand="TIME_TARGET",
        ),
    )
    assert out["goal_profile"] == GOAL_PROFILE_COMPETITIVE_PERFORMANCE


def test_bq_notes_make_marathon_time_goal_competitive_profile():
    out = evaluate_plan_generation_readiness(
        plan_request={
            **_plan(target_time="3:45:00", primary_goal="Target Time"),
            "notes": "BQ attempt — peak training block",
        },
        assessment_api=_assessment(
            avg_mpw=35.0,
            longest=14.0,
            baseline_band="MODERATE",
            stance="MANAGEABLE_TENSION",
            goal_demand="TIME_TARGET",
        ),
    )
    assert out["goal_profile"] == GOAL_PROFILE_COMPETITIVE_PERFORMANCE

    plan = _plan(race_date=date(2026, 10, 11))
    out = evaluate_plan_generation_readiness(
        plan_request=plan,
        assessment_api=_assessment(),
    )
    raw = json.dumps(out, default=str)
    data = json.loads(raw)
    for row in data["category_assessments"]:
        json.dumps(row["facts_used"])


def test_review_system_section_includes_category_assessments():
    from src.coaching_intelligence.pre_generation_runner_review import (
        pre_generation_runner_review_system_section,
    )

    txt = pre_generation_runner_review_system_section(
        {
            "assessment_status": "ready_to_generate",
            "summary_lines": ["Summary line"],
            "plan_generation_readiness": {
                "decision": "defer",
                "readiness_level": "high_risk",
                "allowed_user_actions": ["add_running_day"],
                "recommended_path": {"type": "add_running_day", "message": "m"},
                "goal_profile": "competitive_performance",
                "category_assessments": [
                    {
                        "category_id": "training_availability",
                        "applies_to_goal": True,
                        "status": "bad",
                        "reason_codes": ["RULE_SUB3_THREE_DAYS_HIGH_RISK"],
                        "facts_used": {"training_day_count": 3},
                    },
                ],
            },
        }
    )
    assert "Category assessments" in txt
    assert "goal_profile" in txt
    assert "training_availability" in txt


def test_plan_request_digest_json_serializable_for_pydantic_date_race():
    from src.coaching_intelligence.pre_generation_runner_assessment import (
        _plan_request_digest,
    )

    digest = _plan_request_digest(
        {
            "primary_goal": "Target Time",
            "race_distance": "Marathon",
            "race_date": date(2026, 10, 11),
            "target_time": "3:00:00",
            "training_days": ["Mon"],
        }
    )
    assert json.loads(json.dumps(digest))["race_date"] == "2026-10-11"
