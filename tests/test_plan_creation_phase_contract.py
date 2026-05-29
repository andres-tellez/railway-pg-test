"""Contract tests: plan_creation_phase + compute_plan_creation_ui (split-confirm)."""

from __future__ import annotations

import pytest

from src.smartcoach_mobile_coach.plan_creation_ui import (
    PHASE_AWAITING_INTAKE_CONFIRMATION,
    PHASE_AWAITING_PLAN_GENERATION_CONFIRMATION,
    PHASE_AWAITING_TRADEOFF_CHOICE,
    PHASE_COLLECTING_ADDITIONAL_TRAINING_DAY,
    PHASE_COLLECTING_INTAKE,
    apply_review_to_plan_intake_ux_for_phase,
    compute_plan_creation_ui,
)
from src.smartcoach_mobile_coach.plan_intake_flow import update_plan_intake_state


DRAFT_SUB3 = {
    "race_distance": "Marathon",
    "race_date": "2026-10-11",
    "primary_goal": "Target Time",
    "target_time": "3:00:00",
    "training_days": ["Mon", "Wed", "Sat"],
    "long_run_day": "Sat",
}


@pytest.fixture
def monkeypatch_split_confirm(monkeypatch):
    monkeypatch.setenv("SMARTCOACH_PLAN_CREATION_SPLIT_CONFIRM_V1", "1")


def test_sub_three_recap_phase_and_yes_no_chips(monkeypatch_split_confirm):
    """Sub-3 + 3 days, ready, not intake_confirmed: recap + Yes/No chips."""
    base = {"draft": dict(DRAFT_SUB3), "ux": {}, "alignment": {}}
    s = update_plan_intake_state(base, updates={}, source_user_message="")
    assert s.get("ready_to_generate") is True
    assert s["ux"].get("plan_creation_phase") == PHASE_AWAITING_INTAKE_CONFIRMATION
    ui = compute_plan_creation_ui(s)
    assert ui is not None
    assert ui.get("field_key") == "plan_intake.intake_confirmation"
    labels = {o["label"] for o in (ui.get("options") or [])}
    assert labels == {"Yes", "No"}


def test_intake_confirmation_yes_chip_marks_confirmed(monkeypatch_split_confirm):
    base = {"draft": dict(DRAFT_SUB3), "ux": {}, "alignment": {}}
    s0 = update_plan_intake_state(base, updates={}, source_user_message="")
    s1 = update_plan_intake_state(
        s0,
        updates={"intake_confirmed": True},
        source_user_message="Yes, that looks right.",
    )
    assert s1["ux"].get("intake_confirmed") is True


def test_full_sub_three_add_tuesday_recap_then_create_chip(monkeypatch_split_confirm):
    s0 = update_plan_intake_state(
        {"draft": dict(DRAFT_SUB3), "ux": {}, "alignment": {}},
        updates={},
        source_user_message="",
    )
    assert s0["ux"]["plan_creation_phase"] == PHASE_AWAITING_INTAKE_CONFIRMATION

    s1 = update_plan_intake_state(s0, updates={}, source_user_message="yes")
    assert s1["ux"].get("intake_confirmed") is True
    apply_review_to_plan_intake_ux_for_phase(
        s1,
        {"assessment_status": "needs_user_decision"},
        intake_confirmed=True,
    )
    assert s1["ux"]["plan_creation_phase"] == PHASE_AWAITING_TRADEOFF_CHOICE
    tradeoff = compute_plan_creation_ui(s1)
    assert tradeoff is not None
    assert tradeoff.get("field_key") == "plan_intake.runner_tradeoff"

    s2 = update_plan_intake_state(
        s1,
        updates={"runner_tradeoff_choice": "expand_running_days"},
        source_user_message="",
    )
    assert s2["ux"]["plan_creation_phase"] == PHASE_COLLECTING_ADDITIONAL_TRAINING_DAY
    add_ui = compute_plan_creation_ui(s2)
    assert add_ui is not None
    assert add_ui.get("field_key") == "plan_intake.collect_additional_training_day"
    labels = {o["label"] for o in (add_ui.get("options") or [])}
    assert labels == {"Tuesday", "Thursday", "Friday", "Sunday"}

    merged = ["Mon", "Tue", "Wed", "Sat"]
    s3 = update_plan_intake_state(
        s2,
        updates={"training_days": merged},
        source_user_message="",
    )
    assert s3["ux"]["plan_creation_phase"] == PHASE_AWAITING_INTAKE_CONFIRMATION
    ui3 = compute_plan_creation_ui(s3)
    # Recap is NL; schedule re-confirm chips may appear after expansion clears.
    assert ui3 is None or ui3.get("field_key") != "plan_intake.plan_generation_confirm"
    assert s3["ux"].get("plan_generation_confirmed") is None

    s3b = s3
    if s3["ux"].get("schedule_confirm_before_posture"):
        s3b = update_plan_intake_state(
            s3,
            updates={"schedule_days_confirmed": True},
            source_user_message="",
        )

    s4 = update_plan_intake_state(s3b, updates={}, source_user_message="yes")
    apply_review_to_plan_intake_ux_for_phase(
        s4,
        {
            "assessment_status": "ready_to_generate",
            "plan_generation_readiness": {
                "decision": "allow",
                "readiness_level": "stretch",
                "allowed_user_actions": ["create_plan", "continue_with_warning"],
            },
        },
        intake_confirmed=True,
    )
    assert (
        s4["ux"]["plan_creation_phase"] == PHASE_AWAITING_PLAN_GENERATION_CONFIRMATION
    )
    gen_ui = compute_plan_creation_ui(s4)
    assert gen_ui is not None
    assert gen_ui.get("field_key") == "plan_intake.plan_generation_confirm"


def test_adjust_goal_restarts_full_intake_questionnaire(monkeypatch_split_confirm):
    """Choosing adjust_goal resets intake so the athlete sees the full question flow again."""
    s0 = update_plan_intake_state(
        {"draft": dict(DRAFT_SUB3), "ux": {}, "alignment": {}},
        updates={},
        source_user_message="",
    )
    s1 = update_plan_intake_state(s0, updates={}, source_user_message="yes")
    apply_review_to_plan_intake_ux_for_phase(
        s1,
        {
            "assessment_status": "needs_user_decision",
            "plan_generation_readiness": {
                "decision": "defer",
                "readiness_level": "high_risk",
                "allowed_user_actions": ["adjust_goal"],
            },
        },
        intake_confirmed=True,
    )
    assert s1["ux"]["plan_creation_phase"] == PHASE_AWAITING_TRADEOFF_CHOICE

    s1["ux"]["plan_generation_confirmed"] = True
    s2 = update_plan_intake_state(
        s1,
        updates={"runner_tradeoff_choice": "adjust_goal"},
        source_user_message="",
    )
    assert s2["ux"].get("runner_goal_edit_pending") is not True
    assert s2["ux"].get("runner_tradeoff_edit_focus") is None
    assert s2["draft"] == {}
    assert s2["missing_required"] and s2["missing_required"][0] == "race_distance"
    assert s2["ux"]["plan_creation_phase"] == PHASE_COLLECTING_INTAKE

    ui = compute_plan_creation_ui(s2)
    assert ui is not None
    assert ui.get("field_key") == "plan_intake.race_distance"
