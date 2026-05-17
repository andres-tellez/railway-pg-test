"""Tests for isolated Run Review Lab system prompt builder."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.smartcoach_mobile_coach.experiments.run_review_lab_isolated_system.builder import (
    build_isolated_lab_system_prefix,
)
from src.smartcoach_mobile_coach.thread_derived_context import DerivedThreadCoachContext


def test_isolated_prefix_skips_full_orchestrator_contracts() -> None:
    sess = MagicMock()
    with patch(
        "src.smartcoach_mobile_coach.orchestrator._hr_calibration_system_section",
        return_value="",
    ):
        text = build_isolated_lab_system_prefix(
            anchor_local_date="2026-05-17",
            client_timezone="America/Chicago",
            session=sess,
            internal_user_id="user-1",
            thread_ctx=None,
        )
    assert "run-review experiment turn" in text
    assert "2026-05-17" in text
    assert "America/Chicago" in text
    assert "CORE PRINCIPLES" not in text
    assert "Coach turn prose shape" not in text


def test_isolated_prefix_thread_continuity_when_activity_known() -> None:
    sess = MagicMock()
    ctx = DerivedThreadCoachContext(
        prior_run_summary_in_thread=True,
        last_assistant_was_run_summary=True,
        last_structured_run_activity_id=9001,
        latest_plan_intake_state=None,
        latest_plan_generation_result=None,
    )
    with patch(
        "src.smartcoach_mobile_coach.orchestrator._hr_calibration_system_section",
        return_value="",
    ):
        text = build_isolated_lab_system_prefix(
            anchor_local_date="2026-05-17",
            client_timezone=None,
            session=sess,
            internal_user_id="u1",
            thread_ctx=ctx,
        )
    assert "Thread continuity" in text
    assert "9001" in text
