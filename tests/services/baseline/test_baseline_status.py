"""
Unit tests for ``src.services.baseline.baseline_status`` (V1.6 §12,
Phase A item 4).

Locks the deterministic three-band classification so:
  * the enum wire values and cascade ordering cannot silently drift,
  * the bucket helper correctly counts distinct 7-day windows
    (including same-day, boundary, and out-of-window cases),
  * the DAO-backed adapter queries the correct athlete + window and
    maps query results into the pure classifier.

The adapter test uses the shared in-memory SQLite session fixture
so it exercises the real SQL path rather than a mock.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

import pytest

from src.db.models.activities import Activity
from src.services.baseline.baseline_status import (
    BASELINE_WINDOW_DAYS,
    BASELINE_WINDOW_WEEKS,
    BaselineStatus,
    classify_baseline_status,
    compute_baseline_status_for_athlete,
    count_runs_and_weeks_in_window,
)


# ---------------------------------------------------------------------------
# Constants + enum wire contract.
# ---------------------------------------------------------------------------


class TestEnumAndConstants:
    def test_enum_wire_values(self):
        assert BaselineStatus.INSUFFICIENT.value == "insufficient"
        assert BaselineStatus.THIN.value == "thin"
        assert BaselineStatus.STRONG.value == "strong"

    def test_enum_is_str_based_for_json(self):
        import json

        assert json.dumps(BaselineStatus.STRONG.value) == '"strong"'

    def test_window_constants(self):
        assert BASELINE_WINDOW_DAYS == 28
        assert BASELINE_WINDOW_WEEKS == 4

    def test_exactly_three_values(self):
        """Contract: the enum has exactly the three values mandated
        by spec §12. Adding a fourth silently would reshape the
        coach's tone decisions in §19 — lock it."""
        assert len(list(BaselineStatus)) == 3


# ---------------------------------------------------------------------------
# Pure classifier — cascade matrix.
# ---------------------------------------------------------------------------


class TestClassifyBaselineStatusCascade:
    """Every branch of the three-band cascade (§12)."""

    # ---- insufficient: weeks < 2 OR runs < 3 --------------------------
    def test_zero_weeks_zero_runs_is_insufficient(self):
        assert (
            classify_baseline_status(
                runs_in_last_4_weeks=0, weeks_with_runs_in_last_4=0
            )
            is BaselineStatus.INSUFFICIENT
        )

    def test_one_week_many_runs_is_insufficient(self):
        """1 week of data alone → insufficient, regardless of run count.
        Spec: weeks < 2 OR runs < 3."""
        assert (
            classify_baseline_status(
                runs_in_last_4_weeks=10, weeks_with_runs_in_last_4=1
            )
            is BaselineStatus.INSUFFICIENT
        )

    def test_four_weeks_two_runs_is_insufficient(self):
        """Runs < 3 → insufficient even with a full 4-week window —
        ordering-sensitive (must be caught before strong's AND)."""
        assert (
            classify_baseline_status(
                runs_in_last_4_weeks=2, weeks_with_runs_in_last_4=4
            )
            is BaselineStatus.INSUFFICIENT
        )

    def test_two_runs_is_insufficient_regardless(self):
        """Boundary: exactly 2 runs is still insufficient (spec '< 3')."""
        assert (
            classify_baseline_status(
                runs_in_last_4_weeks=2, weeks_with_runs_in_last_4=2
            )
            is BaselineStatus.INSUFFICIENT
        )

    # ---- strong: weeks >= 4 AND runs >= 6 ------------------------------
    def test_four_weeks_six_runs_is_strong(self):
        """Boundary: exactly 4 weeks + 6 runs → strong (spec inequalities
        are ≥, not >)."""
        assert (
            classify_baseline_status(
                runs_in_last_4_weeks=6, weeks_with_runs_in_last_4=4
            )
            is BaselineStatus.STRONG
        )

    def test_four_weeks_many_runs_is_strong(self):
        assert (
            classify_baseline_status(
                runs_in_last_4_weeks=20, weeks_with_runs_in_last_4=4
            )
            is BaselineStatus.STRONG
        )

    def test_four_weeks_five_runs_is_thin_not_strong(self):
        """Runs < 6 AND weeks = 4 → thin (strong needs the AND)."""
        assert (
            classify_baseline_status(
                runs_in_last_4_weeks=5, weeks_with_runs_in_last_4=4
            )
            is BaselineStatus.THIN
        )

    def test_three_weeks_many_runs_is_thin_not_strong(self):
        """Weeks < 4 → not strong even with many runs."""
        assert (
            classify_baseline_status(
                runs_in_last_4_weeks=12, weeks_with_runs_in_last_4=3
            )
            is BaselineStatus.THIN
        )

    # ---- thin: the middle band -----------------------------------------
    def test_two_weeks_three_runs_is_thin(self):
        """Boundary: exactly 2 weeks + 3 runs passes insufficient and
        lands in thin."""
        assert (
            classify_baseline_status(
                runs_in_last_4_weeks=3, weeks_with_runs_in_last_4=2
            )
            is BaselineStatus.THIN
        )

    def test_three_weeks_five_runs_is_thin(self):
        assert (
            classify_baseline_status(
                runs_in_last_4_weeks=5, weeks_with_runs_in_last_4=3
            )
            is BaselineStatus.THIN
        )


class TestClassifyBaselineStatusDefensiveClamping:
    """Negative/out-of-range inputs must not crash the coach."""

    def test_negative_runs_treated_as_zero(self):
        assert (
            classify_baseline_status(
                runs_in_last_4_weeks=-5, weeks_with_runs_in_last_4=4
            )
            is BaselineStatus.INSUFFICIENT
        )

    def test_negative_weeks_treated_as_zero(self):
        assert (
            classify_baseline_status(
                runs_in_last_4_weeks=10, weeks_with_runs_in_last_4=-1
            )
            is BaselineStatus.INSUFFICIENT
        )

    def test_weeks_above_cap_is_clamped(self):
        """Caller bug: weeks > 4. Clamp to 4 so strong remains reachable
        rather than silently falling through to thin."""
        assert (
            classify_baseline_status(
                runs_in_last_4_weeks=6, weeks_with_runs_in_last_4=99
            )
            is BaselineStatus.STRONG
        )


# ---------------------------------------------------------------------------
# Pure helper: count_runs_and_weeks_in_window.
# ---------------------------------------------------------------------------


class TestCountRunsAndWeeks:
    TODAY = date(2026, 4, 21)  # Tuesday

    def test_empty_iterable_returns_zero_zero(self):
        assert count_runs_and_weeks_in_window([], today=self.TODAY) == (0, 0)

    def test_same_day_run_counts_in_bucket_zero(self):
        runs, weeks = count_runs_and_weeks_in_window([self.TODAY], today=self.TODAY)
        assert (runs, weeks) == (1, 1)

    def test_run_exactly_7_days_ago_counts_in_bucket_1(self):
        """day_offset = 7 → bucket = 1 (boundary at the week edge)."""
        d = self.TODAY - timedelta(days=7)
        runs, weeks = count_runs_and_weeks_in_window([d], today=self.TODAY)
        assert (runs, weeks) == (1, 1)

    def test_run_27_days_ago_is_still_in_window(self):
        """Inclusive bound: exactly 27 days back sits in bucket 3."""
        d = self.TODAY - timedelta(days=27)
        runs, weeks = count_runs_and_weeks_in_window([d], today=self.TODAY)
        assert (runs, weeks) == (1, 1)

    def test_run_28_days_ago_is_excluded(self):
        """Earliest in window = today - 27 days. 28 days ago is stale."""
        d = self.TODAY - timedelta(days=28)
        runs, weeks = count_runs_and_weeks_in_window([d], today=self.TODAY)
        assert (runs, weeks) == (0, 0)

    def test_future_dated_run_is_excluded(self):
        """Defensive: a future-dated activity (clock skew / bad import)
        must not count toward the baseline — spec window is 'last 4
        weeks' not 'last 4 weeks ± clock error'."""
        d = self.TODAY + timedelta(days=1)
        runs, weeks = count_runs_and_weeks_in_window([d], today=self.TODAY)
        assert (runs, weeks) == (0, 0)

    def test_none_dates_skipped(self):
        runs, weeks = count_runs_and_weeks_in_window(
            [None, self.TODAY, None], today=self.TODAY
        )
        assert (runs, weeks) == (1, 1)

    def test_multiple_runs_same_bucket_count_once_for_weeks(self):
        """3 runs in the same 7-day bucket → runs=3, weeks=1."""
        dates = [
            self.TODAY,
            self.TODAY - timedelta(days=1),
            self.TODAY - timedelta(days=3),
        ]
        runs, weeks = count_runs_and_weeks_in_window(dates, today=self.TODAY)
        assert (runs, weeks) == (3, 1)

    def test_one_run_per_bucket_gives_weeks_4(self):
        """Runs at day-offsets 0, 7, 14, 21 → 4 distinct buckets."""
        dates = [self.TODAY - timedelta(days=d) for d in (0, 7, 14, 21)]
        runs, weeks = count_runs_and_weeks_in_window(dates, today=self.TODAY)
        assert (runs, weeks) == (4, 4)

    def test_mix_of_in_window_and_stale_runs(self):
        dates = [
            self.TODAY,  # bucket 0
            self.TODAY - timedelta(days=10),  # bucket 1
            self.TODAY - timedelta(days=40),  # stale (excluded)
        ]
        runs, weeks = count_runs_and_weeks_in_window(dates, today=self.TODAY)
        assert (runs, weeks) == (2, 2)


# ---------------------------------------------------------------------------
# Integration: DAO-backed adapter against in-memory SQLite.
# ---------------------------------------------------------------------------


TEST_ATHLETE_ID = 54321
OTHER_ATHLETE_ID = 99999
DEFAULT_USER_UUID = UUID("00000000-0000-0000-0000-000000000042")


def _make_activity(
    *, athlete_id: int, start_dt: datetime, activity_id: int
) -> Activity:
    return Activity(
        activity_id=activity_id,
        athlete_id=athlete_id,
        user_id=DEFAULT_USER_UUID,
        name=f"Run {activity_id}",
        type="Run",
        start_date=start_dt,
    )


class TestAdapterAgainstSeededActivities:
    """
    End-to-end test: seed activities at known dates, call the adapter
    with a fixed ``today``, assert the classification.
    """

    TODAY = date(2026, 4, 21)

    def test_no_activities_is_insufficient(self, test_db_session):
        status = compute_baseline_status_for_athlete(
            test_db_session, TEST_ATHLETE_ID, today=self.TODAY
        )
        assert status is BaselineStatus.INSUFFICIENT

    def test_one_run_is_insufficient(self, test_db_session):
        test_db_session.add(
            _make_activity(
                athlete_id=TEST_ATHLETE_ID,
                start_dt=datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc),
                activity_id=1001,
            )
        )
        test_db_session.commit()
        status = compute_baseline_status_for_athlete(
            test_db_session, TEST_ATHLETE_ID, today=self.TODAY
        )
        assert status is BaselineStatus.INSUFFICIENT

    def test_three_runs_across_two_weeks_is_thin(self, test_db_session):
        """3 runs spanning 2 distinct 7-day buckets → thin
        (crosses the insufficient threshold on both axes)."""
        for i, day_offset in enumerate([0, 1, 8]):
            test_db_session.add(
                _make_activity(
                    athlete_id=TEST_ATHLETE_ID,
                    start_dt=datetime.combine(
                        self.TODAY - timedelta(days=day_offset),
                        datetime.min.time(),
                        tzinfo=timezone.utc,
                    ),
                    activity_id=2000 + i,
                )
            )
        test_db_session.commit()
        status = compute_baseline_status_for_athlete(
            test_db_session, TEST_ATHLETE_ID, today=self.TODAY
        )
        assert status is BaselineStatus.THIN

    def test_six_runs_across_four_weeks_is_strong(self, test_db_session):
        """6 runs, one in each of the 4 buckets plus extras → strong."""
        for i, day_offset in enumerate([0, 2, 8, 10, 16, 23]):
            test_db_session.add(
                _make_activity(
                    athlete_id=TEST_ATHLETE_ID,
                    start_dt=datetime.combine(
                        self.TODAY - timedelta(days=day_offset),
                        datetime.min.time(),
                        tzinfo=timezone.utc,
                    ),
                    activity_id=3000 + i,
                )
            )
        test_db_session.commit()
        status = compute_baseline_status_for_athlete(
            test_db_session, TEST_ATHLETE_ID, today=self.TODAY
        )
        assert status is BaselineStatus.STRONG

    def test_adapter_filters_by_athlete(self, test_db_session):
        """Runs belonging to a different athlete must not inflate the
        target athlete's baseline."""
        for i, day_offset in enumerate([0, 2, 8, 10, 16, 23]):
            test_db_session.add(
                _make_activity(
                    athlete_id=OTHER_ATHLETE_ID,
                    start_dt=datetime.combine(
                        self.TODAY - timedelta(days=day_offset),
                        datetime.min.time(),
                        tzinfo=timezone.utc,
                    ),
                    activity_id=4000 + i,
                )
            )
        test_db_session.commit()
        status = compute_baseline_status_for_athlete(
            test_db_session, TEST_ATHLETE_ID, today=self.TODAY
        )
        assert status is BaselineStatus.INSUFFICIENT

    def test_adapter_excludes_stale_activities_outside_window(self, test_db_session):
        """A runner with great history 40+ days ago but nothing recent
        must downgrade to insufficient, matching spec §12's 4-week
        window. Without this filter, a returning runner would be
        misclassified as strong."""
        for i, day_offset in enumerate([40, 45, 50, 60, 70, 80]):
            test_db_session.add(
                _make_activity(
                    athlete_id=TEST_ATHLETE_ID,
                    start_dt=datetime.combine(
                        self.TODAY - timedelta(days=day_offset),
                        datetime.min.time(),
                        tzinfo=timezone.utc,
                    ),
                    activity_id=5000 + i,
                )
            )
        test_db_session.commit()
        status = compute_baseline_status_for_athlete(
            test_db_session, TEST_ATHLETE_ID, today=self.TODAY
        )
        assert status is BaselineStatus.INSUFFICIENT

    def test_adapter_excludes_non_run_activity_types(self, test_db_session):
        """Rides / swims must not count toward the running baseline —
        §12 explicitly measures 'run history'."""
        for i, day_offset in enumerate([0, 2, 8, 10, 16, 23]):
            act = _make_activity(
                athlete_id=TEST_ATHLETE_ID,
                start_dt=datetime.combine(
                    self.TODAY - timedelta(days=day_offset),
                    datetime.min.time(),
                    tzinfo=timezone.utc,
                ),
                activity_id=6000 + i,
            )
            act.type = "Ride"
            test_db_session.add(act)
        test_db_session.commit()
        status = compute_baseline_status_for_athlete(
            test_db_session, TEST_ATHLETE_ID, today=self.TODAY
        )
        assert status is BaselineStatus.INSUFFICIENT

    def test_adapter_default_today_does_not_crash(self, test_db_session):
        """Smoke test: omitting ``today`` falls back to ``utcnow``.
        With zero seeded activities for the target athlete, result
        is insufficient regardless of the clock."""
        status = compute_baseline_status_for_athlete(test_db_session, TEST_ATHLETE_ID)
        assert status is BaselineStatus.INSUFFICIENT
