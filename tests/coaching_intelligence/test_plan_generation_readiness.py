from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from src.coaching_intelligence.plan_generation_readiness import (
    CATEGORY_CONSISTENCY,
    CATEGORY_DATA_CONFIDENCE,
    CATEGORY_EFFORT_CONTROL,
    CATEGORY_GOAL_DEMAND,
    CATEGORY_LONG_RUN_DURABILITY,
    CATEGORY_ORDER,
    CATEGORY_PERFORMANCE_ALIGNMENT,
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
    RULE_MODERATE_PERFORMANCE_PACE_GAP,
    SCHEMA_VERSION,
    STATUS_BAD,
    STATUS_OK,
    STATUS_WARN,
    evaluate_plan_generation_readiness,
)
from tests.coaching_intelligence.ambition_gap_fixtures import (
    synthetic_ambition_attributions,
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
    target_time_present: bool = True,
    **activity_extras: Any,
) -> dict:
    act: dict = {
        "avg_miles_per_week_approx": avg_mpw,
        "longest_run_miles": longest,
        "activities_found": activities_found,
        "lookback_weeks": 6,
        "completed_calendar_weeks_count": 4 if activities_found > 0 else 0,
    }
    act.update(activity_extras)
    thin = avg_mpw <= 0
    attr = synthetic_ambition_attributions(
        baseline_band=baseline_band,
        goal_demand=goal_demand,
        thin_baseline_data=thin,
        longest_run_miles=float(longest),
        target_time_present=target_time_present,
    )
    return {
        "schema_version": "pre_generation_runner_assessment.v1",
        "activity_summary": act,
        "ambition_gap": {
            "stance": stance,
            "baseline_band": baseline_band,
            "goal_demand": goal_demand,
            "thin_baseline_data": thin,
            "attributions": attr,
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
            typical_easy_pace_sec_per_mi=420.0,
            best_sustained_endurance_pace_sec_per_mi=405.0,
            pace_reliability="high",
            runs_usable_pace_count=18,
            long_runs_ge_10_mi_count=5,
            weeks_with_long_run_10plus=4,
            long_run_progression_trend="flat",
        ),
    )

    assert out["decision"] == DECISION_ALLOW
    assert out["readiness_level"] == LEVEL_STRETCH
    assert "RULE_SUB3_ESTABLISHED_BASELINE" in out["reason_codes"]
    assert "create_plan" in out["allowed_user_actions"]


def test_sub3_established_but_slow_observed_pace_escalates_to_high_risk():
    """P1: performance_alignment dominates — training structure can look fine while paces lag goal MP."""
    out = evaluate_plan_generation_readiness(
        plan_request=_plan(training_days=["Mon", "Tue", "Thu", "Sat", "Sun"]),
        assessment_api=_assessment(
            avg_mpw=42.0,
            longest=16.0,
            activities_found=20,
            baseline_band="ESTABLISHED",
            stance="COHERENT",
            typical_easy_pace_sec_per_mi=560.0,
            best_sustained_endurance_pace_sec_per_mi=530.0,
            pace_reliability="medium",
            runs_usable_pace_count=10,
            long_runs_ge_10_mi_count=4,
            weeks_with_long_run_10plus=3,
            long_run_progression_trend="flat",
        ),
    )

    assert out["readiness_level"] == LEVEL_HIGH_RISK
    assert "RULE_PERFORMANCE_LARGE_GAP_EASY_VS_GOAL_PACE" in out["reason_codes"]
    by_id = {c["category_id"]: c for c in out["category_assessments"]}
    assert by_id[CATEGORY_PERFORMANCE_ALIGNMENT]["status"] == STATUS_BAD


def test_sub3_sparse_long_run_pattern_escalates():
    """P2: durability quality — one long effort is not a pattern."""
    out = evaluate_plan_generation_readiness(
        plan_request=_plan(training_days=["Mon", "Tue", "Thu", "Sat", "Sun"]),
        assessment_api=_assessment(
            avg_mpw=42.0,
            longest=16.0,
            activities_found=12,
            baseline_band="ESTABLISHED",
            stance="COHERENT",
            typical_easy_pace_sec_per_mi=418.0,
            best_sustained_endurance_pace_sec_per_mi=402.0,
            pace_reliability="high",
            runs_usable_pace_count=14,
            long_runs_ge_10_mi_count=1,
            weeks_with_long_run_10plus=1,
            long_run_progression_trend="flat",
            lookback_weeks=8,
            active_weeks=6,
            completed_calendar_weeks_count=6,
        ),
    )
    assert out["readiness_level"] == LEVEL_HIGH_RISK
    assert "RULE_LONG_RUN_PATTERN_THIN" in out["reason_codes"]


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
    from src.coaching_intelligence.pre_generation_runner_review import (
        assessment_status_from_readiness,
    )

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
                "assessment_status": assessment_status_from_readiness(readiness),
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
    assert SCHEMA_VERSION == "plan_generation_readiness.v2.2"
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
    assert by_id[CATEGORY_PERFORMANCE_ALIGNMENT]["applies_to_goal"] is False


def test_coach_analysis_for_llm_matches_readiness_and_omits_non_applicable_categories():
    """Structured LLM payload is derived only from readiness; no effort_control when N/A."""
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
    coach = out.get("coach_analysis_for_llm")
    assert isinstance(coach, dict)
    assert coach.get("schema_version") == "coach_analysis_for_llm.v1.1"
    assert coach["recommended_actions"] == out["allowed_user_actions"]
    assert coach["key_findings"] == out["key_findings"]
    assert coach["decision"] == out["decision"]
    assert coach["readiness_level"] == out["readiness_level"]
    assert str(coach["coach_read"]).startswith("Decision:")
    assert "headline" in coach and str(coach["headline"]).strip()
    assert "main_concerns" in coach and isinstance(coach["main_concerns"], list)
    assert "recommended_path" in coach and isinstance(coach["recommended_path"], dict)
    dig = out.get("inputs_digest") or {}
    labels = {r["label"] for r in coach["facts_reviewed"]}
    if dig.get("avg_miles_per_week_approx") is not None:
        assert "Recent mileage (approx)" in labels
    summaries = coach["applicable_category_summaries"]
    assert not any("effort_control" in s for s in summaries)
    assert "Goal profile" in labels
    assert "Training schedule" in labels
    json.dumps(coach)

    disp = out.get("runner_analysis_display")
    assert isinstance(disp, dict)
    assert disp.get("schema_version") == "runner_analysis_display.v2"
    assert isinstance(disp.get("verdict"), dict)
    assert isinstance(disp.get("chips"), list)
    rs = out.get("readiness_summary") or {}
    assert rs.get("schema_version") == "readiness_summary.v1"
    assert "category_assessments" not in rs
    gd = disp.get("goal_direction")
    assert isinstance(gd, dict)
    assert gd.get("schema_version") == "goal_direction_display.v1"
    assert "RULE_" not in json.dumps(disp)
    assert isinstance(disp.get("facts"), list)


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


def _assessment_sub3_perf_durability_freq_stack(**overrides: Any) -> dict:
    """Baseline body: sub-3 time target + 3 days + large pace gap + thin long runs."""
    base: dict = {
        "avg_mpw": 42.0,
        "longest": 16.0,
        "activities_found": 20,
        "baseline_band": "ESTABLISHED",
        "stance": "COHERENT",
        "typical_easy_pace_sec_per_mi": 560.0,
        "best_sustained_endurance_pace_sec_per_mi": 530.0,
        "pace_reliability": "medium",
        "runs_usable_pace_count": 10,
        "long_runs_ge_10_mi_count": 1,
        "weeks_with_long_run_10plus": 1,
        "long_run_progression_trend": "flat",
    }
    base.update(overrides)
    return _assessment(**base)


def test_sub3_unsupported_perf_gap_orders_main_reasons_and_softens_frequency():
    """Performance → durability → frequency; frequency is never the sole concern line."""
    out = evaluate_plan_generation_readiness(
        plan_request=_plan(training_days=["Mon", "Wed", "Sat"]),
        assessment_api=_assessment_sub3_perf_durability_freq_stack(),
    )
    rc = set(out["reason_codes"])
    assert "RULE_PERFORMANCE_LARGE_GAP_EASY_VS_GOAL_PACE" in rc
    assert rc & {
        "RULE_LONG_RUN_PATTERN_THIN",
        "RULE_LONG_RUN_FREQUENCY_LOW",
    }
    assert "RULE_SUB3_THREE_DAYS_HIGH_RISK" in rc

    why = out["runner_analysis_display"]["why_concerned"]
    assert len(why) >= 3
    assert "observed paces" in why[0].lower()
    assert "durability" in why[1].lower()
    low2 = why[2].lower()
    assert "three" in low2 and "day" in low2
    assert "also" in low2
    assert "/mi/mi" not in " ".join(why)


def test_sub3_unsupported_large_perf_gap_user_actions_adjust_goal_only():
    out = evaluate_plan_generation_readiness(
        plan_request=_plan(training_days=["Mon", "Wed", "Sat"]),
        assessment_api=_assessment_sub3_perf_durability_freq_stack(),
    )
    assert out["allowed_user_actions"] == ["adjust_goal"]
    disp = out["runner_analysis_display"]
    assert disp["recommended_actions"] == ["adjust_goal"]
    assert "add_running_day" not in disp["recommended_actions"]
    gd = disp.get("goal_direction") or {}
    prim = gd.get("primary_action") or {}
    assert prim.get("id") == "adjust_goal"
    assert prim.get("label") == "Update my marathon goal"


def test_sub3_relaxed_goal_time_recomputes_readiness_for_plan_creation():
    """After easing the time target, readiness can reach allow + create_plan (re-assess)."""
    assess = _assessment_sub3_perf_durability_freq_stack()
    tight = evaluate_plan_generation_readiness(
        plan_request=_plan(
            training_days=["Mon", "Wed", "Sat"],
            target_time="3:00:00",
        ),
        assessment_api=assess,
    )
    assert tight["decision"] != DECISION_ALLOW
    assert "create_plan" not in tight["allowed_user_actions"]

    relaxed = evaluate_plan_generation_readiness(
        plan_request=_plan(
            training_days=["Mon", "Wed", "Sat"],
            target_time="3:40:00",
        ),
        assessment_api=assess,
    )
    assert relaxed["decision"] == DECISION_ALLOW
    assert relaxed["readiness_level"] == LEVEL_STRETCH
    assert RULE_MODERATE_PERFORMANCE_PACE_GAP in relaxed["reason_codes"]
    assert "create_plan" in relaxed["allowed_user_actions"]
    assert "continue_with_warning" in relaxed["allowed_user_actions"]
    by_id = {c["category_id"]: c for c in relaxed["category_assessments"]}
    pa = by_id[CATEGORY_PERFORMANCE_ALIGNMENT]
    assert pa["applies_to_goal"] is True
    assert pa["status"] == STATUS_WARN
    assert RULE_MODERATE_PERFORMANCE_PACE_GAP in pa["reason_codes"]
    fu = pa["facts_used"]
    assert fu.get("gap_easy_minus_goal_sec_per_mi") is not None
    coach = relaxed["runner_analysis_display"]["coach_read"]
    assert "developmental" in coach.lower()
    assert "supported by the current profile" not in coach.lower()
    rp_msg = str(relaxed.get("recommended_path", {}).get("message") or "")
    assert "developmental" in rp_msg.lower()
    assert "supported by the current profile" not in rp_msg.lower()


def test_completion_marathon_skips_performance_alignment_category():
    """Finish / completion profile must not judge marathon pace vs a time target."""
    out = evaluate_plan_generation_readiness(
        plan_request=_plan(
            primary_goal="Just Finish",
            target_time="",
            training_days=["Mon", "Tue", "Thu", "Sat"],
        ),
        assessment_api=_assessment(
            avg_mpw=34,
            longest=14,
            activities_found=16,
            baseline_band="ESTABLISHED",
            stance="COHERENT",
            goal_demand="FINISH",
            typical_easy_pace_sec_per_mi=600.0,
            best_sustained_endurance_pace_sec_per_mi=580.0,
            pace_reliability="high",
        ),
    )
    assert out["goal_profile"] == GOAL_PROFILE_COMPLETION
    by_id = {c["category_id"]: c for c in out["category_assessments"]}
    assert by_id[CATEGORY_PERFORMANCE_ALIGNMENT]["applies_to_goal"] is False
    assert by_id[CATEGORY_PERFORMANCE_ALIGNMENT]["status"] == STATUS_OK


def test_moderate_marathon_pace_gap_compound_stress_defers_plan_creation():
    """Two+ structural weaknesses with moderate pace gap escalates beyond allow (no create_plan)."""
    out = evaluate_plan_generation_readiness(
        plan_request=_plan(
            training_days=["Mon", "Wed", "Sat"],
            target_time="3:40:00",
        ),
        assessment_api=_assessment(
            avg_mpw=42.0,
            longest=7.0,
            activities_found=20,
            baseline_band="MODERATE",
            stance="COHERENT",
            typical_easy_pace_sec_per_mi=560.0,
            best_sustained_endurance_pace_sec_per_mi=530.0,
            pace_reliability="medium",
            runs_usable_pace_count=10,
            goal_demand="TIME_TARGET",
        ),
    )
    assert out["goal_profile"] == GOAL_PROFILE_MODERATE_PERFORMANCE
    assert RULE_MODERATE_PERFORMANCE_PACE_GAP in out["reason_codes"]
    assert out["readiness_level"] == LEVEL_HIGH_RISK
    assert out["decision"] == DECISION_DEFER
    assert "create_plan" not in out["allowed_user_actions"]
