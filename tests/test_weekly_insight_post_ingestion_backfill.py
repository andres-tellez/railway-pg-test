"""Tests for post-ingestion weekly insight backfill scheduling."""

from __future__ import annotations

import os
from unittest.mock import patch

from src.services.weekly_insight_post_ingestion_backfill import (
    schedule_weekly_insights_after_strava_ingestion,
)


@patch(
    "src.services.weekly_insight_post_ingestion_backfill.schedule_ensure_user_weekly_insights"
)
def test_schedule_calls_reconciler_on_inserts(mock_schedule):
    schedule_weekly_insights_after_strava_ingestion(
        "550e8400-e29b-41d4-a716-446655440000",
        force_full_sync=False,
        inserted_count=2,
    )
    mock_schedule.assert_called_once_with("550e8400-e29b-41d4-a716-446655440000")


@patch(
    "src.services.weekly_insight_post_ingestion_backfill.schedule_ensure_user_weekly_insights"
)
def test_schedule_calls_reconciler_on_force_full_even_if_zero_inserts(mock_schedule):
    schedule_weekly_insights_after_strava_ingestion(
        "550e8400-e29b-41d4-a716-446655440000",
        force_full_sync=True,
        inserted_count=0,
    )
    mock_schedule.assert_called_once()


@patch(
    "src.services.weekly_insight_post_ingestion_backfill.schedule_ensure_user_weekly_insights"
)
def test_schedule_skips_without_user(mock_schedule):
    schedule_weekly_insights_after_strava_ingestion(
        "",
        force_full_sync=True,
        inserted_count=5,
    )
    mock_schedule.assert_not_called()


@patch(
    "src.services.weekly_insight_post_ingestion_backfill.schedule_ensure_user_weekly_insights"
)
def test_schedule_skips_when_no_inserts_and_not_force_full(mock_schedule):
    schedule_weekly_insights_after_strava_ingestion(
        "550e8400-e29b-41d4-a716-446655440000",
        force_full_sync=False,
        inserted_count=0,
    )
    mock_schedule.assert_not_called()


@patch.dict(os.environ, {"WEEKLY_INSIGHT_INGESTION_BACKFILL": "0"})
@patch(
    "src.services.weekly_insight_post_ingestion_backfill.schedule_ensure_user_weekly_insights"
)
def test_schedule_respects_disable_env(mock_schedule):
    schedule_weekly_insights_after_strava_ingestion(
        "550e8400-e29b-41d4-a716-446655440000",
        force_full_sync=True,
        inserted_count=1,
    )
    mock_schedule.assert_not_called()
