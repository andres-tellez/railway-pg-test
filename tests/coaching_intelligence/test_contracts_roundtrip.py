"""Round-trip tests for Wave 1 coaching_intelligence contracts."""

from __future__ import annotations

from src.coaching_intelligence.contracts import (
    Deficits,
    GoalProfileModel,
    GOAL_PROFILE_SCHEMA,
    ReadinessVerdictPayload,
    RunnerEvidenceSummary,
    RUNNER_EVIDENCE_SCHEMA,
    Suggestion,
    SUGGESTION_SCHEMA,
)


def test_goal_profile_roundtrip():
    g = GoalProfileModel(
        schema_version=GOAL_PROFILE_SCHEMA,
        primary_goal="Target Time",
        race_distance="Marathon",
        target_time="3:15:00",
        profile_tag="moderate_performance",
        demand_score=0.4,
    )
    back = GoalProfileModel.from_api_dict(g.to_api_dict())
    assert back == g


def test_deficits_roundtrip_partial():
    d = Deficits(
        schema_version="deficits.v1",
        pace_deficit_sec_per_mi=12.5,
        volume_deficit_mpw=None,
    )
    assert Deficits.from_api_dict(d.to_api_dict()) == d


def test_suggestion_roundtrip():
    s = Suggestion(
        schema_version=SUGGESTION_SCHEMA,
        id="adj_goal",
        label="Soften goal",
        chip_updates={"primary_goal": "Target Time"},
        proposed_value="3:20:00",
    )
    assert Suggestion.from_api_dict(s.to_api_dict()) == s


def test_runner_evidence_summary_roundtrip():
    summary = {
        "avg_miles_per_week_approx": 22.0,
        "longest_run_miles": 12.0,
        "activities_found": 10,
    }
    wrapped = RunnerEvidenceSummary.from_activity_summary(summary)
    assert wrapped.schema_version == RUNNER_EVIDENCE_SCHEMA
    api = wrapped.to_api_dict()
    again = RunnerEvidenceSummary.from_api_dict(api)
    assert again.to_api_dict() == api


def test_readiness_verdict_payload_is_lossless_dict_wrap():
    payload = {
        "decision": "defer",
        "readiness_level": "high_risk",
        "policy_version": "policy.v1.0",
        "trace_id": "abc",
        "reason_codes": ["RULE_SUB3_THREE_DAYS_HIGH_RISK"],
    }
    rv = ReadinessVerdictPayload.from_api_dict(payload)
    assert rv.to_api_dict() == payload
