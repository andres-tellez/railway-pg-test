"""F2 Step 1: week-over-week weekly mileage smoothing (recommend_weekly_total only)."""

import json
import logging
from unittest.mock import patch

import pytest

from src.services.training_plan.v2.marathon import weekly_total_calculator_v2 as wcalc
from src.services.training_plan.v2.marathon.weekly_total_calculator_v2 import (
    recommend_weekly_total,
)
from src.services.training_plan.v2.race_configs.marathon_config import MarathonConfig


@pytest.fixture
def marathon_cfg() -> MarathonConfig:
    return MarathonConfig()


def test_f2_smoothing_no_bind_when_lr_anchor_inside_band(
    marathon_cfg: MarathonConfig,
) -> None:
    """LR anchor already within ±ramp / −12% of prev week → smoothing does not move total."""
    wcalc.logger.setLevel(logging.DEBUG)
    with patch.object(wcalc.logger, "debug", wraps=wcalc.logger.debug) as spy:
        total = recommend_weekly_total(
            long_run=15.2,
            runs_per_week=4,
            config=marathon_cfg,
            prev_week_total=40.0,
            phase="Build",
            weeks_before_first_taper=10,
            week_number=5,
        )
        assert total == 38
        trace_json = next(
            (
                c.args[1]
                for c in spy.call_args_list
                if len(c.args) >= 2
                and isinstance(c.args[1], str)
                and "weekly_total_trace" in c.args[1]
            ),
            "",
        )
    assert trace_json
    payload = json.loads(trace_json)
    assert payload["smoothing_applied"] is False
    assert payload["smoothing_max_up"] == pytest.approx(40.0 * 1.08)
    assert payload["smoothing_max_down"] == pytest.approx(40.0 * 0.88)
    assert payload["total_before_weekly_smoothing"] == pytest.approx(38.0)
    assert payload["total_after_weekly_smoothing"] == pytest.approx(38.0)


def test_f2_smoothing_ramp_caps_large_jump_at_weekly_increase_cap(
    marathon_cfg: MarathonConfig,
) -> None:
    """LR-only anchor above prev*(1+cap) → smoothed down to ramp cap (then rounding)."""
    total = recommend_weekly_total(
        long_run=20.0,
        runs_per_week=4,
        config=marathon_cfg,
        prev_week_total=30.0,
        phase="Build",
        weeks_before_first_taper=10,
    )
    assert total <= round(30.0 * (1 + marathon_cfg.weekly_increase_cap))
    assert total == 32


def test_f2_smoothing_downward_limits_drop_to_twelve_percent(
    marathon_cfg: MarathonConfig,
) -> None:
    """Very low LR anchor vs high prev week → total floored at prev*(1−0.12)."""
    total = recommend_weekly_total(
        long_run=8.0,
        runs_per_week=4,
        config=marathon_cfg,
        prev_week_total=50.0,
        phase="Build",
        weeks_before_first_taper=10,
    )
    floor = 50.0 * (1 - 0.12)
    assert total >= int(floor)  # whole miles
    assert total == 44
