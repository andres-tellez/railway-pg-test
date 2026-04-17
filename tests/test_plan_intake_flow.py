from __future__ import annotations

from src.smartcoach_mobile_coach.plan_intake_flow import (
    build_plan_request_from_state,
    update_plan_intake_state,
    user_confirms_plan_intake,
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


def test_plan_intake_accepts_natural_language_race_date():
    state = update_plan_intake_state(
        None,
        updates={
            "race_date": "October 11 of 2026",
            "race_distance": "Marathon",
            "primary_goal": "Just Finish",
            "training_days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
        },
    )
    assert state["draft"]["race_date"] == "2026-10-11"
    assert state["ready_to_generate"] is True


def test_plan_intake_target_time_from_spoken_duration():
    state = update_plan_intake_state(
        None,
        updates={
            "race_date": "2026-10-12",
            "race_distance": "Marathon",
            "primary_goal": "Target Time",
            "target_time": "3 hours 40 minutes",
            "training_days": ["Tue", "Thu", "Sat"],
        },
    )
    assert state["draft"]["target_time"] == "3:40:00"
    assert state["ready_to_generate"] is True


def test_user_confirms_plan_intake_short_affirmations():
    assert user_confirms_plan_intake("Y") is True
    assert user_confirms_plan_intake("y.") is True
    assert user_confirms_plan_intake("yes") is True
    assert user_confirms_plan_intake("Looks good!") is True
    assert user_confirms_plan_intake("yes but change the date") is False
    assert user_confirms_plan_intake("no thanks") is False
