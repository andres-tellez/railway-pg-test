"""Unit tests for classify_week_temporality and is_future_week.

Covers V1.6 Pre-Phase A 0.2 — single source of truth for past/current/future
week classification. Spec ref: SMARTCOACH_SYSTEM_SPEC_V1.md §6 future-week
payload contract; PHASE_3_IMPLEMENTATION_CHECKLIST 0.2.
"""

from datetime import date, datetime

import pytest

from src.utils.date_helpers import (
    WeekTemporality,
    classify_week_temporality,
    is_future_week,
)


def _tzdata_available() -> bool:
    """Some dev machines (stock Windows Python) lack the tzdata package and
    cannot resolve any IANA timezone, including UTC. CI has tzdata via pip.
    Used to gate the tz-resolution integration tests only."""
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo("UTC")
        return True
    except Exception:
        return False


_TZDATA_REQUIRED = pytest.mark.skipif(
    not _tzdata_available(),
    reason="tzdata not available on this interpreter; tz resolution tests skipped",
)


class TestClassifyWeekTemporality:
    """Basic past/current/future classification with explicit today override."""

    def test_current_week_monday_equals_today(self):
        today = date(2026, 4, 20)  # Monday
        assert classify_week_temporality(today, today=today) == WeekTemporality.CURRENT

    def test_current_week_when_today_is_sunday(self):
        # Sunday is the last day of the calendar week
        week_start = date(2026, 4, 20)  # Monday
        today = date(2026, 4, 26)  # Sunday of same week
        assert (
            classify_week_temporality(week_start, today=today)
            == WeekTemporality.CURRENT
        )

    def test_past_week_ends_one_day_before_today(self):
        last_monday = date(2026, 4, 13)
        today = date(2026, 4, 20)  # Next Monday
        assert (
            classify_week_temporality(last_monday, today=today) == WeekTemporality.PAST
        )

    def test_future_week_starts_one_day_after_today(self):
        next_monday = date(2026, 4, 27)
        today = date(2026, 4, 26)  # Previous Sunday
        assert (
            classify_week_temporality(next_monday, today=today)
            == WeekTemporality.FUTURE
        )

    def test_distant_past_week(self):
        assert (
            classify_week_temporality(date(2020, 1, 6), today=date(2026, 4, 20))
            == WeekTemporality.PAST
        )

    def test_distant_future_week(self):
        assert (
            classify_week_temporality(date(2030, 1, 6), today=date(2026, 4, 20))
            == WeekTemporality.FUTURE
        )


class TestTargetWeekNormalization:
    """Any date within the target week must classify the same way."""

    @pytest.mark.parametrize(
        "day_in_week",
        [
            date(2026, 4, 20),  # Monday
            date(2026, 4, 22),  # Wednesday
            date(2026, 4, 24),  # Friday
            date(2026, 4, 26),  # Sunday
        ],
    )
    def test_any_day_of_current_week_classifies_as_current(self, day_in_week):
        today = date(2026, 4, 22)  # Wednesday of the same week
        assert (
            classify_week_temporality(day_in_week, today=today)
            == WeekTemporality.CURRENT
        )

    def test_iso_string_input(self):
        assert (
            classify_week_temporality("2026-04-20", today=date(2026, 4, 20))
            == WeekTemporality.CURRENT
        )

    def test_iso_string_with_time_input(self):
        assert (
            classify_week_temporality("2026-04-20T12:34:56", today=date(2026, 4, 20))
            == WeekTemporality.CURRENT
        )

    def test_datetime_input(self):
        assert (
            classify_week_temporality(
                datetime(2026, 4, 22, 15, 30), today=date(2026, 4, 20)
            )
            == WeekTemporality.CURRENT
        )

    def test_today_datetime_is_truncated_to_date(self):
        assert (
            classify_week_temporality(
                date(2026, 4, 20), today=datetime(2026, 4, 22, 23, 59)
            )
            == WeekTemporality.CURRENT
        )


class TestBoundaryConditions:
    """Off-by-one traps at week boundaries are the most likely real-world bugs."""

    def test_sunday_is_still_current_not_past(self):
        """Sunday belongs to the week starting the prior Monday, not the next week."""
        week_start = date(2026, 4, 20)
        sunday = date(2026, 4, 26)
        assert (
            classify_week_temporality(week_start, today=sunday)
            == WeekTemporality.CURRENT
        )

    def test_monday_of_next_week_makes_prior_week_past(self):
        prior_week_start = date(2026, 4, 20)
        next_monday = date(2026, 4, 27)
        assert (
            classify_week_temporality(prior_week_start, today=next_monday)
            == WeekTemporality.PAST
        )

    def test_sunday_makes_next_week_still_future(self):
        sunday_now = date(2026, 4, 26)
        next_week_start = date(2026, 4, 27)
        assert (
            classify_week_temporality(next_week_start, today=sunday_now)
            == WeekTemporality.FUTURE
        )


class TestIsFutureWeekPredicate:
    """is_future_week is a thin wrapper — cover each branch once for parity."""

    def test_future_week_returns_true(self):
        assert is_future_week(date(2026, 4, 27), today=date(2026, 4, 26)) is True

    def test_current_week_returns_false(self):
        assert is_future_week(date(2026, 4, 20), today=date(2026, 4, 22)) is False

    def test_past_week_returns_false(self):
        assert is_future_week(date(2026, 4, 13), today=date(2026, 4, 20)) is False


class TestTimezoneIntegration:
    """When today is not provided, user_tz drives the 'today' resolution."""

    @_TZDATA_REQUIRED
    def test_unknown_tz_falls_back_to_utc_without_error(self):
        # The utility must not raise on a bogus tz; UTC fallback is spec'd in
        # timezone_helpers.get_today_date_in_timezone.
        result = classify_week_temporality(date(2020, 1, 6), user_tz="Not/A_Real_Zone")
        assert result == WeekTemporality.PAST

    @_TZDATA_REQUIRED
    def test_no_tz_uses_utc(self):
        result = classify_week_temporality(date(2020, 1, 6))
        assert result == WeekTemporality.PAST


class TestEnumValues:
    """Lock the string values so they can be used as JSON discriminators."""

    def test_enum_string_values(self):
        assert WeekTemporality.PAST.value == "past"
        assert WeekTemporality.CURRENT.value == "current"
        assert WeekTemporality.FUTURE.value == "future"
