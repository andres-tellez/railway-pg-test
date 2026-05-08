from __future__ import annotations

from unittest.mock import MagicMock

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
        agent_tools,
        "compute_plan_intake_activity_summary",
        lambda **_kwargs: {"avg_miles_per_week_approx": 10.0, "longest_run_miles": 8.0},
    )
    monkeypatch.setattr(
        agent_tools,
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
        "posture_priority",
    ]
    assert run_mock.called is False


def test_generate_plan_coherent_path_still_invokes_planner(monkeypatch):
    monkeypatch.setenv("SMARTCOACH_ENABLE_INTAKE_ALIGNMENT_V1", "true")
    monkeypatch.setattr(
        agent_tools,
        "build_plan_request_from_state",
        lambda _s: _s["draft"],
    )
    monkeypatch.setattr(
        agent_tools,
        "compute_plan_intake_activity_summary",
        lambda **_kwargs: {
            "avg_miles_per_week_approx": 40.0,
            "longest_run_miles": 16.0,
        },
    )
    monkeypatch.setattr(
        agent_tools,
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
