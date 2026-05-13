"""Fastpath bypasses LLM when athlete taps Create my plan or recap is chip-confirmed."""

from __future__ import annotations

from typing import Any, Dict

import pytest

from src.smartcoach_mobile_coach.orchestrator import should_plan_confirm_fastpath_fire


def _ready_state(*, plan_generation_confirmed: bool) -> Dict[str, Any]:
    ux: Dict[str, Any] = {
        "intake_confirmed": True,
        "runner_review_delivered": True,
        "plan_creation_phase": "awaiting_plan_generation_confirmation",
        "plan_generation_readiness": {
            "decision": "allow",
            "readiness_level": "ready",
            "allowed_user_actions": ["create_plan"],
        },
    }
    if plan_generation_confirmed:
        ux["plan_generation_confirmed"] = True
    return {
        "draft": {
            "race_distance": "Marathon",
            "race_date": "2026-10-11",
            "primary_goal": "Target Time",
            "target_time": "3:40:00",
            "training_days": ["Mon", "Wed", "Fri", "Sat"],
        },
        "ready_to_generate": True,
        "ux": ux,
        "alignment": {},
    }


@pytest.fixture(autouse=True)
def _enable_fastpath(monkeypatch):
    monkeypatch.setenv("SMARTCOACH_PLAN_CONFIRM_FASTPATH", "1")


def test_fastpath_fires_when_create_my_plan_chip_message():
    """Mobile chip emits user_message='Create my plan'; LLM must NOT be required."""
    state = _ready_state(plan_generation_confirmed=False)
    assert should_plan_confirm_fastpath_fire(state, "Create my plan") is True


def test_fastpath_fires_when_chip_already_flipped_plan_generation_confirmed():
    """Route-side merge sets plan_generation_confirmed; even a blank user_message must fire."""
    state = _ready_state(plan_generation_confirmed=True)
    assert should_plan_confirm_fastpath_fire(state, "") is True


def test_fastpath_fires_for_yes_style_confirmations():
    state = _ready_state(plan_generation_confirmed=False)
    assert should_plan_confirm_fastpath_fire(state, "yes") is True
    assert should_plan_confirm_fastpath_fire(state, "Looks good") is True


def test_fastpath_skipped_when_not_ready_to_generate():
    state = _ready_state(plan_generation_confirmed=True)
    state["ready_to_generate"] = False
    assert should_plan_confirm_fastpath_fire(state, "Create my plan") is False


def test_fastpath_skipped_when_eval_model_override_set():
    state = _ready_state(plan_generation_confirmed=True)
    assert (
        should_plan_confirm_fastpath_fire(
            state, "Create my plan", eval_model_override="gpt-4o-mini"
        )
        is False
    )


def test_fastpath_skipped_when_env_disabled(monkeypatch):
    monkeypatch.setenv("SMARTCOACH_PLAN_CONFIRM_FASTPATH", "0")
    state = _ready_state(plan_generation_confirmed=True)
    assert should_plan_confirm_fastpath_fire(state, "Create my plan") is False


def test_fastpath_skipped_for_unrelated_user_text():
    state = _ready_state(plan_generation_confirmed=False)
    assert should_plan_confirm_fastpath_fire(state, "What about Tuesdays?") is False


def test_fastpath_skipped_when_no_prior_plan_state():
    assert should_plan_confirm_fastpath_fire(None, "Create my plan") is False
