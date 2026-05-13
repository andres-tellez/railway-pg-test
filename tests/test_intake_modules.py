"""Lightweight tests for ``src.smartcoach_mobile_coach.intake`` helpers (Phase 7.1)."""

from __future__ import annotations

from src.smartcoach_mobile_coach.intake import (
    normalize,
    parsers,
    soft_reset,
    structured_updates,
)
from src.smartcoach_mobile_coach.plan_intake_flow import (
    _normalize_race_distance_intake,
)


def test_structured_updates_applies_race_distance():
    draft: dict = {}
    ux: dict = {}
    alignment: dict = {}
    alignment_answers: dict = {}
    errors: list[str] = []
    structured_updates.apply_structured_updates(
        {"race_distance": "Marathon"},
        draft=draft,
        ux=ux,
        alignment=alignment,
        alignment_answers=alignment_answers,
        errors=errors,
        prior_training_days_for_expansion=None,
    )
    assert draft.get("race_distance") == "Marathon"
    assert not errors


def test_normalize_race_distance_intake_helper():
    assert _normalize_race_distance_intake(" marathon ") == "Marathon"


def test_soft_reset_clears_flags():
    ux = {"intake_confirmed": True, "plan_generation_readiness": {"x": 1}}
    soft_reset.clear_plan_confirmation_ux(ux)
    assert "intake_confirmed" not in ux
    assert "plan_generation_readiness" not in ux


def test_validate_long_run_matches_training_days():
    errors: list[str] = []
    normalize.validate_long_run_matches_training_days(
        {"training_days": ["Mon", "Wed"], "long_run_day": "Fri"},
        errors,
    )
    assert errors


def test_state_machine_finalizes_via_public_entrypoint():
    from src.smartcoach_mobile_coach.plan_intake_flow import update_plan_intake_state

    s = update_plan_intake_state(None)
    assert s.get("version") == 1
    assert "missing_required" in s
