"""Unit tests for tempo split row parsing from DB result rows."""

from __future__ import annotations

from types import SimpleNamespace

from src.smartcoach_mobile_coach.weekly_insights_service import _tempo_split_row_from_db


def test_tempo_split_row_uses_lap_index_when_split_is_null():
    row = SimpleNamespace(
        split=None,
        lap_index=2,
        average_heartrate=155.0,
        conv_avg_speed=7.5,
        conv_distance=1.0,
        distance=None,
        moving_time=None,
    )
    parsed = _tempo_split_row_from_db(row)
    assert parsed is not None
    assert parsed.split_index == 2
    assert parsed.avg_hr == 155.0
    assert parsed.pace_min_per_mi == 7.5


def test_tempo_split_row_prefers_split_over_lap_index():
    row = SimpleNamespace(
        split=3,
        lap_index=2,
        average_heartrate=150.0,
        conv_avg_speed=7.0,
        conv_distance=1.0,
        distance=None,
        moving_time=None,
    )
    parsed = _tempo_split_row_from_db(row)
    assert parsed is not None
    assert parsed.split_index == 3


def test_tempo_split_row_returns_none_without_index():
    row = SimpleNamespace(
        split=None,
        lap_index=None,
        average_heartrate=150.0,
        conv_avg_speed=7.0,
        conv_distance=1.0,
        distance=None,
        moving_time=None,
    )
    assert _tempo_split_row_from_db(row) is None
