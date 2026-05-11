"""Runner-review UX stamping for split-confirm + tradeoff chips."""

from __future__ import annotations

import pytest

from src.smartcoach_mobile_coach.orchestrator import (
    _additional_training_day_ui_prompt_from_plan_intake_state,
    _merge_split_confirm_ux_after_runner_review,
    _plan_generation_confirm_ui_prompt_from_plan_intake_state,
    _runner_tradeoff_ui_prompt_from_plan_intake_state,
    _ui_prompt_from_plan_intake_state,
)
from src.smartcoach_mobile_coach.plan_intake_flow import update_plan_intake_state


def test_merge_clears_stale_resolved_when_ready_flips_to_needs_decision():
    uxs = {
        "intake_confirmed": True,
        "runner_tradeoff_resolved": True,
        "runner_review_assessment_status": "ready_to_generate",
    }
    _merge_split_confirm_ux_after_runner_review(
        uxs,
        {"assessment_status": "needs_user_decision"},
        intake_confirmed=True,
    )
    assert uxs["runner_review_assessment_status"] == "needs_user_decision"
    assert uxs.get("runner_tradeoff_resolved") is False
    assert uxs.get("runner_tradeoff_pending") is True


def test_merge_expansion_pending_suppresses_tradeoff_pending():
    uxs = {
        "runner_tradeoff_resolved": False,
        "training_days_expansion_pending": True,
        "runner_review_assessment_status": "needs_user_decision",
    }
    _merge_split_confirm_ux_after_runner_review(
        uxs,
        {"assessment_status": "needs_user_decision"},
        intake_confirmed=True,
    )
    assert uxs.get("runner_tradeoff_pending") is False


def test_merge_edit_focus_suppresses_tradeoff_pending():
    uxs = {
        "runner_tradeoff_resolved": False,
        "runner_tradeoff_edit_focus": "goal",
        "runner_review_assessment_status": "needs_user_decision",
    }
    _merge_split_confirm_ux_after_runner_review(
        uxs,
        {"assessment_status": "needs_user_decision"},
        intake_confirmed=True,
    )
    assert uxs.get("runner_tradeoff_pending") is False


def test_merge_needs_decision_respects_continue_resolve():
    # User tapped Continue with tradeoff: resolved True, classifier still needs_user_decision
    uxs = {
        "runner_tradeoff_resolved": True,
        "runner_review_assessment_status": "needs_user_decision",
    }
    _merge_split_confirm_ux_after_runner_review(
        uxs,
        {"assessment_status": "needs_user_decision"},
        intake_confirmed=True,
    )
    assert uxs.get("runner_tradeoff_pending") is False


def test_merge_ready_to_generate_does_not_set_runner_tradeoff_resolved():
    uxs = {}
    _merge_split_confirm_ux_after_runner_review(
        uxs,
        {"assessment_status": "ready_to_generate"},
        intake_confirmed=True,
    )
    assert uxs.get("runner_tradeoff_pending") is False
    assert "runner_tradeoff_resolved" not in uxs


def test_merge_none_review_bundle_does_not_force_resolved():
    uxs = {}
    _merge_split_confirm_ux_after_runner_review(uxs, None, intake_confirmed=False)
    assert "runner_tradeoff_resolved" not in uxs


@pytest.fixture
def monkeypatch_split_confirm(monkeypatch):
    monkeypatch.setenv("SMARTCOACH_PLAN_CREATION_SPLIT_CONFIRM_V1", "1")


def test_ui_prompt_tradeoff_not_create_when_needs_decision_pending(
    monkeypatch_split_confirm,
):
    intake = {
        "ready_to_generate": True,
        "draft": {
            "race_distance": "Marathon",
            "primary_goal": "Target Time",
            "target_time": "3:00:00",
            "training_days": ["Mon", "Wed", "Sat"],
            "race_date": "2026-10-11",
        },
        "ux": {
            "intake_confirmed": True,
            "runner_review_delivered": True,
            "runner_review_assessment_status": "needs_user_decision",
            "runner_tradeoff_pending": True,
            "runner_tradeoff_resolved": False,
        },
        "alignment": {},
    }
    tradeoff = _runner_tradeoff_ui_prompt_from_plan_intake_state(intake)
    assert tradeoff is not None
    assert tradeoff.get("field_key") == "plan_intake.runner_tradeoff"
    assert _plan_generation_confirm_ui_prompt_from_plan_intake_state(intake) is None
    prompt = _ui_prompt_from_plan_intake_state(intake)
    assert prompt is not None
    assert prompt.get("field_key") == "plan_intake.runner_tradeoff"


def test_expand_running_days_resolves_tradeoff_and_starts_add_day_flow(monkeypatch):
    monkeypatch.setenv("SMARTCOACH_PLAN_CREATION_SPLIT_CONFIRM_V1", "1")
    base = {
        "draft": {
            "race_distance": "Marathon",
            "race_date": "2026-10-11",
            "primary_goal": "Target Time",
            "target_time": "3:00:00",
            "training_days": ["Mon", "Wed", "Sat"],
            "long_run_day": "Sat",
        },
        "ux": {
            "intake_confirmed": True,
            "runner_review_delivered": True,
            "runner_tradeoff_pending": True,
            "runner_tradeoff_resolved": False,
            "runner_review_assessment_status": "needs_user_decision",
        },
        "alignment": {},
    }
    out = update_plan_intake_state(
        base,
        updates={"runner_tradeoff_choice": "expand_running_days"},
        source_user_message="",
    )
    ux = out["ux"]
    assert ux.get("runner_tradeoff_resolved") is True
    assert ux.get("runner_tradeoff_pending") is False
    assert ux.get("runner_add_day_pick_pending") is True
    assert ux.get("training_days_expansion_pending") is True
    assert ux.get("expansion_base_training_days") == ["Mon", "Wed", "Sat"]
    assert "training_days" in out["missing_required"]


def test_additional_day_prompt_lists_free_weekdays(monkeypatch_split_confirm):
    intake = {
        "ready_to_generate": False,
        "draft": {
            "race_distance": "Marathon",
            "race_date": "2026-10-11",
            "primary_goal": "Target Time",
            "target_time": "3:00:00",
            "long_run_day": "Sat",
        },
        "missing_required": ["training_days"],
        "ux": {
            "intake_confirmed": True,
            "runner_review_delivered": True,
            "runner_add_day_pick_pending": True,
            "training_days_expansion_pending": True,
            "expansion_base_training_days": ["Mon", "Wed", "Sat"],
            "runner_tradeoff_resolved": True,
            "runner_tradeoff_pending": False,
            "runner_review_assessment_status": "needs_user_decision",
        },
        "alignment": {},
    }
    p = _additional_training_day_ui_prompt_from_plan_intake_state(intake)
    assert p is not None
    assert p.get("field_key") == "plan_intake.collect_additional_training_day"
    labels = {o["label"] for o in (p.get("options") or [])}
    assert labels == {"Tuesday", "Thursday", "Friday", "Sunday"}
    tradeoff = _runner_tradeoff_ui_prompt_from_plan_intake_state(intake)
    assert tradeoff is None


def test_ui_prompt_prefers_additional_day_over_tradeoff(monkeypatch_split_confirm):
    intake = {
        "ready_to_generate": False,
        "draft": {
            "race_distance": "Marathon",
            "race_date": "2026-10-11",
            "primary_goal": "Target Time",
            "target_time": "3:00:00",
            "long_run_day": "Sat",
        },
        "missing_required": ["training_days"],
        "ux": {
            "intake_confirmed": True,
            "runner_review_delivered": True,
            "runner_add_day_pick_pending": True,
            "training_days_expansion_pending": True,
            "expansion_base_training_days": ["Mon", "Wed", "Sat"],
            "runner_tradeoff_resolved": True,
            "runner_tradeoff_pending": False,
            "runner_review_assessment_status": "needs_user_decision",
        },
        "alignment": {},
    }
    assert _ui_prompt_from_plan_intake_state(intake).get("field_key") == (
        "plan_intake.collect_additional_training_day"
    )


def test_plan_generation_hidden_when_edit_focus_goal(monkeypatch_split_confirm):
    intake = {
        "ready_to_generate": True,
        "draft": {
            "race_distance": "Marathon",
            "race_date": "2026-10-11",
            "primary_goal": "Target Time",
            "target_time": "3:00:00",
            "training_days": ["Mon", "Wed", "Sat"],
            "long_run_day": "Sat",
        },
        "ux": {
            "intake_confirmed": True,
            "runner_review_delivered": True,
            "runner_tradeoff_edit_focus": "goal",
            "runner_review_assessment_status": "needs_user_decision",
            "runner_tradeoff_resolved": False,
            "runner_tradeoff_pending": False,
        },
        "alignment": {},
    }
    assert _plan_generation_confirm_ui_prompt_from_plan_intake_state(intake) is None
