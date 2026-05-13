"""Thin pace reliability + competitive marathon: optional STRETCH soften (env flag)."""

from __future__ import annotations

from src.coaching_intelligence.plan_generation_readiness import (
    CONFIDENCE_LOW,
    DECISION_ALLOW,
    LEVEL_READY,
    LEVEL_STRETCH,
    evaluate_plan_generation_readiness,
)
from tests.coaching_intelligence.test_plan_generation_readiness import (
    _assessment,
    _plan,
)


def test_competitive_marathon_thin_pace_default_allow_ready_low_confidence(monkeypatch):
    monkeypatch.delenv("SMARTCOACH_THIN_PACE_STRETCH_DOWNGRADE", raising=False)
    plan = _plan(
        target_time="3:25:00",
        training_days=["Mon", "Tue", "Thu", "Sat", "Sun"],
    )
    assessment = _assessment(
        avg_mpw=30.0,
        longest=14.0,
        activities_found=6,
        baseline_band="ESTABLISHED",
        stance="COHERENT",
        goal_demand="TIME_TARGET",
        pace_reliability="none",
    )
    out = evaluate_plan_generation_readiness(
        plan_request=plan,
        assessment_api=assessment,
        trace_id="thin-pace-smoke-default",
    )
    assert out["decision"] == DECISION_ALLOW
    assert out["readiness_level"] == LEVEL_READY
    assert out["confidence"] == CONFIDENCE_LOW
    assert "RULE_PERFORMANCE_PACE_DATA_THIN" in out["reason_codes"]


def test_competitive_marathon_thin_pace_flag_on_downgrades_to_stretch(monkeypatch):
    monkeypatch.setenv("SMARTCOACH_THIN_PACE_STRETCH_DOWNGRADE", "1")
    plan = _plan(
        target_time="3:25:00",
        training_days=["Mon", "Tue", "Thu", "Sat", "Sun"],
    )
    assessment = _assessment(
        avg_mpw=30.0,
        longest=14.0,
        activities_found=6,
        baseline_band="ESTABLISHED",
        stance="COHERENT",
        goal_demand="TIME_TARGET",
        pace_reliability="none",
    )
    out = evaluate_plan_generation_readiness(
        plan_request=plan,
        assessment_api=assessment,
        trace_id="thin-pace-smoke-flag",
    )
    assert out["decision"] == DECISION_ALLOW
    assert out["readiness_level"] == LEVEL_STRETCH
    assert "RULE_PERFORMANCE_PACE_DATA_THIN" in out["reason_codes"]


def test_thin_pace_flag_on_low_activity_count_no_downgrade(monkeypatch):
    monkeypatch.setenv("SMARTCOACH_THIN_PACE_STRETCH_DOWNGRADE", "1")
    plan = _plan(
        target_time="3:25:00",
        training_days=["Mon", "Tue", "Thu", "Sat", "Sun"],
    )
    assessment = _assessment(
        avg_mpw=30.0,
        longest=14.0,
        activities_found=1,
        baseline_band="ESTABLISHED",
        stance="COHERENT",
        goal_demand="TIME_TARGET",
        pace_reliability="none",
    )
    out = evaluate_plan_generation_readiness(
        plan_request=plan,
        assessment_api=assessment,
        trace_id="thin-pace-smoke-degenerate",
    )
    assert out["decision"] == DECISION_ALLOW
    assert out["readiness_level"] == LEVEL_READY
