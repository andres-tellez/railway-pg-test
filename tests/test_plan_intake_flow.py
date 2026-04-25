from __future__ import annotations

from src.smartcoach_mobile_coach.plan_intake_flow import (
    PLAN_UX_STAGE_CONFIRM,
    PLAN_UX_STAGE_FAST_TRACK,
    PLAN_UX_STAGE_GOAL_ALIGNMENT,
    mark_plan_runner_understanding_shown,
    plan_runner_understanding_shown,
    build_plan_request_from_state,
    update_plan_intake_state,
    user_confirms_plan_intake,
)


def test_plan_intake_missing_required_order_for_empty_draft():
    state = update_plan_intake_state(None)
    assert state["missing_required"] == [
        "race_distance",
        "race_date",
        "primary_goal",
        "training_days",
    ]
    assert state["ux"]["stage"] == "understand_runner"


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
    assert state["ux"]["stage"] == PLAN_UX_STAGE_FAST_TRACK


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
    assert state["ux"]["stage"] == "details"


def test_plan_intake_ux_stage_goal_alignment_after_distance_only():
    state = update_plan_intake_state(None, updates={"race_distance": "Marathon"})
    assert state["ux"]["stage"] == PLAN_UX_STAGE_GOAL_ALIGNMENT


def test_plan_intake_ux_state_preserves_runner_understanding_flag():
    state = update_plan_intake_state(None, updates={"race_distance": "Marathon"})
    state = mark_plan_runner_understanding_shown(state)
    assert plan_runner_understanding_shown(state) is True

    state = update_plan_intake_state(state, updates={"race_date": "2026-10-12"})
    assert plan_runner_understanding_shown(state) is True


def test_plan_intake_mark_runner_understanding_advances_empty_stage():
    state = update_plan_intake_state(None)
    assert state["ux"]["stage"] == "understand_runner"

    state = mark_plan_runner_understanding_shown(state)
    assert state["ux"]["runner_understanding_shown"] is True
    assert state["ux"]["stage"] == PLAN_UX_STAGE_GOAL_ALIGNMENT


def test_plan_intake_ready_after_prior_draft_moves_to_confirm_stage():
    state = update_plan_intake_state(None, updates={"race_distance": "Marathon"})
    state = update_plan_intake_state(
        state,
        updates={
            "race_date": "2026-10-12",
            "primary_goal": "Just Finish",
            "training_days": ["Tue", "Thu", "Sat"],
        },
    )
    assert state["ready_to_generate"] is True
    assert state["ux"]["stage"] == PLAN_UX_STAGE_CONFIRM


def test_plan_intake_normalizes_goal_phrases():
    """Broader primary_goal strings map to schema enum values."""
    state = update_plan_intake_state(
        None,
        updates={
            "race_date": "2026-10-12",
            "race_distance": "Marathon",
            "primary_goal": "going for a personal record",
            "training_days": ["Tue", "Thu", "Sat"],
            "target_time": "3:40:00",
        },
    )
    assert state["draft"]["primary_goal"] == "Target Time"
    assert state["ready_to_generate"] is True


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


def test_plan_intake_training_days_monday_through_saturday_string():
    state = update_plan_intake_state(
        None,
        updates={
            "race_date": "2026-10-12",
            "race_distance": "Marathon",
            "primary_goal": "Just Finish",
            "training_days": "Monday through Saturday",
        },
    )
    assert state["draft"]["training_days"] == [
        "Mon",
        "Tue",
        "Wed",
        "Thu",
        "Fri",
        "Sat",
    ]
    assert state["ready_to_generate"] is True


def test_plan_intake_training_days_weekdays_plus_saturday():
    state = update_plan_intake_state(
        None,
        updates={
            "race_date": "2026-10-12",
            "race_distance": "Marathon",
            "primary_goal": "Just Finish",
            "training_days": "weekdays plus Saturday",
        },
    )
    assert state["draft"]["training_days"] == [
        "Mon",
        "Tue",
        "Wed",
        "Thu",
        "Fri",
        "Sat",
    ]


def test_plan_intake_training_days_count_is_valid_partial_input():
    state = update_plan_intake_state(
        None,
        updates={
            "race_date": "2026-10-12",
            "race_distance": "Marathon",
            "primary_goal": "Target Time",
            "target_time": "3:30:00",
            "training_days": "5 days per week",
        },
    )
    assert state["ready_to_generate"] is False
    assert state["errors"] == []
    assert state["missing_required"] == ["training_days"]
    assert state["ux"]["training_days_count"] == 5
    assert state["ux"]["stage"] == "details"
    assert "training_days" not in state["draft"]
    assert state["draft"]["race_distance"] == "Marathon"
    assert state["draft"]["target_time"] == "3:30:00"


def test_plan_intake_training_days_count_from_source_message_preserves_fast_track_inputs():
    state = update_plan_intake_state(
        None,
        updates={
            "race_name": "Chicago Marathon",
            "race_date": "Oct 11 2026",
            "primary_goal": "Target Time",
            "target_time": "3:30",
        },
        source_user_message="Chicago Oct 11, 3:30 goal, 5 days per week",
    )
    assert state["ready_to_generate"] is False
    assert state["errors"] == []
    assert state["missing_required"] == ["training_days"]
    assert state["ux"]["training_days_count"] == 5
    assert state["ux"]["stage"] == "details"
    assert state["draft"]["race_distance"] == "Marathon"
    assert state["draft"]["race_name"] == "Chicago Marathon"


def test_plan_intake_training_days_actual_weekdays_clear_count_partial():
    state = update_plan_intake_state(
        None,
        updates={
            "race_date": "2026-10-12",
            "race_distance": "Marathon",
            "primary_goal": "Just Finish",
            "training_days": "5 days per week",
        },
    )
    state = update_plan_intake_state(
        state,
        updates={"training_days": "Monday, Tuesday, Thursday, Friday, Saturday"},
    )
    assert state["ready_to_generate"] is True
    assert state["ux"]["stage"] == PLAN_UX_STAGE_CONFIRM
    assert "training_days_count" not in state["ux"]
    assert state["draft"]["training_days"] == ["Mon", "Tue", "Thu", "Fri", "Sat"]


def test_plan_intake_training_days_wraparound_range():
    state = update_plan_intake_state(
        None,
        updates={
            "race_date": "2026-10-12",
            "race_distance": "Marathon",
            "primary_goal": "Just Finish",
            "training_days": "Friday through Monday",
        },
    )
    assert state["draft"]["training_days"] == ["Fri", "Sat", "Sun", "Mon"]


def test_plan_intake_infers_marathon_from_race_name_only():
    state = update_plan_intake_state(
        None,
        updates={
            "race_name": "Chicago Marathon",
            "race_date": "2026-10-12",
            "primary_goal": "Just Finish",
            "training_days": ["Tue", "Thu", "Sat"],
        },
    )
    assert state["draft"]["race_distance"] == "Marathon"
    assert state["draft"]["race_name"] == "Chicago Marathon"
    assert state["ready_to_generate"] is True


def test_plan_intake_normalizes_race_distance_synonyms():
    state = update_plan_intake_state(
        None,
        updates={"race_distance": "full marathon"},
    )
    assert state["draft"]["race_distance"] == "Marathon"


def test_plan_intake_fills_race_name_from_source_user_message():
    state = update_plan_intake_state(
        None,
        updates={
            "race_date": "2026-10-12",
            "race_distance": "Marathon",
            "primary_goal": "Just Finish",
            "training_days": ["Tue", "Thu", "Sat"],
        },
        source_user_message=(
            "Please build a plan for the Bank of America Chicago Marathon on that date."
        ),
    )
    assert state["draft"]["race_name"] == "Bank of America Chicago Marathon"
    assert state["ready_to_generate"] is True


def test_plan_intake_does_not_overwrite_explicit_race_name_when_user_message_differs():
    state = update_plan_intake_state(
        None,
        updates={
            "race_name": "Berlin Marathon",
            "race_date": "2026-09-27",
            "race_distance": "Marathon",
            "primary_goal": "Just Finish",
            "training_days": ["Tue", "Thu", "Sat"],
        },
        source_user_message="I was also thinking about Chicago Marathon someday",
    )
    assert state["draft"]["race_name"] == "Berlin Marathon"


def test_user_confirms_plan_intake_short_affirmations():
    assert user_confirms_plan_intake("Y") is True
    assert user_confirms_plan_intake("y.") is True
    assert user_confirms_plan_intake("yes") is True
    assert user_confirms_plan_intake("Looks good!") is True
    assert user_confirms_plan_intake("yes but change the date") is False
    assert user_confirms_plan_intake("no thanks") is False
