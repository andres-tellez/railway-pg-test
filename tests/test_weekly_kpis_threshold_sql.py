"""Sanity checks for weekly KPI SQL threshold / tempo classification."""

from src.smartcoach_mobile_coach.weekly_insights_service import (
    THRESHOLD_MIN_FRACTION_SPLITS_ABOVE_Z2_HIGH,
    THRESHOLD_MIN_SPLITS_WITH_HR,
    _WEEK_KPIS_SQL,
)


def test_week_kpis_sql_uses_split_majority_for_threshold():
    assert "split_stats" in _WEEK_KPIS_SQL
    assert "split_median_after_warmup" in _WEEK_KPIS_SQL
    assert "median_hr_after_split_1" in _WEEK_KPIS_SQL
    assert "week_runs" in _WEEK_KPIS_SQL


def test_week_kpis_sql_interpolates_constants():
    assert str(THRESHOLD_MIN_SPLITS_WITH_HR) in _WEEK_KPIS_SQL
    fragment = str(THRESHOLD_MIN_FRACTION_SPLITS_ABOVE_Z2_HIGH)
    assert fragment in _WEEK_KPIS_SQL
