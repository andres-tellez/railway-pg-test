"""Structured agent payload coercion for plan-intake chip commits."""

from __future__ import annotations

from src.smartcoach_mobile_coach.routes import _coerce_structured_intake_updates


def test_coerce_passes_runner_tradeoff_expand():
    payload = {
        "structured_input": {
            "kind": "update_plan_intake",
            "updates": {"runner_tradeoff_choice": "expand_running_days"},
        }
    }
    assert _coerce_structured_intake_updates(payload) == {
        "runner_tradeoff_choice": "expand_running_days"
    }


def test_coerce_normalizes_tradeoff_choice_case():
    payload = {
        "structured_input": {
            "kind": "update_plan_intake",
            "updates": {"runner_tradeoff_choice": "CONTINUE_TRADEOFF"},
        }
    }
    assert _coerce_structured_intake_updates(payload) == {
        "runner_tradeoff_choice": "continue_tradeoff"
    }


def test_coerce_passes_build_base_first_tradeoff_choice():
    payload = {
        "structured_input": {
            "kind": "update_plan_intake",
            "updates": {"runner_tradeoff_choice": "build_base_first"},
        }
    }
    assert _coerce_structured_intake_updates(payload) == {
        "runner_tradeoff_choice": "build_base_first"
    }


def test_coerce_drops_unknown_tradeoff_choice():
    payload = {
        "structured_input": {
            "kind": "update_plan_intake",
            "updates": {"runner_tradeoff_choice": "hack"},
        }
    }
    assert _coerce_structured_intake_updates(payload) is None


def test_coerce_passes_plan_generation_confirmed():
    payload = {
        "structured_input": {
            "kind": "update_plan_intake",
            "updates": {"plan_generation_confirmed": True},
        }
    }
    assert _coerce_structured_intake_updates(payload) == {
        "plan_generation_confirmed": True
    }


def test_coerce_combines_tradeoff_and_schedule():
    payload = {
        "structured_input": {
            "kind": "update_plan_intake",
            "updates": {
                "runner_tradeoff_choice": "expand_running_days",
                "schedule_days_confirmed": True,
            },
        }
    }
    out = _coerce_structured_intake_updates(payload)
    assert out == {
        "runner_tradeoff_choice": "expand_running_days",
        "schedule_days_confirmed": True,
    }


def test_coerce_passes_apply_coach_suggested_goal_with_core_fields(monkeypatch):
    """Mobile runner-analysis CTA sends this bundle; API must forward all keys."""
    payload = {
        "structured_input": {
            "kind": "update_plan_intake",
            "updates": {
                "primary_goal": "Target Time",
                "target_time": "3:40:00",
                "apply_coach_suggested_goal": True,
            },
        }
    }
    out = _coerce_structured_intake_updates(payload)
    assert out == {
        "primary_goal": "Target Time",
        "target_time": "3:40:00",
        "apply_coach_suggested_goal": True,
    }
