"""Contract: coach_analysis_for_llm shapes expected by Runner Analysis UI."""

from __future__ import annotations

import json

from src.coaching_intelligence.plan_generation_readiness import (
    ACTION_ADD_RUNNING_DAY,
    CATEGORY_EFFORT_CONTROL,
    DECISION_DEFER,
    evaluate_plan_generation_readiness,
)


def _race_date(weeks: int = 24) -> str:
    from datetime import date, timedelta

    return (date.today() + timedelta(weeks=weeks)).isoformat()


def test_sub3_three_days_coach_payload_lists_facts_and_concerns_not_effort_control():
    plan_request = {
        "race_distance": "Marathon",
        "race_date": _race_date(),
        "primary_goal": "Target Time",
        "target_time": "3:00:00",
        "training_days": ["Mon", "Wed", "Sat"],
    }
    assessment_api = {
        "schema_version": "pre_generation_runner_assessment.v1",
        "activity_summary": {
            "avg_miles_per_week_approx": 24.0,
            "longest_run_miles": 12.0,
            "activities_found": 8,
            "lookback_weeks": 6,
            "active_weeks": 4,
            "completed_calendar_weeks_count": 4,
        },
        "ambition_gap": {
            "stance": "COHERENT",
            "baseline_band": "MODERATE",
            "goal_demand": "TIME_TARGET",
        },
        "intake_alignment_state": {"generation_ready": True, "unresolved_flags": []},
    }
    out = evaluate_plan_generation_readiness(
        plan_request=plan_request, assessment_api=assessment_api
    )
    assert out["decision"] == DECISION_DEFER
    coach = out["coach_analysis_for_llm"]
    assert coach["schema_version"].startswith("coach_analysis_for_llm.v1")
    labels = {r["label"] for r in coach["facts_reviewed"]}
    assert "Goal" in labels
    assert "Training schedule" in labels
    assert "Recent mileage (approx)" in labels
    assert "Data confidence (coverage)" in labels
    mc = " ".join(coach["main_concerns"])
    assert "effort control" not in mc.lower()
    assert ACTION_ADD_RUNNING_DAY in coach["recommended_actions"]
    by_id = {c["category_id"]: c for c in out["category_assessments"]}
    assert by_id[CATEGORY_EFFORT_CONTROL]["applies_to_goal"] is False
    json.dumps(coach)
