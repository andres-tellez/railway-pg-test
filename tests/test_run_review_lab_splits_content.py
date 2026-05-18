from __future__ import annotations

from src.smartcoach_mobile_coach.run_review.context_builder import stub_context_for_test
from src.smartcoach_mobile_coach.run_review_lab.splits_content import (
    compose_splits_turn_content,
    render_deterministic_splits_block,
)
from src.smartcoach_mobile_coach.run_review_lab.prompt import (
    build_run_review_lab_appendix,
)


def _ctx_with_splits(*, truncated: bool = False) -> object:
    rows = [
        {
            "lap_index": 1,
            "segment_label": "mile 1 (lap 1)",
            "distance_display": "1.00 mi",
            "moving_time_display": "9:48",
            "avg_pace_display": "9:48/mi",
            "avg_heart_rate_display": "127 bpm",
        },
        {
            "lap_index": 2,
            "segment_label": "mile 2 (lap 2)",
            "distance_display": "1.00 mi",
            "moving_time_display": "9:45",
            "avg_pace_display": "9:45/mi",
            "avg_heart_rate_display": "138 bpm",
        },
    ]
    payload = {
        "splits": rows,
        "splits_count": len(rows),
        "splits_total_count": 5 if truncated else len(rows),
        "splits_truncated": truncated,
    }
    return stub_context_for_test(
        activity_id=99,
        anchor_local_date="2026-05-18",
        facts={},
        splits_payload=payload,
        scope="splits_only",
    )


def test_render_deterministic_splits_uses_display_fields() -> None:
    ctx = _ctx_with_splits()
    block = render_deterministic_splits_block(ctx)
    assert block is not None
    assert "mile 1 (lap 1)" in block
    assert "**Moving Time:** 9:48" in block
    assert "**Average Heart Rate:** 127 bpm" in block
    assert "**Average Pace:** 9:48/mi" in block
    assert "mile 2 (lap 2)" in block
    assert "9:45" in block
    assert "138 bpm" in block


def test_render_deterministic_splits_truncation_note() -> None:
    ctx = _ctx_with_splits(truncated=True)
    block = render_deterministic_splits_block(ctx)
    assert block is not None
    assert "middle lap" in block.lower()


def test_compose_splits_turn_content_orders_block_then_coaching() -> None:
    out = compose_splits_turn_content(
        "Here are your splits for the run:\n\n1. mile 1:",
        "Nice steady effort today.",
    )
    assert out.startswith("Here are your splits")
    assert out.endswith("Nice steady effort today.")


def test_splits_coaching_appendix_forbids_per_lap_numbers() -> None:
    ctx = _ctx_with_splits()
    appendix = build_run_review_lab_appendix(
        ctx=ctx,
        coach_snapshot=None,
        scope="splits_only",
        splits_coaching_only=True,
    )
    assert "must NOT list per-lap numbers" in appendix
    assert "exact per-lap table" in appendix
