"""Budget/drop policy tests for CoachContext."""

from src.smartcoach_mobile_coach.coach_context.budget import apply_budget
from src.smartcoach_mobile_coach.coach_context.schemas import (
    AthleteSlice,
    CoachSnapshot,
    MemorySlice,
    PlanSlice,
    TrendsSlice,
    WorkingContextSlice,
)


def _snapshot_with_large_memory() -> CoachSnapshot:
    return CoachSnapshot(
        schema_version=1,
        today="2026-05-15",
        tz="UTC",
        athlete=AthleteSlice(
            display_name="A",
            unit_system="mi",
            baseline_status="thin",
            hr_calibration_status="calibrated",
            zones_compact={"z2_bpm": 1, "z3_bpm": 2, "z4_bpm": 3},
        ),
        plan=PlanSlice(
            has_active_plan=True, race={"name": "X"}, phase={"label": "Base"}
        ),
        trends=TrendsSlice(mileage_4w=[20, 22, 24, 26], mileage_delta_last_vs_avg=4),
        memory=MemorySlice(
            plan_memories=[
                {"text": "x" * 400, "source": "coach"},
                {"text": "y" * 400, "source": "coach"},
            ],
            session_summary_excerpt="z" * 500,
        ),
        working=WorkingContextSlice(
            last_structured_run_activity_id=42,
            prior_run_summary_in_thread=True,
            plan_creation_clarification_pending=True,
        ),
        omitted_fields=[],
    )


def test_budget_drops_fields_and_preserves_must_keep() -> None:
    snap = _snapshot_with_large_memory()
    updated, omitted, _size = apply_budget(snap, max_chars=500)
    assert updated.plan is not None
    assert updated.plan.has_active_plan is True
    assert updated.today == "2026-05-15"
    assert "memory.session_summary_excerpt" in omitted
    assert any(k.startswith("memory") for k in omitted)
