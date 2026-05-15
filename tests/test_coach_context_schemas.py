"""Schema tests for CoachSnapshot dataclasses."""

from src.smartcoach_mobile_coach.coach_context.schemas import (
    AthleteSlice,
    CoachSnapshot,
    PlanSlice,
)


def test_snapshot_to_dict_contains_expected_keys() -> None:
    snap = CoachSnapshot(
        schema_version=1,
        today="2026-05-15",
        tz="UTC",
        athlete=AthleteSlice(
            display_name="Andre",
            unit_system="mi",
            baseline_status="thin",
            hr_calibration_status="calibrated",
            zones_compact={"z2_bpm": 145, "z3_bpm": 160, "z4_bpm": 172},
        ),
        plan=PlanSlice(has_active_plan=True),
        trends=None,
        memory=None,
        working=None,
        omitted_fields=[],
    )
    out = snap.to_dict()
    assert out["schema_version"] == 1
    assert out["today"] == "2026-05-15"
    assert out["athlete"]["unit_system"] == "mi"
    assert out["plan"]["has_active_plan"] is True
    assert out["omitted_fields"] == []
