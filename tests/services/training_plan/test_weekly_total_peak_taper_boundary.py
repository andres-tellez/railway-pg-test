"""Peak→Taper weekly total boundary (first taper week vs final peak week)."""

from typing import Any, Dict, List

import pytest

from src.services.training_plan.v2.marathon.weekly_total_calculator_v2 import (
    calculate_weekly_totals_from_long_runs,
    recommend_weekly_total,
)
from src.services.training_plan.v2.race_configs.marathon_config import MarathonConfig


class MarathonWithoutTaperPhaseDelta(MarathonConfig):
    """Marathon config with no Taper entry in phase_delta_caps (exposes boundary-only cap)."""

    @property
    def phase_delta_caps(self) -> Dict[str, float]:
        return {"Base": 0.10, "Build": 0.10, "Peak": 0.05}


def test_recommend_weekly_total_caps_first_taper_after_peak_without_taper_delta():
    cfg = MarathonWithoutTaperPhaseDelta()
    # Prior peak week total; LR-based taper total would stay high without explicit boundary.
    total = recommend_weekly_total(
        long_run=18.0,
        runs_per_week=4,
        config=cfg,
        prev_week_total=50.0,
        prev_phase="Peak",
        phase="Taper",
    )
    assert total <= 45  # 90% of 50
    assert total >= 1


def test_recommend_weekly_total_stricter_ratio_override():
    class StrictMarathon(MarathonWithoutTaperPhaseDelta):
        @property
        def peak_to_taper_first_week_max_ratio(self) -> float:
            return 0.85

    cfg = StrictMarathon()
    total = recommend_weekly_total(
        long_run=18.0,
        runs_per_week=4,
        config=cfg,
        prev_week_total=50.0,
        prev_phase="Peak",
        phase="Taper",
    )
    assert total <= 42  # 85% of 50


def test_peak_prev_triggers_stricter_cap_than_non_peak_prev():
    """Boundary applies only when prev_phase is Peak (not Build/Taper)."""
    cfg = MarathonWithoutTaperPhaseDelta()
    common: Dict[str, Any] = dict(
        long_run=19.0,
        runs_per_week=4,
        config=cfg,
        prev_week_total=50.0,
        phase="Taper",
    )
    after_peak = recommend_weekly_total(**common, prev_phase="Peak")
    after_build = recommend_weekly_total(**common, prev_phase="Build")
    assert after_peak <= 45
    assert after_build >= after_peak


def test_calculate_weekly_totals_first_taper_respects_peak_ceiling():
    weeks: List[Dict[str, Any]] = [
        {
            "week_number": 1,
            "long_run_miles": 10.0,
            "phase": "Base",
            "is_cutback": False,
        },
        {
            "week_number": 2,
            "long_run_miles": 20.0,
            "phase": "Peak",
            "is_cutback": False,
        },
        {
            "week_number": 3,
            "long_run_miles": 18.0,
            "phase": "Taper",
            "is_cutback": False,
        },
    ]
    out = calculate_weekly_totals_from_long_runs(
        weeks=weeks,
        runs_per_week=4,
        config=MarathonWithoutTaperPhaseDelta(),
    )
    peak_total = float(out[1]["weekly_mileage"])
    taper_total = float(out[2]["weekly_mileage"])
    assert taper_total <= peak_total * 0.90 + 0.51  # whole-mile rounding slack


def test_calculate_weekly_totals_taper_week_label_alias():
    weeks: List[Dict[str, Any]] = [
        {
            "week_number": 1,
            "long_run_miles": 20.0,
            "phase": "Peak",
            "is_cutback": False,
        },
        {
            "week_number": 2,
            "long_run_miles": 18.0,
            "phase": "Taper week",
            "is_cutback": False,
        },
    ]
    out = calculate_weekly_totals_from_long_runs(
        weeks=weeks,
        runs_per_week=4,
        config=MarathonWithoutTaperPhaseDelta(),
    )
    peak_total = float(out[0]["weekly_mileage"])
    taper_total = float(out[1]["weekly_mileage"])
    assert taper_total <= peak_total * 0.90 + 0.51
