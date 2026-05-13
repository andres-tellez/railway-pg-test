"""Readiness payload observability (policy_version, trace_id) — Wave 1."""

from __future__ import annotations

from src.coaching_intelligence.plan_generation_readiness import (
    evaluate_plan_generation_readiness,
)
from src.coaching_intelligence.policy.policy_table import POLICY_VERSION
from tests.coaching_intelligence.ambition_gap_fixtures import (
    synthetic_ambition_attributions,
)


def _minimal_plan():
    return {
        "race_distance": "Marathon",
        "race_date": "2099-12-01",
        "primary_goal": "Target Time",
        "target_time": "4:00:00",
        "training_days": ["Mon", "Wed", "Fri", "Sun"],
    }


def _minimal_assessment():
    return {
        "schema_version": "pre_generation_runner_assessment.v1",
        "activity_summary": {
            "avg_miles_per_week_approx": 35.0,
            "longest_run_miles": 14.0,
            "activities_found": 12,
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
                longest_run_miles=14.0,
            ),
        },
        "intake_alignment_state": {"generation_ready": True, "unresolved_flags": []},
    }


def test_readiness_payload_includes_policy_version():
    out = evaluate_plan_generation_readiness(
        plan_request=_minimal_plan(),
        assessment_api=_minimal_assessment(),
    )
    assert out.get("policy_version") == POLICY_VERSION


def test_readiness_payload_echoes_trace_id_when_provided():
    out = evaluate_plan_generation_readiness(
        plan_request=_minimal_plan(),
        assessment_api=_minimal_assessment(),
        trace_id="gate-test-trace",
    )
    assert out.get("trace_id") == "gate-test-trace"
    assert out.get("policy_version") == POLICY_VERSION


def test_readiness_payload_omits_trace_id_when_not_provided():
    out = evaluate_plan_generation_readiness(
        plan_request=_minimal_plan(),
        assessment_api=_minimal_assessment(),
    )
    assert "trace_id" not in out


def test_readiness_payload_echoes_evidence_snapshot_id_from_assessment():
    asm = _minimal_assessment()
    asm["evidence_snapshot_id"] = "ev-abc-001"
    out = evaluate_plan_generation_readiness(
        plan_request=_minimal_plan(),
        assessment_api=asm,
    )
    assert out.get("evidence_snapshot_id") == "ev-abc-001"


def test_readiness_payload_prefers_explicit_evidence_snapshot_id_param():
    asm = _minimal_assessment()
    asm["evidence_snapshot_id"] = "from-assessment"
    out = evaluate_plan_generation_readiness(
        plan_request=_minimal_plan(),
        assessment_api=asm,
        evidence_snapshot_id="from-param",
    )
    assert out.get("evidence_snapshot_id") == "from-param"
