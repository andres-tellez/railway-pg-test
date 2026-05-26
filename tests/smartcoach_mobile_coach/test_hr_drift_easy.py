"""Unit tests for easy_kpi HR drift authority."""

from __future__ import annotations

from src.smartcoach_mobile_coach.easy_kpi.hr_drift_easy import (
    DEFAULT_HR_DRIFT_BAND_CONFIG,
    build_easy_hr_drift_zones_chart,
    classify_easy_hr_drift,
    format_hr_drift_target_display,
    hr_drift_zones_chart_api_payload,
)
from src.utils.hr_zone_constants import (
    HR_DRIFT_BANDS,
    hr_drift_band_from_pct,
    hr_drift_band_zones_chart,
)


def test_hr_drift_target_display_matches_bands():
    assert format_hr_drift_target_display() == "under 2.5% ideal, under 5% acceptable"


def test_classify_easy_hr_drift_boundaries():
    cfg = DEFAULT_HR_DRIFT_BAND_CONFIG
    assert classify_easy_hr_drift(drift_pct=0.0) == "green"
    assert classify_easy_hr_drift(drift_pct=cfg.green_max - 0.01) == "green"
    assert classify_easy_hr_drift(drift_pct=cfg.green_max) == "yellow"
    assert classify_easy_hr_drift(drift_pct=cfg.yellow_max - 0.01) == "yellow"
    assert classify_easy_hr_drift(drift_pct=cfg.yellow_max) == "orange"
    assert classify_easy_hr_drift(drift_pct=cfg.orange_max) == "red"


def test_hr_zone_constants_delegates_to_easy_kpi():
    assert HR_DRIFT_BANDS["green_max"] == DEFAULT_HR_DRIFT_BAND_CONFIG.green_max
    assert hr_drift_band_from_pct(1.0) == "green"
    assert hr_drift_band_from_pct(10.0) == "red"
    assert hr_drift_band_zones_chart() == hr_drift_zones_chart_api_payload(
        build_easy_hr_drift_zones_chart()
    )
