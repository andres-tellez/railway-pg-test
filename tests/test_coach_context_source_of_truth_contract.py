"""Contracts for CoachContext field source mapping and import guardrails."""

from pathlib import Path

from src.smartcoach_mobile_coach.coach_context.snapshot_builder import FIELD_SOURCES


def test_field_sources_cover_expected_keys() -> None:
    expected = {
        "plan.has_active_plan",
        "plan.race",
        "plan.phase",
        "athlete.display_name",
        "athlete.baseline_status",
        "athlete.unit_system",
        "athlete.hr_calibration_status",
        "athlete.zones_compact",
        "trends.mileage_4w",
        "memory.plan_memories",
        "memory.session_summary_excerpt",
        "working.last_structured_run_activity_id",
    }
    assert expected.issubset(set(FIELD_SOURCES.keys()))
    assert len(set(FIELD_SOURCES.keys())) == len(FIELD_SOURCES.keys())


def test_coach_context_must_not_import_orchestrator() -> None:
    base = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "smartcoach_mobile_coach"
        / "coach_context"
    )
    offenders = []
    for path in base.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if (
            "from src.smartcoach_mobile_coach.orchestrator import" in text
            or "import src.smartcoach_mobile_coach.orchestrator" in text
        ):
            offenders.append(str(path))
    assert offenders == []
