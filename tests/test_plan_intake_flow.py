from __future__ import annotations

from src.smartcoach_mobile_coach.plan_intake_flow import (
    build_plan_request_from_state,
    update_plan_intake_state,
)


def test_plan_intake_updates_to_ready_state():
    state = update_plan_intake_state(
        None,
        updates={
            "race_date": "2026-10-12",
            "race_distance": "Marathon",
            "primary_goal": "Just Finish",
            "training_days": ["Tue", "Thu", "Sat"],
        },
    )
    assert state["ready_to_generate"] is True
    assert state["status"] == "ready_to_confirm"
    assert state["draft"]["long_run_day"] == "Sat"
    assert state["missing_required"] == []


def test_plan_intake_rejects_bad_training_days():
    state = update_plan_intake_state(
        None,
        updates={
            "training_days": ["Tue", "Funday"],
        },
    )
    assert state["ready_to_generate"] is False
    assert any("training_days" in e for e in state["errors"])


def test_plan_intake_target_time_required_for_target_goal():
    state = update_plan_intake_state(
        None,
        updates={
            "race_date": "2026-10-12",
            "race_distance": "Marathon",
            "primary_goal": "Target Time",
            "training_days": "Tue,Thu,Sat",
        },
    )
    assert "target_time" in state["missing_required"]
    assert state["ready_to_generate"] is False


def test_build_plan_request_from_state_validates_schema():
    state = update_plan_intake_state(
        None,
        updates={
            "race_date": "2026-10-12",
            "race_distance": "Marathon",
            "primary_goal": "Just Finish",
            "training_days": ["Tue", "Thu", "Sat"],
            "long_run_day": "Sat",
            "notes": "Returning from injury, build conservatively.",
        },
    )
    req = build_plan_request_from_state(state)
    assert req["race_distance"] == "Marathon"
    assert req["long_run_day"] == "Sat"
    assert req["training_days"] == ["Tue", "Thu", "Sat"]
