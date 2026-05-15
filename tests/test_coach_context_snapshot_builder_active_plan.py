"""Snapshot builder tests for active-plan users."""

from __future__ import annotations

from src.smartcoach_mobile_coach.coach_context.schemas import (
    AthleteSlice,
    MemorySlice,
    PlanSlice,
    TrendsSlice,
    WorkingContextSlice,
)
from src.smartcoach_mobile_coach.coach_context.snapshot_builder import build_snapshot


def test_build_snapshot_active_plan(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.coach_context.snapshot_builder.build_user_context_payload",
        lambda **_kw: {
            "display_name": "Andre",
            "baseline_status": "thin",
            "preferences": {"unit_system": "imperial"},
            "race_goal": {
                "race_name": "Chicago",
                "race_distance": "Marathon",
                "race_date": "2026-10-11",
                "goal_time": "3:40:00",
                "weeks_until_race": 20,
            },
            "plan": {
                "current_phase": "Build",
                "current_week_number": 4,
                "phase_kpi_priority": [{"label": "Aerobic endurance"}],
            },
            "plan_memories": [{"text": "Long run on Sunday", "source": "plan"}],
            "session_summary": {"excerpt": "Great consistency this week"},
        },
    )
    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.coach_context.snapshot_builder.build_athlete_slice",
        lambda **_kw: AthleteSlice(
            display_name="Andre",
            unit_system="mi",
            baseline_status="thin",
            hr_calibration_status="calibrated",
            zones_compact={"z2_bpm": 145, "z3_bpm": 160, "z4_bpm": 172},
        ),
    )
    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.coach_context.snapshot_builder.build_plan_slice",
        lambda **_kw: PlanSlice(
            has_active_plan=True,
            race={
                "name": "Chicago",
                "distance": "Marathon",
                "date": "2026-10-11",
                "weeks_until": 20,
                "goal_time": "3:40:00",
            },
            phase={"label": "Build", "week_in_phase": 4, "kpi_priority": ["Aerobic"]},
        ),
    )
    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.coach_context.snapshot_builder.build_trends_slice",
        lambda **_kw: TrendsSlice(
            mileage_4w=[20, 24, 28, 30], mileage_delta_last_vs_avg=6
        ),
    )
    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.coach_context.snapshot_builder.build_memory_slice",
        lambda **_kw: MemorySlice(
            plan_memories=[{"text": "Long run on Sunday", "source": "plan"}],
            session_summary_excerpt=None,
        ),
    )
    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.coach_context.snapshot_builder.build_working_slice",
        lambda **_kw: WorkingContextSlice(
            last_structured_run_activity_id=101,
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
    assert result.snapshot.plan is not None
    assert result.snapshot.plan.has_active_plan is True
    assert result.snapshot.trends is not None
    assert result.trace["built"] is True


def test_build_snapshot_soft_failure_isolated(monkeypatch) -> None:
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
        lambda **_kw: (_ for _ in ()).throw(RuntimeError("boom")),
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
        conversation_history=[],
    )
    assert result.snapshot.plan is not None
    assert result.snapshot.trends is None
