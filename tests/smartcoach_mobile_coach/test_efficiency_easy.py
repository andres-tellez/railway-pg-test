"""Unit tests for easy_kpi aerobic efficiency authority."""

from __future__ import annotations

from src.smartcoach_mobile_coach.easy_kpi.efficiency_easy import (
    DEFAULT_EFFICIENCY_BAND_CONFIG,
    EFFICIENCY_GOAL_DISPLAY,
    build_easy_efficiency_zones_chart,
    classify_easy_efficiency,
    efficiency_zones_chart_api_payload,
    format_efficiency_goal_display,
)
from src.utils.hr_zone_constants import (
    AEROBIC_EFFICIENCY_BANDS,
    aerobic_efficiency_band_from_value,
    aerobic_efficiency_band_zones_chart,
)


def test_efficiency_goal_display():
    assert format_efficiency_goal_display() == EFFICIENCY_GOAL_DISPLAY
    assert EFFICIENCY_GOAL_DISPLAY == "higher is better at the same effort"


def test_classify_easy_efficiency_boundaries():
    cfg = DEFAULT_EFFICIENCY_BAND_CONFIG
    assert classify_easy_efficiency(efficiency=5.0) == "green"
    assert classify_easy_efficiency(efficiency=cfg.green_min) == "green"
    assert classify_easy_efficiency(efficiency=cfg.green_min - 0.01) == "yellow"
    assert classify_easy_efficiency(efficiency=cfg.yellow_min) == "yellow"
    assert classify_easy_efficiency(efficiency=cfg.orange_min) == "orange"
    assert classify_easy_efficiency(efficiency=cfg.orange_min - 0.01) == "red"


def test_hr_zone_constants_delegates_to_easy_kpi():
    assert (
        AEROBIC_EFFICIENCY_BANDS["green_min"]
        == DEFAULT_EFFICIENCY_BAND_CONFIG.green_min
    )
    assert aerobic_efficiency_band_from_value(4.8) == "green"
    assert aerobic_efficiency_band_from_value(3.0) == "red"
    assert aerobic_efficiency_band_zones_chart() == efficiency_zones_chart_api_payload(
        build_easy_efficiency_zones_chart()
    )
