from __future__ import annotations

from src.smartcoach_mobile_coach.agent_tools import (
    _build_plan_generation_brief,
    _plan_baseline_from_validation,
    _plan_overview_from_validation,
)


def test_plan_overview_extracts_phases_and_peaks():
    validation_result = {
        "validated_plan": {
            "start_date": "2026-06-08",
            "weeks": [
                {
                    "week_number": 1,
                    "phase": "Base",
                    "weekly_mileage": 28,
                    "long_run_miles": 10,
                },
                {
                    "week_number": 2,
                    "phase": "Build",
                    "weekly_mileage": 32.4,
                    "long_run_miles": 12,
                },
                {
                    "week_number": 3,
                    "phase": "Build",
                    "weekly_mileage": 35.2,
                    "long_run_miles": 14,
                },
                {
                    "week_number": 4,
                    "phase": "Peak",
                    "weekly_mileage": 40,
                    "long_run_miles": 18,
                },
            ],
        }
    }
    plan_request = {
        "training_days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
        "long_run_day": "Sat",
    }
    saved = {
        "race_date": "2026-10-11",
        "race_distance": "Marathon",
        "workouts": [],
    }

    out = _plan_overview_from_validation(validation_result, plan_request, saved)

    assert out["plan_start_date"] == "2026-06-08"
    assert out["total_weeks"] == 4
    assert out["phase_sequence"] == ["Base", "Build", "Peak"]
    assert out["phase_blocks"] == [
        {
            "phase": "Base",
            "start_week": 1,
            "end_week": 1,
            "peak_weekly_miles": 28.0,
        },
        {
            "phase": "Build",
            "start_week": 2,
            "end_week": 3,
            "peak_weekly_miles": 35.2,
        },
        {
            "phase": "Peak",
            "start_week": 4,
            "end_week": 4,
            "peak_weekly_miles": 40.0,
        },
    ]
    assert out["peak_weekly_miles"] == 40.0
    assert out["peak_long_run_miles"] == 18.0
    assert out["training_days"] == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    assert out["long_run_day"] == "Sat"


def test_plan_baseline_uses_pass1_rationale():
    validation_result = {
        "pass1_rationale": {
            "base_mpw": 24.36,
            "longest_recent": 9.84,
            "start_lr": 10.0,
            "recommended_weeks": 18,
        }
    }
    out = _plan_baseline_from_validation(validation_result, activity_weeks=12)

    assert out["source"] == "materialized_view"
    assert out["lookback_weeks_requested"] == 12
    assert out["avg_weekly_miles"] == 24.4
    assert out["longest_recent_run_miles"] == 9.8
    assert out["starting_long_run_miles"] == 10.0
    assert out["recommended_weeks"] == 18


def test_plan_generation_brief_includes_preview_and_plan_tab_handoff():
    payload = {
        "overview": {
            "plan_start_date": "2026-06-08",
            "total_weeks": 18,
            "phase_sequence": ["Base", "Build", "Peak", "Taper"],
            "phase_blocks": [
                {
                    "phase": "Base",
                    "start_week": 1,
                    "end_week": 6,
                    "peak_weekly_miles": 32.0,
                },
                {
                    "phase": "Build",
                    "start_week": 7,
                    "end_week": 13,
                    "peak_weekly_miles": 40.5,
                },
            ],
            "peak_long_run_miles": 20.0,
        },
        "baseline": {
            "lookback_weeks_requested": 12,
            "avg_weekly_miles": 22.5,
            "longest_recent_run_miles": 10.2,
        },
        "this_week": {
            "workouts": [
                {"date": "2026-06-08", "workout_type": "easy", "miles": 4},
                {"date": "2026-06-10", "workout_type": "tempo", "miles": 6},
            ]
        },
    }
    out = _build_plan_generation_brief("Marathon", "2026-10-11", payload)

    assert "Your Marathon plan is saved for 2026-10-11." in out
    assert "**Week 1 starts:** Mon., June 8th" in out
    assert "from the last **12** weeks" in out
    assert "- **Weekly miles:** 22.5 mi/week" in out
    assert "- **Longest run:** 10.2 mi" in out
    assert "**Plan overview**" in out
    assert "| Phase | Weeks |" in out
    assert "| Base | 6 |" in out
    assert "| Build | 7 |" in out
    assert "- **Peak long run (plan):** 20.0 mi" in out
    assert "| Day | Run Type | Miles |" in out
    assert "| Mon | Easy | 4.0 |" in out
    assert "| Wed | Tempo | 6.0 |" in out
    assert "**View your Plan:** click on Plan " in out
    assert "**Questions** - Any questions?" in out
