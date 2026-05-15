"""Snapshot builder tests for no-plan and follow-up contexts."""

from __future__ import annotations

from src.smartcoach_mobile_coach.coach_context.schemas import (
    AthleteSlice,
    PlanSlice,
    TrendsSlice,
    WorkingContextSlice,
)
from src.smartcoach_mobile_coach.coach_context.snapshot_builder import build_snapshot


def test_build_snapshot_no_plan(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.coach_context.snapshot_builder.build_user_context_payload",
        lambda **_kw: {
            "display_name": "Andre",
            "baseline_status": "thin",
            "preferences": {"unit_system": "metric"},
            "race_goal": None,
            "plan": None,
            "plan_memories": [],
            "session_summary": None,
        },
    )
    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.coach_context.snapshot_builder.build_athlete_slice",
        lambda **_kw: AthleteSlice(
            display_name="Andre",
            unit_system="km",
            baseline_status="thin",
            hr_calibration_status="in_progress",
            zones_compact=None,
        ),
    )
    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.coach_context.snapshot_builder.build_plan_slice",
        lambda **_kw: PlanSlice(has_active_plan=False, race=None, phase=None),
    )
    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.coach_context.snapshot_builder.build_trends_slice",
        lambda **_kw: TrendsSlice(
            mileage_4w=[10, 12, 14, 16], mileage_delta_last_vs_avg=4
        ),
    )
    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.coach_context.snapshot_builder.build_memory_slice",
        lambda **_kw: None,
    )
    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.coach_context.snapshot_builder.build_working_slice",
        lambda **_kw: None,
    )
    result = build_snapshot(
        session=None,
        internal_user_id="11111111-1111-1111-1111-111111111111",
        tz="UTC",
        anchor_local_date="2026-05-15",
        conversation_history=[{"role": "assistant", "content": "hi"}],
    )
    assert result.snapshot.plan is not None
    assert result.snapshot.plan.has_active_plan is False
    assert result.snapshot.athlete is not None
    assert result.snapshot.athlete.zones_compact is None


def test_build_snapshot_followup_has_last_activity(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.coach_context.snapshot_builder.build_user_context_payload",
        lambda **_kw: {"preferences": {"unit_system": "imperial"}},
    )
    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.coach_context.snapshot_builder.build_athlete_slice",
        lambda **_kw: AthleteSlice(
            display_name=None,
            unit_system="mi",
            baseline_status=None,
            hr_calibration_status="unknown",
            zones_compact=None,
        ),
    )
    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.coach_context.snapshot_builder.build_plan_slice",
        lambda **_kw: PlanSlice(has_active_plan=False),
    )
    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.coach_context.snapshot_builder.build_trends_slice",
        lambda **_kw: None,
    )
    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.coach_context.snapshot_builder.build_memory_slice",
        lambda **_kw: None,
    )
    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.coach_context.snapshot_builder.build_working_slice",
        lambda **_kw: WorkingContextSlice(
            last_structured_run_activity_id=42,
            prior_run_summary_in_thread=True,
            plan_creation_clarification_pending=False,
        ),
    )
    result = build_snapshot(
        session=None,
        internal_user_id="11111111-1111-1111-1111-111111111111",
        tz="UTC",
        anchor_local_date="2026-05-15",
        conversation_history=[],
    )
    assert result.snapshot.working is not None
    assert result.snapshot.working.last_structured_run_activity_id == 42
