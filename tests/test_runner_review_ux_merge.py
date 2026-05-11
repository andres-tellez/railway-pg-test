"""Runner-review UX stamping for split-confirm + tradeoff chips (phase model)."""

from __future__ import annotations

import pytest

from src.smartcoach_mobile_coach.plan_creation_ui import (
    apply_review_to_plan_intake_ux_for_phase,
    compute_plan_creation_ui,
    recompute_plan_creation_phase,
    sync_legacy_ux_from_phase,
)
from src.smartcoach_mobile_coach.plan_intake_flow import update_plan_intake_state


def _marathon_draft() -> dict:
    return {
        "race_distance": "Marathon",
        "race_date": "2026-10-11",
        "primary_goal": "Target Time",
        "target_time": "3:00:00",
        "training_days": ["Mon", "Wed", "Sat"],
        "long_run_day": "Sat",
    }


def _finalize_phase(state: dict) -> None:
    recompute_plan_creation_phase(state)
    ux = state.get("ux") if isinstance(state.get("ux"), dict) else {}
    sync_legacy_ux_from_phase(ux, str(ux.get("plan_creation_phase") or ""))


def _ready_state(ux: dict) -> dict:
    return {
        "version": 1,
        "ux": dict(ux),
        "ready_to_generate": True,
        "status": "ready_to_confirm",
        "missing_required": [],
        "draft": _marathon_draft(),
        "alignment": {},
    }


def test_merge_clears_stale_resolved_when_ready_flips_to_needs_decision():
    uxs = {
        "intake_confirmed": True,
        "runner_tradeoff_resolved": True,
        "runner_review_assessment_status": "ready_to_generate",
    }
    state = _ready_state(uxs)
    apply_review_to_plan_intake_ux_for_phase(
        state,
        {"assessment_status": "needs_user_decision"},
        intake_confirmed=True,
    )
    uxs2 = state["ux"]
    assert uxs2["runner_review_assessment_status"] == "needs_user_decision"
    assert uxs2.get("runner_tradeoff_resolved") is False
    assert uxs2.get("runner_tradeoff_pending") is True


def test_merge_expansion_pending_suppresses_tradeoff_pending():
    uxs = {
        "intake_confirmed": True,
        "runner_tradeoff_resolved": False,
        "training_days_expansion_pending": True,
        "runner_add_day_pick_pending": True,
        "expansion_base_training_days": ["Mon", "Wed", "Sat"],
        "runner_review_assessment_status": "needs_user_decision",
    }
    state = {
        "version": 1,
        "ux": dict(uxs),
        "ready_to_generate": False,
        "status": "collecting",
        "missing_required": ["training_days"],
        "draft": {**_marathon_draft(), "training_days": None},
        "alignment": {},
    }
    del state["draft"]["training_days"]
    apply_review_to_plan_intake_ux_for_phase(
        state,
        {"assessment_status": "needs_user_decision"},
        intake_confirmed=True,
    )
    assert state["ux"].get("runner_tradeoff_pending") is False


def test_merge_edit_focus_suppresses_tradeoff_pending():
    uxs = {
        "intake_confirmed": True,
        "runner_tradeoff_resolved": False,
        "runner_tradeoff_edit_focus": "goal",
        "runner_review_assessment_status": "needs_user_decision",
    }
    state = _ready_state(uxs)
    apply_review_to_plan_intake_ux_for_phase(
        state,
        {"assessment_status": "needs_user_decision"},
        intake_confirmed=True,
    )
    assert state["ux"].get("runner_tradeoff_pending") is False


def test_merge_needs_decision_respects_continue_resolve():
    uxs = {
        "intake_confirmed": True,
        "runner_tradeoff_resolved": True,
        "runner_review_assessment_status": "needs_user_decision",
    }
    state = _ready_state(uxs)
    apply_review_to_plan_intake_ux_for_phase(
        state,
        {"assessment_status": "needs_user_decision"},
        intake_confirmed=True,
    )
    assert state["ux"].get("runner_tradeoff_pending") is False


def test_merge_ready_to_generate_does_not_infer_tradeoff_resolved():
    uxs = {"intake_confirmed": True}
    state = _ready_state(uxs)
    apply_review_to_plan_intake_ux_for_phase(
        state,
        {"assessment_status": "ready_to_generate"},
        intake_confirmed=True,
    )
    assert state["ux"].get("runner_tradeoff_pending") is False
    assert state["ux"].get("runner_review_assessment_status") == "ready_to_generate"
    assert state["ux"].get("runner_tradeoff_resolved") is True


def test_merge_none_review_bundle_recomputes_phase():
    state = {
        "version": 1,
        "ux": {},
        "ready_to_generate": False,
        "status": "collecting",
        "missing_required": ["race_date"],
        "draft": {"race_distance": "Marathon"},
        "alignment": {},
    }
    apply_review_to_plan_intake_ux_for_phase(state, None, intake_confirmed=False)
    assert state["ux"].get("runner_tradeoff_resolved") is False


@pytest.fixture
def monkeypatch_split_confirm(monkeypatch):
    monkeypatch.setenv("SMARTCOACH_PLAN_CREATION_SPLIT_CONFIRM_V1", "1")


def test_ui_prompt_tradeoff_not_create_when_needs_decision_pending(
    monkeypatch_split_confirm,
):
    intake = {
        "ready_to_generate": True,
        "draft": _marathon_draft(),
        "ux": {
            "intake_confirmed": True,
            "runner_review_delivered": True,
            "runner_review_assessment_status": "needs_user_decision",
            "runner_tradeoff_pending": True,
            "runner_tradeoff_resolved": False,
        },
        "missing_required": [],
        "alignment": {},
    }
    _finalize_phase(intake)
    tradeoff = compute_plan_creation_ui(intake)
    assert tradeoff is not None
    assert tradeoff.get("field_key") == "plan_intake.runner_tradeoff"
    gen_chip = compute_plan_creation_ui(
        {
            **intake,
            "ux": {
                **intake["ux"],
                "plan_creation_phase": "awaiting_plan_generation_confirmation",
                "runner_tradeoff_pending": False,
                "runner_tradeoff_resolved": True,
                "plan_generation_readiness": {
                    "decision": "allow",
                    "readiness_level": "ready",
                    "allowed_user_actions": ["create_plan"],
                },
            },
        }
    )
    assert gen_chip is not None
    assert gen_chip.get("field_key") == "plan_intake.plan_generation_confirm"


def test_expand_running_days_resolves_tradeoff_and_starts_add_day_flow(monkeypatch):
    monkeypatch.setenv("SMARTCOACH_PLAN_CREATION_SPLIT_CONFIRM_V1", "1")
    base = {
        "draft": _marathon_draft(),
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
    assert ux.get("plan_creation_phase") == "collecting_additional_training_day"


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
    _finalize_phase(intake)
    p = compute_plan_creation_ui(intake)
    assert p is not None
    assert p.get("field_key") == "plan_intake.collect_additional_training_day"
    labels = {o["label"] for o in (p.get("options") or [])}
    assert labels == {"Tuesday", "Thursday", "Friday", "Sunday"}


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
    _finalize_phase(intake)
    assert compute_plan_creation_ui(intake).get("field_key") == (
        "plan_intake.collect_additional_training_day"
    )


def test_plan_generation_hidden_when_edit_focus_goal(monkeypatch_split_confirm):
    intake = {
        "ready_to_generate": True,
        "draft": _marathon_draft(),
        "ux": {
            "intake_confirmed": True,
            "runner_review_delivered": True,
            "runner_tradeoff_edit_focus": "goal",
            "runner_review_assessment_status": "needs_user_decision",
            "runner_tradeoff_resolved": False,
            "runner_tradeoff_pending": False,
        },
        "missing_required": [],
        "alignment": {},
    }
    _finalize_phase(intake)
    assert compute_plan_creation_ui(intake) is None


def test_plan_generation_hidden_when_readiness_defers(monkeypatch_split_confirm):
    intake = {
        "ready_to_generate": True,
        "draft": _marathon_draft(),
        "ux": {
            "intake_confirmed": True,
            "runner_review_delivered": True,
            "runner_review_assessment_status": "ready_to_generate",
            "runner_tradeoff_resolved": True,
            "runner_tradeoff_pending": False,
            "plan_creation_phase": "awaiting_plan_generation_confirmation",
            "plan_generation_readiness": {
                "decision": "defer",
                "readiness_level": "high_risk",
                "allowed_user_actions": ["add_running_day", "adjust_goal"],
            },
        },
        "missing_required": [],
        "alignment": {},
    }

    assert compute_plan_creation_ui(intake) is None


def test_plan_generation_shown_when_decision_allow_even_if_actions_omit_create_plan(
    monkeypatch_split_confirm,
):
    """Create chip follows readiness decision = allow (not the actions list alone)."""
    intake = {
        "ready_to_generate": True,
        "draft": _marathon_draft(),
        "ux": {
            "intake_confirmed": True,
            "runner_review_delivered": True,
            "runner_review_assessment_status": "ready_to_generate",
            "runner_tradeoff_resolved": True,
            "runner_tradeoff_pending": False,
            "plan_creation_phase": "awaiting_plan_generation_confirmation",
            "plan_generation_readiness": {
                "decision": "allow",
                "readiness_level": "ready",
                "allowed_user_actions": [],
            },
        },
        "missing_required": [],
        "alignment": {},
    }
    gen_ui = compute_plan_creation_ui(intake)
    assert gen_ui is not None
    assert gen_ui.get("field_key") == "plan_intake.plan_generation_confirm"


def test_plan_generation_hidden_when_no_readiness_snapshot(monkeypatch_split_confirm):
    intake = {
        "ready_to_generate": True,
        "draft": _marathon_draft(),
        "ux": {
            "intake_confirmed": True,
            "runner_review_delivered": True,
            "runner_review_assessment_status": "ready_to_generate",
            "runner_tradeoff_resolved": True,
            "runner_tradeoff_pending": False,
            "plan_creation_phase": "awaiting_plan_generation_confirmation",
        },
        "missing_required": [],
        "alignment": {},
    }
    assert compute_plan_creation_ui(intake) is None


def test_currently_unrealistic_tradeoff_filters_continue(monkeypatch_split_confirm):
    intake = {
        "ready_to_generate": True,
        "draft": _marathon_draft(),
        "ux": {
            "intake_confirmed": True,
            "runner_review_delivered": True,
            "runner_review_assessment_status": "needs_user_decision",
            "runner_tradeoff_pending": True,
            "runner_tradeoff_resolved": False,
            "plan_generation_readiness": {
                "decision": "defer",
                "readiness_level": "currently_unrealistic",
                "allowed_user_actions": [
                    "add_running_day",
                    "adjust_goal",
                    "adjust_timeline",
                    "build_base_first",
                ],
            },
        },
        "missing_required": [],
        "alignment": {},
    }
    _finalize_phase(intake)

    tradeoff = compute_plan_creation_ui(intake)
    option_ids = {o["id"] for o in tradeoff.get("options") or []}
    assert "rt_continue" not in option_ids
    assert option_ids == {"rt_expand", "rt_goal", "rt_time", "rt_base"}
