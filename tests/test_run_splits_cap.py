"""Tests for get_run_splits row capping (head + tail)."""

from __future__ import annotations

from src.smartcoach_mobile_coach.run_splits import cap_split_rows_for_coach


def test_cap_noop_when_under_limit():
    rows = [{"lap_index": i} for i in range(5)]
    out, truncated, total = cap_split_rows_for_coach(rows, 24)
    assert out == rows
    assert not truncated
    assert total == 5


def test_cap_head_tail_preserves_ends():
    rows = [{"lap_index": i} for i in range(30)]
    out, truncated, total = cap_split_rows_for_coach(rows, 10)
    assert truncated
    assert total == 30
    assert len(out) == 10
    # head (10+1)//2 == 5 first, tail 5 last
    assert [r["lap_index"] for r in out[:5]] == [0, 1, 2, 3, 4]
    assert [r["lap_index"] for r in out[5:]] == [25, 26, 27, 28, 29]


def test_cap_max_rows_two():
    rows = [{"lap_index": i} for i in range(10)]
    out, truncated, total = cap_split_rows_for_coach(rows, 2)
    assert truncated
    assert len(out) == 2
    assert out[0]["lap_index"] == 0
    assert out[1]["lap_index"] == 9
