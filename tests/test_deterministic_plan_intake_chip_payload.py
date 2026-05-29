"""Deterministic assistant JSON for structured plan-intake chip turns (no LLM)."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.smartcoach_mobile_coach.orchestrator.plan_creation_branch import (
    build_deterministic_plan_intake_chip_assistant_payload,
)


def test_deterministic_chip_payload_includes_plan_intake_state_and_copy():
    session = MagicMock()
    state = {
        "draft": {},
        "missing_required": ["race_distance"],
        "ready_to_generate": False,
        "ux": {},
        "alignment": {},
    }
    out = build_deterministic_plan_intake_chip_assistant_payload(
        session,
        "user-1",
        plan_intake_state=state,
        anchor_local_date="2026-05-13",
        activity_summary=None,
    )
    assert out.get("type") == "text"
    content = str(out.get("content") or "")
    assert "half marathon" in content.lower() or "marathon" in content.lower()
    data = out.get("data") or {}
    assert isinstance(data.get("plan_intake_state"), dict)


def test_deterministic_chip_skips_runner_card_when_tradeoff_resolved(monkeypatch):
    from src.smartcoach_mobile_coach.orchestrator import plan_creation_branch as pcb

    fake_review = {
        "assessment_status": "ready_to_generate",
        "plan_generation_readiness": {"decision": "allow"},
    }
    monkeypatch.setattr(
        pcb,
        "_try_build_runner_review_bundle",
        lambda *a, **k: ("", fake_review),
    )
    session = MagicMock()
    state = {
        "draft": {
            "race_distance": "Marathon",
            "race_date": "2026-10-11",
            "primary_goal": "Target Time",
            "target_time": "3:40:00",
            "training_days": ["Mon", "Wed", "Sat"],
        },
        "missing_required": [],
        "ready_to_generate": True,
        "ux": {
            "intake_confirmed": True,
            "runner_review_delivered": True,
            "runner_tradeoff_resolved": True,
        },
        "alignment": {},
    }
    out = build_deterministic_plan_intake_chip_assistant_payload(
        session,
        "user-1",
        plan_intake_state=state,
        anchor_local_date="2026-05-13",
        activity_summary=None,
    )
    data = out.get("data") or {}
    assert "pre_generation_runner_review" not in data
    assert "updated your goal" in str(out.get("content") or "").lower()
    ui = data.get("ui_prompt")
    assert isinstance(ui, dict)
    assert ui.get("field_key") == "plan_intake.plan_generation_confirm"
