"""Prompt formatting tests for CoachSnapshot appendix."""

from src.smartcoach_mobile_coach.coach_context.prompt_formatter import (
    format_snapshot_for_system,
)
from src.smartcoach_mobile_coach.coach_context.schemas import CoachSnapshot, PlanSlice


def test_formatter_emits_header_and_json_block() -> None:
    snapshot = CoachSnapshot(
        schema_version=1,
        today="2026-05-15",
        tz="UTC",
        athlete=None,
        plan=PlanSlice(has_active_plan=False),
        trends=None,
        memory=None,
        working=None,
        omitted_fields=["trends"],
    )
    block = format_snapshot_for_system(snapshot)
    assert "## Coach Snapshot v1 (authoritative)" in block
    assert "```json" in block
    assert '"has_active_plan":false' in block
    assert '"omitted_fields":["trends"]' in block
    assert "None" not in block
