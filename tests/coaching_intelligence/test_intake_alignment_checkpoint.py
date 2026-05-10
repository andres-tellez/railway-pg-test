from __future__ import annotations

from unittest.mock import MagicMock

from src.coaching_intelligence import pre_generation_runner_assessment as pgra
from src.smartcoach_mobile_coach import agent_tools


def _state() -> dict:
    return {
        "draft": {
            "race_distance": "Marathon",
            "race_date": "2026-10-12",
            "primary_goal": "Target Time",
            "target_time": "3:00:00",
            "training_days": ["Tue", "Thu", "Sat"],
        }
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
        "compute_plan_intake_activity_summary",
        lambda **_kwargs: {"avg_miles_per_week_approx": 10.0, "longest_run_miles": 8.0},
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

    assert out["error"] == "alignment_required"
    assert out["alignment_brief"]["allowed_question_categories"] == [
        "frequency_flexibility",
    ]
    assert out["pre_generation_runner_assessment"]["schema_version"].endswith(".v1")
    assert (
        out["pre_generation_runner_assessment"]["ambition_gap"]["stance"]
        == "HIGH_TENSION"
    )
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
        "compute_plan_intake_activity_summary",
        lambda **_kwargs: {
            "avg_miles_per_week_approx": 40.0,
            "longest_run_miles": 16.0,
        },
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

    out = agent_tools.tool_generate_training_plan(
        session=MagicMock(),
        internal_user_id="u-1",
        args={"confirm": True},
        current_state=_state(),
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
        "compute_plan_intake_activity_summary",
        lambda **_kwargs: {
            "avg_miles_per_week_approx": 30.0,
            "longest_run_miles": 10.0,
        },
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

    out = agent_tools.tool_generate_training_plan(
        session=MagicMock(),
        internal_user_id="u-1",
        args={"confirm": True},
        current_state=_state(),
    )

    assert out["error"] == "plan_generation_failed"


def test_high_tension_resolved_still_uses_same_planner_path(monkeypatch):
    monkeypatch.setenv("SMARTCOACH_ENABLE_INTAKE_ALIGNMENT_V1", "true")
    monkeypatch.setattr(
        agent_tools,
        "build_plan_request_from_state",
        lambda _s: _s["draft"],
    )
    monkeypatch.setattr(
        pgra,
        "compute_plan_intake_activity_summary",
        lambda **_kwargs: {"avg_miles_per_week_approx": 10.0, "longest_run_miles": 8.0},
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

    assert out["error"] == "plan_generation_failed"


def test_pre_generation_assessment_failure_is_structured_and_skips_planner(monkeypatch):
    monkeypatch.setattr(
        agent_tools,
        "build_plan_request_from_state",
        lambda _s: _s["draft"],
    )

    def _assessment_raises(*_args, **_kwargs):
        raise RuntimeError("simulated activity summary failure")

    monkeypatch.setattr(
        agent_tools,
        "build_pre_generation_runner_assessment",
        _assessment_raises,
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


def test_execute_tool_returns_assessment_error_not_tool_execution_failed(monkeypatch):
    monkeypatch.setattr(
        agent_tools,
        "build_plan_request_from_state",
        lambda _s: _s["draft"],
    )

    def _assessment_raises(*_args, **_kwargs):
        raise ValueError("database unavailable")

    monkeypatch.setattr(
        agent_tools,
        "build_pre_generation_runner_assessment",
        _assessment_raises,
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
