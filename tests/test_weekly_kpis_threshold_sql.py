"""Sanity checks for weekly KPI SQL (activities execution columns)."""

from src.smartcoach_mobile_coach.weekly_insights_service import (
    _USERS_WITH_EASY_RUNS_SQL,
    _WEEK_KPIS_SQL,
    _WEEK_TEMPO_SEGMENT_FACTS_SQL,
)


def test_week_kpis_sql_reads_activities_insights_system():
    assert "public.activities" in _WEEK_KPIS_SQL
    assert "insights_system = 'easy'" in _WEEK_KPIS_SQL
    assert "insights_system = 'tempo'" in _WEEK_KPIS_SQL
    assert "v_easy_runs" not in _WEEK_KPIS_SQL


def test_tempo_segment_facts_sql_reads_stored_columns():
    assert "tempo_segment_pace_min_per_mi" in _WEEK_TEMPO_SEGMENT_FACTS_SQL
    assert "splits" not in _WEEK_TEMPO_SEGMENT_FACTS_SQL.lower()
    assert "v_easy_runs" not in _WEEK_TEMPO_SEGMENT_FACTS_SQL


def test_users_with_easy_runs_sql_uses_insights_system():
    assert "insights_system = 'easy'" in _USERS_WITH_EASY_RUNS_SQL
    assert "v_easy_runs" not in _USERS_WITH_EASY_RUNS_SQL
