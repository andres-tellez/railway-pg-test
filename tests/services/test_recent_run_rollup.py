"""Tests for recent run rollup (Strava status / coach signals)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from src.db.models.activities import Activity
from src.services.recent_run_rollup import compute_recent_run_rollup_for_user

DEFAULT_USER_UUID = UUID("00000000-0000-0000-0000-000000000042")
TEST_ATHLETE_ID = 77777
TODAY = date(2026, 4, 21)


def _run(*, day_offset: int, activity_id: int, distance_m: float | None) -> Activity:
    return Activity(
        activity_id=activity_id,
        athlete_id=TEST_ATHLETE_ID,
        user_id=DEFAULT_USER_UUID,
        name=f"Run {activity_id}",
        type="Run",
        start_date=datetime.combine(
            TODAY - timedelta(days=day_offset),
            datetime.min.time(),
            tzinfo=timezone.utc,
        ),
        distance=distance_m,
    )


class TestRecentRunRollup:
    def test_empty_is_zeros_and_null_longest(self, test_db_session):
        out = compute_recent_run_rollup_for_user(
            test_db_session, DEFAULT_USER_UUID, today=TODAY
        )
        assert out == {
            "runs_28d": 0,
            "weeks_with_runs_28d": 0,
            "longest_run_meters_28d": None,
        }

    def test_counts_runs_and_weeks_and_longest(self, test_db_session):
        test_db_session.add(_run(day_offset=0, activity_id=1, distance_m=5000.0))
        test_db_session.add(_run(day_offset=8, activity_id=2, distance_m=10_000.0))
        test_db_session.commit()
        out = compute_recent_run_rollup_for_user(
            test_db_session, DEFAULT_USER_UUID, today=TODAY
        )
        assert out["runs_28d"] == 2
        assert out["weeks_with_runs_28d"] == 2
        assert out["longest_run_meters_28d"] == 10_000.0

    def test_ignores_other_users(self, test_db_session):
        other = UUID("00000000-0000-0000-0000-000000000099")
        test_db_session.add(
            Activity(
                activity_id=1,
                athlete_id=TEST_ATHLETE_ID,
                user_id=other,
                name="Run",
                type="Run",
                start_date=datetime.combine(
                    TODAY, datetime.min.time(), tzinfo=timezone.utc
                ),
                distance=5000.0,
            )
        )
        test_db_session.commit()
        out = compute_recent_run_rollup_for_user(
            test_db_session, DEFAULT_USER_UUID, today=TODAY
        )
        assert out["runs_28d"] == 0

    def test_ignores_non_run_type(self, test_db_session):
        test_db_session.add(
            Activity(
                activity_id=1,
                athlete_id=TEST_ATHLETE_ID,
                user_id=DEFAULT_USER_UUID,
                name="Ride",
                type="Ride",
                start_date=datetime.combine(
                    TODAY, datetime.min.time(), tzinfo=timezone.utc
                ),
                distance=20_000.0,
            )
        )
        test_db_session.commit()
        out = compute_recent_run_rollup_for_user(
            test_db_session, DEFAULT_USER_UUID, today=TODAY
        )
        assert out["runs_28d"] == 0

    def test_runs_without_distance_yield_null_longest(self, test_db_session):
        test_db_session.add(_run(day_offset=0, activity_id=1, distance_m=None))
        test_db_session.commit()
        out = compute_recent_run_rollup_for_user(
            test_db_session, DEFAULT_USER_UUID, today=TODAY
        )
        assert out["runs_28d"] == 1
        assert out["longest_run_meters_28d"] is None
