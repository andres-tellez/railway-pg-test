"""Tests for coach Strava readiness (list-level vs detail enrichment)."""

from __future__ import annotations

import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.db.models.activities import Activity
from src.db.models.strava_sync_status import StravaSyncStatus
from src.services.coach_strava_readiness_service import (
    evaluate_coach_strava_data_readiness,
)


FIXED_USER_UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")
FIXED_USER_ID = str(FIXED_USER_UUID)
FIXED_ATHLETE_ID = 347085
_WIDE_WINDOW = SimpleNamespace(window_after_ts=1, before_ts=2_000_000_000)


@pytest.fixture
def mock_coach_window():
    with patch(
        "src.services.coach_strava_readiness_service.compute_strava_six_week_window",
        return_value=_WIDE_WINDOW,
    ):
        yield


def _add_sync_complete(session, athlete_id: int = FIXED_ATHLETE_ID) -> None:
    session.add(
        StravaSyncStatus(
            user_id=FIXED_USER_ID,
            athlete_id=athlete_id,
            status="complete",
            progress=100.0,
            step="Sync complete",
        )
    )


def test_coach_ready_when_list_summary_present_without_detail_enrichment(
    test_db_session, mock_coach_window
):
    """Established accounts: list-ingest columns suffice for ActivityFetcher."""
    _add_sync_complete(test_db_session)
    test_db_session.add(
        Activity(
            activity_id=900001,
            athlete_id=FIXED_ATHLETE_ID,
            user_id=FIXED_USER_UUID,
            type="Run",
            name="Morning run",
            start_date=datetime(2026, 5, 10, 12, 0, 0),
            distance=5000.0,
            moving_time=1800,
            detail_enriched_at=None,
        )
    )
    test_db_session.commit()

    r = evaluate_coach_strava_data_readiness(
        test_db_session, FIXED_USER_ID, FIXED_ATHLETE_ID
    )
    assert r.coach_data_ready is True
    assert r.pending_detail_enrichment == 1
    assert r.sync_status == "complete"


def test_coach_not_ready_when_summary_incomplete(test_db_session, mock_coach_window):
    _add_sync_complete(test_db_session)
    test_db_session.add(
        Activity(
            activity_id=900002,
            athlete_id=FIXED_ATHLETE_ID,
            user_id=FIXED_USER_UUID,
            type="Run",
            name="Broken row",
            start_date=datetime(2026, 5, 11, 12, 0, 0),
            distance=5000.0,
            moving_time=None,
            detail_enriched_at=None,
        )
    )
    test_db_session.commit()

    r = evaluate_coach_strava_data_readiness(
        test_db_session, FIXED_USER_ID, FIXED_ATHLETE_ID
    )
    assert r.coach_data_ready is False
    assert r.pending_detail_enrichment == 1


def test_coach_ready_uses_conv_distance_when_distance_null(
    test_db_session, mock_coach_window
):
    _add_sync_complete(test_db_session)
    test_db_session.add(
        Activity(
            activity_id=900003,
            athlete_id=FIXED_ATHLETE_ID,
            user_id=FIXED_USER_UUID,
            type="Run",
            name="Converted only",
            start_date=datetime(2026, 5, 12, 12, 0, 0),
            distance=None,
            conv_distance=3.1,
            moving_time=1500,
            detail_enriched_at=None,
        )
    )
    test_db_session.commit()

    r = evaluate_coach_strava_data_readiness(
        test_db_session, FIXED_USER_ID, FIXED_ATHLETE_ID
    )
    assert r.coach_data_ready is True
    assert r.pending_detail_enrichment == 1
