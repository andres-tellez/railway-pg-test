"""Sanity checks for weekly KPI SQL tempo run classification."""

from src.smartcoach_mobile_coach.insights_systems import (
    TEMPO_RUN_MIN_FRACTION_SPLITS_ABOVE_Z2_HIGH,
    TEMPO_RUN_MIN_SPLITS_WITH_HR,
)
from src.smartcoach_mobile_coach.weekly_insights_service import _WEEK_KPIS_SQL


def test_week_kpis_sql_uses_split_majority_for_tempo():
    assert "split_stats" in _WEEK_KPIS_SQL
    assert "split_median_after_warmup" in _WEEK_KPIS_SQL
    assert "median_hr_after_split_1" in _WEEK_KPIS_SQL
    assert "week_runs" in _WEEK_KPIS_SQL
    assert "'tempo'" in _WEEK_KPIS_SQL


def test_week_kpis_sql_interpolates_constants():
    assert str(TEMPO_RUN_MIN_SPLITS_WITH_HR) in _WEEK_KPIS_SQL
    fragment = str(TEMPO_RUN_MIN_FRACTION_SPLITS_ABOVE_Z2_HIGH)
    assert fragment in _WEEK_KPIS_SQL
