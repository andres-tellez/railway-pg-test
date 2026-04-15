"""Unit tests for weekly insight calendar week helpers."""

from datetime import date

from src.smartcoach_mobile_coach.weekly_insights_service import (
    calendar_week_containing,
    _week_bounds,
)


def test_calendar_week_containing_wednesday():
    # 2026-04-15 is a Wednesday
    d = date(2026, 4, 15)
    mon, sun = calendar_week_containing(d)
    assert mon == date(2026, 4, 13)
    assert sun == date(2026, 4, 19)


def test_week_bounds_completed_not_same_as_calendar_midweek():
    d = date(2026, 4, 15)
    mon_c, sun_c = calendar_week_containing(d)
    mon_b, sun_b = _week_bounds(d)
    assert (mon_c, sun_c) != (mon_b, sun_b)
    assert mon_b < mon_c
