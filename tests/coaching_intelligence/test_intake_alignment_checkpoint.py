from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from src.coaching_intelligence.contracts.runner_evidence import RunnerEvidenceSummary
from src.coaching_intelligence import pre_generation_runner_assessment as pgra
from src.smartcoach_mobile_coach import agent_tools


def _stub_evidence(**fields):
    merged = {
        "lookback_weeks": 6,
        "activities_found": int(fields.get("activities_found") or 0),
        "has_running_data": int(fields.get("activities_found") or 0) > 0,
        "total_miles_window": 0.0,
        "avg_miles_per_week_raw_window": 0.0,
        "weekly_mileage_history": [],
        "consistency_weeks_active_in_history": 0,
        "history_lookback_weeks": 12,
        **fields,
    }
    return RunnerEvidenceSummary.from_activity_summary(merged)


def _state() -> dict:
    return {
        "draft": {
            "race_distance": "Marathon",
            "race_date": "2026-10-12",
            "primary_goal": "Target Time",
            "target_time": "3:00:00",
            "training_days": ["Tue", "Thu", "Sat"],
        },
        "ux": {
            "intake_confirmed": True,
            "runner_review_delivered": True,
            "plan_generation_confirmed": True,
            "runner_review_assessment_status": "ready_to_generate",
        },
    }


def test_generate_plan_pauses_for_high_tension_when_alignment_enabled(monkeypatch):
    monkeypatch.setenv("SMARTCOACH_ENABLE_INTAKE_ALIGNMENT_V1", "true")
    monkeypatch.setattr(
        agent_tools,
        "build_plan_request_from_state",
        lambda _s: _s["draft"],
    )
    monkeypatch.setattr(
        pgra,
        "build_runner_evidence",
        lambda *_a, **_k: _stub_evidence(
            avg_miles_per_week_approx=10.0,
            longest_run_miles=8.0,
            activities_found=8,
        ),
    )
    monkeypatch.setattr(
        pgra,
        "evaluate_ambition_gap",
        lambda **_kwargs: {
            "stance": "HIGH_TENSION",
            "goal_demand": "TIME_TARGET",
            "baseline_band": "THIN",
            "attributions": ["STANCE_HIGH_TENSION_TIME_VS_THIN_BASELINE"],
        },
    )
    run_mock = MagicMock()
    monkeypatch.setattr(agent_tools, "run_v2_plan_generation", run_mock)

    out = agent_tools.tool_generate_training_plan(
        session=MagicMock(),
        internal_user_id="u-1",
        args={"confirm": True},
        current_state=_state(),
    )

    assert out["error"] == "plan_generation_readiness_deferred"
    assert out["pre_generation_runner_assessment"]["schema_version"].endswith(".v1")
    assert (
        out["pre_generation_runner_assessment"]["ambition_gap"]["stance"]
        == "HIGH_TENSION"
    )
    assert out["plan_generation_readiness"]["decision"] == "defer"
    assert "create_plan" not in out["plan_generation_readiness"]["allowed_user_actions"]
    assert run_mock.called is False


def test_generate_plan_coherent_path_still_invokes_planner(monkeypatch):
    monkeypatch.setenv("SMARTCOACH_ENABLE_INTAKE_ALIGNMENT_V1", "true")
    monkeypatch.setattr(
        agent_tools,
        "build_plan_request_from_state",
        lambda _s: _s["draft"],
    )
    monkeypatch.setattr(
        pgra,
        "build_runner_evidence",
        lambda *_a, **_k: _stub_evidence(
            avg_miles_per_week_approx=40.0,
            longest_run_miles=16.0,
            activities_found=16,
            # Sub-3 competitive profile + missing pattern fields used to trigger
            # RULE_PERFORMANCE_PACE_DATA_THIN / RULE_LONG_RUN_PATTERN_THIN and
            # escalate stretch → high_risk (readiness defer) before the planner runs.
            pace_reliability="high",
            typical_easy_pace_sec_per_mi=480.0,
            best_sustained_endurance_pace_sec_per_mi=430.0,
            long_runs_ge_10_mi_count=4,
            weeks_with_long_run_10plus=3,
        ),
    )
    monkeypatch.setattr(
        pgra,
        "evaluate_ambition_gap",
        lambda **_kwargs: {
            "stance": "COHERENT",
            "goal_demand": "TIME_TARGET",
            "baseline_band": "ESTABLISHED",
            "attributions": ["STANCE_COHERENT_TIME_VS_ESTABLISHED_BASELINE"],
        },
    )

    def _raise_after_reaching_planner(**_kwargs):
        raise RuntimeError("planner-called")

    monkeypatch.setattr(
        agent_tools, "run_v2_plan_generation", _raise_after_reaching_planner
    )

    state = _state()
    state["draft"]["training_days"] = ["Mon", "Tue", "Thu", "Sat", "Sun"]

    out = agent_tools.tool_generate_training_plan(
        session=MagicMock(),
        internal_user_id="u-1",
        args={"confirm": True},
        current_state=state,
    )

    assert out["error"] == "plan_generation_failed"


def test_feature_flag_off_preserves_legacy_generation_path(monkeypatch):
    monkeypatch.delenv("SMARTCOACH_ENABLE_INTAKE_ALIGNMENT_V1", raising=False)
    monkeypatch.setattr(
        agent_tools,
        "build_plan_request_from_state",
        lambda _s: _s["draft"],
    )
    monkeypatch.setattr(
        pgra,
        "build_runner_evidence",
        lambda *_a, **_k: _stub_evidence(
            avg_miles_per_week_approx=30.0,
            longest_run_miles=10.0,
            activities_found=10,
        ),
    )

    def _ambition_gap_must_not_run(**_kwargs):
        raise AssertionError("alignment evaluator should not run when feature is off")

    monkeypatch.setattr(pgra, "evaluate_ambition_gap", _ambition_gap_must_not_run)

    def _alignment_state_must_not_run(**_kwargs):
        raise AssertionError("alignment state should not run when feature is off")

    monkeypatch.setattr(
        pgra, "evaluate_intake_alignment_state", _alignment_state_must_not_run
    )

    def _raise_after_reaching_planner(**_kwargs):
        raise RuntimeError("planner-called")

    monkeypatch.setattr(
        agent_tools, "run_v2_plan_generation", _raise_after_reaching_planner
    )

    state = _state()
    state["draft"]["primary_goal"] = "Just Finish"
    state["draft"]["target_time"] = ""
    state["draft"]["training_days"] = ["Tue", "Thu", "Sat", "Sun"]

    out = agent_tools.tool_generate_training_plan(
        session=MagicMock(),
        internal_user_id="u-1",
        args={"confirm": True},
        current_state=state,
    )

    assert out["error"] == "plan_generation_failed"


def test_high_tension_resolved_still_obeys_readiness_gate(monkeypatch):
    monkeypatch.setenv("SMARTCOACH_ENABLE_INTAKE_ALIGNMENT_V1", "true")
    monkeypatch.setattr(
        agent_tools,
        "build_plan_request_from_state",
        lambda _s: _s["draft"],
    )
    monkeypatch.setattr(
        pgra,
        "build_runner_evidence",
        lambda *_a, **_k: _stub_evidence(
            avg_miles_per_week_approx=10.0,
            longest_run_miles=8.0,
            activities_found=8,
        ),
    )
    monkeypatch.setattr(
        pgra,
        "evaluate_ambition_gap",
        lambda **_kwargs: {
            "stance": "HIGH_TENSION",
            "goal_demand": "TIME_TARGET",
            "baseline_band": "THIN",
            "attributions": ["STANCE_HIGH_TENSION_TIME_VS_THIN_BASELINE"],
        },
    )

    state = _state()
    state["alignment"] = {
        "answers": {
            "frequency_flexible": True,
            "posture_priority": "BALANCED",
        },
        "asked_categories": ["frequency_flexibility"],
        "question_count": 2,
    }

    def _raise_after_reaching_planner(**_kwargs):
        raise RuntimeError("planner-called")

    monkeypatch.setattr(
        agent_tools, "run_v2_plan_generation", _raise_after_reaching_planner
    )

    out = agent_tools.tool_generate_training_plan(
        session=MagicMock(),
        internal_user_id="u-1",
        args={"confirm": True},
        current_state=state,
    )

    assert out["error"] == "plan_generation_readiness_deferred"
    assert out["plan_generation_readiness"]["readiness_level"] in (
        "currently_unrealistic",
        "high_risk",
    )


def test_pre_generation_assessment_failure_is_structured_and_skips_planner(monkeypatch):
    monkeypatch.setattr(
        agent_tools,
        "build_plan_request_from_state",
        lambda _s: _s["draft"],
    )

    def _gate_raises(**_kwargs):
        raise RuntimeError("simulated activity summary failure")

    monkeypatch.setattr(
        agent_tools,
        "get_or_compute_readiness_gate",
        _gate_raises,
    )
    run_mock = MagicMock()
    monkeypatch.setattr(agent_tools, "run_v2_plan_generation", run_mock)

    out = agent_tools.tool_generate_training_plan(
        session=MagicMock(),
        internal_user_id="u-1",
        args={"confirm": True},
        current_state=_state(),
    )

    assert out["error"] == "pre_generation_runner_assessment_failed"
    assert out["tool"] == "generate_training_plan"
    assert "activity summary" in out["message"].lower()
    assert out["failure"]["stage"] == "pre_generation_runner_assessment"
    assert out["failure"]["exception_type"] == "RuntimeError"
    assert "simulated activity summary failure" in out["failure"]["detail"]
    assert out.get("error") != "tool_execution_failed"
    assert run_mock.called is False


def test_generate_plan_uses_shared_readiness_gate_helper(monkeypatch):
    monkeypatch.setattr(
        agent_tools,
        "build_plan_request_from_state",
        lambda _s: _s["draft"],
    )

    gate_calls = {"count": 0}

    def _gate(
        *, session, internal_user_id, plan_request, plan_intake_state, alignment_enabled
    ):
        gate_calls["count"] += 1
        assert internal_user_id == "u-1"
        assert isinstance(plan_request, dict)
        return SimpleNamespace(
            assessment_api={"schema_version": "pre_generation_runner_assessment.v1"},
            readiness_api={
                "trace_id": "tr-shared",
                "policy_version": "policy.v1.0",
                "decision": "defer",
                "readiness_level": "high_risk",
                "reason_codes": ["RULE_SAMPLE"],
                "evidence_snapshot_id": "ev-shared",
            },
            plan_request_digest_sha256="digest-shared",
            cache_status="hit",
        )

    monkeypatch.setattr(agent_tools, "get_or_compute_readiness_gate", _gate)
    run_mock = MagicMock()
    monkeypatch.setattr(agent_tools, "run_v2_plan_generation", run_mock)

    out = agent_tools.tool_generate_training_plan(
        session=MagicMock(),
        internal_user_id="u-1",
        args={"confirm": True},
        current_state=_state(),
    )

    assert gate_calls["count"] == 1
    assert out["error"] == "plan_generation_readiness_deferred"
    assert out["plan_generation_readiness"]["trace_id"] == "tr-shared"
    assert out["plan_generation_readiness"]["evidence_snapshot_id"] == "ev-shared"
    assert run_mock.called is False


def test_execute_tool_returns_assessment_error_not_tool_execution_failed(monkeypatch):
    monkeypatch.setattr(
        agent_tools,
        "build_plan_request_from_state",
        lambda _s: _s["draft"],
    )

    def _gate_raises(**_kwargs):
        raise ValueError("database unavailable")

    monkeypatch.setattr(
        agent_tools,
        "get_or_compute_readiness_gate",
        _gate_raises,
    )

    out = agent_tools.execute_tool(
        MagicMock(),
        "11111111-1111-1111-1111-111111111111",
        "generate_training_plan",
        '{"confirm": true}',
        plan_intake_state=_state(),
    )

    assert out["error"] == "pre_generation_runner_assessment_failed"
    assert out["error"] != "tool_execution_failed"
    assert out["failure"]["exception_type"] == "ValueError"
