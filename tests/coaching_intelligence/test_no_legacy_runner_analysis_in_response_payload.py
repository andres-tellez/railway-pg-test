"""Phase 8.3 — ``plan_generation_readiness`` wire shape for clients (no LLM-only blobs)."""

from __future__ import annotations

from datetime import date

import pytest

from src.coaching_intelligence.composers.llm_payload import build_coach_analysis_for_llm
from src.coaching_intelligence.plan_generation_readiness import (
    evaluate_plan_generation_readiness,
)
from src.coaching_intelligence.policy.policy_table import POLICY_VERSION
from tests.coaching_intelligence.ambition_gap_fixtures import (
    synthetic_ambition_attributions,
)


class _FixedDate(date):
    @classmethod
    def today(cls):
        return date(2026, 5, 12)


@pytest.fixture
def fixed_today(monkeypatch):
    monkeypatch.setattr(
        "src.coaching_intelligence.plan_generation_readiness.date",
        _FixedDate,
    )


def test_no_legacy_runner_analysis_in_response_payload(fixed_today):  # noqa: ARG001
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
        trace_id="trace-phase83-test",
    )

    assert "coach_analysis_for_llm" not in readiness
    assert "runner_analysis_display_v2" not in readiness

    disp = readiness.get("runner_analysis_display")
    assert isinstance(disp, dict)
    assert disp.get("schema_version") == "runner_analysis_display.v2"
    for key in (
        "verdict",
        "chips",
        "coach_read",
        "facts",
        "goal_direction",
        "deficits",
        "suggestions",
        "policy_version",
        "trace_id",
    ):
        assert key in disp

    assert disp.get("policy_version") == POLICY_VERSION
    assert disp.get("trace_id") == "trace-phase83-test"

    coach = build_coach_analysis_for_llm(readiness)
    assert coach.get("schema_version") == "coach_analysis_for_llm.v1.1"
    assert "facts_reviewed" in coach
