"""Weekly threshold segment rollup SQL and service helper."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.smartcoach_mobile_coach.weekly_insights_service import (
    _WEEK_THRESHOLD_SEGMENT_FACTS_SQL,
    _fetch_threshold_week_rollups_batch,
)


def test_threshold_segment_facts_sql_reads_activities_only():
    assert "public.activities" in _WEEK_THRESHOLD_SEGMENT_FACTS_SQL
    assert "insights_system = 'threshold'" in _WEEK_THRESHOLD_SEGMENT_FACTS_SQL
    assert "threshold_segment_pace_min_per_mi" in _WEEK_THRESHOLD_SEGMENT_FACTS_SQL


def test_fetch_threshold_week_rollups_batch():
    session = MagicMock()
    session.execute.return_value.fetchall.return_value = [
        SimpleNamespace(
            run_date=date(2026, 5, 20),
            threshold_segment_pace_min_per_mi=7.1,
            threshold_segment_avg_hr_bpm=166.0,
            threshold_segment_pace_source="splits_hr_z4",
            threshold_segment_confidence="high",
            threshold_segment_split_count=2,
            threshold_qualifying_distance_mi=2.0,
        )
    ]
    week_windows = [(date(2026, 5, 18), date(2026, 5, 24))]
    rollups = _fetch_threshold_week_rollups_batch(
        session,
        "user-id",
        week_windows,
        athlete_id=1,
    )
    count, segment = rollups[date(2026, 5, 18)]
    assert count == 1
    assert segment.threshold_segment_pace_min_per_mi == 7.1
    assert segment.threshold_segment_confidence == "high"
