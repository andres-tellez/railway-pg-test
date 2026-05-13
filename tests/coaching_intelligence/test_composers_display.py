"""Snapshot-style regression for ``build_runner_analysis_display`` (Phase 5)."""

from __future__ import annotations

from datetime import date

import pytest

from src.coaching_intelligence.composers.display import build_runner_analysis_display
from src.coaching_intelligence.plan_generation_readiness import (
    evaluate_plan_generation_readiness,
)
from src.coaching_intelligence.policy.policy_table import POLICY_VERSION
from tests.coaching_intelligence.ambition_gap_fixtures import (
    synthetic_ambition_attributions,
)


class _FixedDate(date):
    """Pinned ``date.today()`` for stable ``weeks_to_race`` in readiness digest."""

    @classmethod
    def today(cls):
        return date(2026, 5, 12)


@pytest.fixture
def fixed_today(monkeypatch):
    monkeypatch.setattr(
        "src.coaching_intelligence.plan_generation_readiness.date",
        _FixedDate,
    )


def test_build_runner_analysis_display_snapshot_just_finish(
    fixed_today,
):  # noqa: ARG001
    plan = {
        "race_distance": "Marathon",
        "race_date": "2030-06-01",
        "primary_goal": "Just Finish",
        "training_days": ["Mon", "Wed", "Fri"],
    }
    assessment = {
        "activity_summary": {
            "avg_miles_per_week_approx": 28.0,
            "longest_run_miles": 10.0,
            "activities_found": 8,
            "lookback_weeks": 6,
            "completed_calendar_weeks_count": 4,
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
        "intake_alignment_state": {"generation_ready": True, "unresolved_flags": []},
    }
    readiness = evaluate_plan_generation_readiness(
        plan_request=plan,
        assessment_api=assessment,
        trace_id="composers-display-snapshot",
    )
    got = build_runner_analysis_display(readiness)
    expected = {
        "chips": [
            {"id": "create_plan", "label": "Update your plan inputs"},
        ],
        "coach_read": (
            "Based on what we can see, you\u2019re **reasonable to plan forward** for this marathon "
            "(June 2030). (Finish-the-race focus)"
        ),
        "coach_summary": {
            "body": (
                "Based on what we can see, you\u2019re **reasonable to plan forward** for this marathon "
                "(June 2030). (Finish-the-race focus)"
            ),
            "headline": "Reasonable to plan forward.",
            "reasons": [],
            "schema_version": "runner_analysis_summary.v1",
        },
        "deficits": {"schema_version": "deficits.v1"},
        "facts": [
            {"summary": "Marathon \u2014 Just Finish", "title": "Goal"},
            {
                "summary": "3 running days per week (Mon, Wed, Fri)",
                "title": "Training rhythm",
            },
            {
                "summary": "~28.0 mi/week (recent snapshot)",
                "title": "Recent weekly volume",
            },
            {"summary": "~10.0 mi", "title": "Longest recent run"},
            {"summary": "211.6 week(s) to race", "title": "Timeline"},
            {
                "summary": "8 logged runs in the lookback we used",
                "title": "Recent logs",
            },
        ],
        "goal_direction": {
            "direction_id": "strong_completion_focus",
            "framing": (
                "For **June 2030**, the coaching recommendation for this block is a **healthy, "
                "finish-line plan** \u2014 fitness that shows up on the day, not a numbers chase. Your goal "
                "reads as **completion-first**, and that\u2019s a respectable way to run a first or return marathon."
            ),
            "headline": "Strong completion-focused cycle",
            "next_steps": [
                "Use the plan to **build durability** you can repeat, not spikes you survive.",
                "Keep the emphasis on **steady weeks** and a long run you can recover from.",
                "When you change your goal here, the next coach reply re-runs this read automatically \u2014 "
                "same inputs, fresh snapshot.",
            ],
            "primary_action": {"id": "create_plan", "label": "Create my plan"},
            "schema_version": "goal_direction_display.v1",
        },
        "recommended_actions": ["create_plan"],
        "recommended_path": {
            "lead": "The requested plan is supported by the current profile."
        },
        "schema_version": "runner_analysis_display.v2",
        "policy_version": POLICY_VERSION,
        "trace_id": "composers-display-snapshot",
        "suggestions": [
            {
                "chip_updates": {"action": "create_plan"},
                "id": "create_plan",
                "label": "Update your plan inputs",
                "schema_version": "suggestion.v1",
            },
        ],
        "verdict": {
            "narrative": (
                "Based on what we can see, you\u2019re **reasonable to plan forward** for this marathon "
                "(June 2030). (Finish-the-race focus)"
            ),
        },
        "why_concerned": [],
    }
    assert got == expected
