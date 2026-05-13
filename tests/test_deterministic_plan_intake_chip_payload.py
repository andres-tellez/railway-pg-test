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
