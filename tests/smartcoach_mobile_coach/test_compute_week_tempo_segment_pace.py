"""Tests for weekly tempo segment rollup from stored activity facts."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.smartcoach_mobile_coach.weekly_insights_service import (
    _WEEK_TEMPO_SEGMENT_FACTS_SQL,
    _compute_week_tempo_segment_pace,
)

USER_ID = "e3362637-9045-4aac-83ed-92bc1f2643b9"


def test_tempo_segment_facts_sql_reads_activities_only():
    assert "public.activities" in _WEEK_TEMPO_SEGMENT_FACTS_SQL
    assert "v_easy_runs" not in _WEEK_TEMPO_SEGMENT_FACTS_SQL
    assert "user_hr_zones" not in _WEEK_TEMPO_SEGMENT_FACTS_SQL


def test_compute_week_tempo_segment_pace_from_stored_run_facts():
    session = MagicMock()
    session.execute.return_value.fetchall.return_value = [
        SimpleNamespace(
            tempo_segment_pace_min_per_mi=8.7967,
            tempo_segment_avg_hr_bpm=147.5,
            tempo_segment_pace_source="splits_hr_z3",
            tempo_segment_confidence="high",
            tempo_segment_split_count=3,
            tempo_qualifying_distance_mi=3.0,
        )
    ]

    result = _compute_week_tempo_segment_pace(
        session,
        USER_ID,
        date(2026, 5, 18),
        date(2026, 5, 24),
        athlete_id=347085,
    )

    assert result.tempo_segment_pace_min_per_mi == 8.7967
    assert result.tempo_segment_pace_source == "splits_hr_z3"
    assert result.tempo_segment_split_count == 3
    assert result.tempo_segment_confidence == "high"


def test_compute_week_tempo_segment_pace_empty_when_no_stored_rows():
    session = MagicMock()
    session.execute.return_value.fetchall.return_value = []

    result = _compute_week_tempo_segment_pace(
        session,
        USER_ID,
        date(2026, 5, 18),
        date(2026, 5, 24),
        athlete_id=347085,
    )

    assert result.tempo_segment_pace_min_per_mi is None
    assert result.tempo_segment_split_count == 0
