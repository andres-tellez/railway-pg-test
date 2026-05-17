from __future__ import annotations

from src.smartcoach_mobile_coach.run_review.context_builder import stub_context_for_test
from src.smartcoach_mobile_coach.run_review_lab.prompt import (
    build_run_review_lab_appendix,
)


def test_lab_appendix_includes_data_blocks_without_v2_contract() -> None:
    ctx = stub_context_for_test(
        activity_id=42,
        anchor_local_date="2026-05-17",
        facts={"execution_summary": {"planned": {"type": "easy"}}},
        evidence_pack={"version": "run_review_evidence_pack_v1_easy"},
    )
    appendix = build_run_review_lab_appendix(
        ctx=ctx,
        coach_snapshot={"schema_version": 1, "today": "2026-05-17"},
    )
    assert "## Run review (lab mode)" in appendix
    assert '"run_context"' in appendix
    assert '"coach_snapshot"' in appendix
    assert "## Output format for this turn" not in appendix
    assert "## Coaching Evaluation Rubric" not in appendix
