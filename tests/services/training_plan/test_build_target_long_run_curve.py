"""Golden tests for build_target_long_run_curve vs build_long_run_spine_weeks mile lists."""

from datetime import date

import pytest

from src.services.training_plan.v2.race_configs.marathon_config import MarathonConfig
from src.services.training_plan.v2.shared_v2 import long_run_spine_v2 as lr_spine
from src.services.training_plan.v2.shared_v2.long_run_spine_v2 import (
    build_long_run_spine_weeks,
    build_target_long_run_curve,
)


@pytest.fixture
def marathon_cfg() -> MarathonConfig:
    return MarathonConfig()


def test_build_target_long_run_curve_matches_spine_fixed_length_golden(
    marathon_cfg: MarathonConfig,
) -> None:
    """Deterministic fixed-length plan: explicit weeks + race_date (no utcnow path)."""
    start, total_weeks, peak = 10.0, 20, 18.0
    race_date = date(2026, 10, 10)
    expected = [
        10.0,
        11.0,
        12.0,
        13.0,
        11.0,
        12.0,
        13.0,
        14.0,
        12.0,
        13.0,
        14.0,
        15.0,
        13.0,
        16.0,
        16.5,
        18.0,
        17.0,
        12.5,
        9.0,
        5.0,
    ]

    curve = build_target_long_run_curve(
        start,
        total_weeks,
        peak,
        race_date=race_date,
        taper_weeks=3,
        inc_miles=1.0,
        cutback_every=4,
        cutback_factor=0.85,
        peak_offset_before_taper=2,
        config=marathon_cfg,
        unit_system="imperial",
    )
    assert curve == expected

    spine = build_long_run_spine_weeks(
        start,
        total_weeks,
        peak,
        race_date=race_date,
        taper_weeks=3,
        inc_miles=1.0,
        cutback_every=4,
        cutback_factor=0.85,
        peak_offset_before_taper=2,
        config=marathon_cfg,
        unit_system="imperial",
    )
    assert [float(w["long_run_miles"]) for w in spine] == expected


def test_build_target_long_run_curve_matches_spine_dynamic_length_golden(
    marathon_cfg: MarathonConfig,
) -> None:
    """Dynamic mode (total_weeks=0): length derived only from spine policy + config (no race_date)."""
    expected = [
        12.0,
        13.0,
        14.0,
        15.0,
        13.0,
        14.0,
        15.0,
        16.0,
        14.0,
        15.0,
        16.0,
        17.0,
        15.0,
        16.0,
        17.0,
        18.0,
        16.0,
        17.0,
        18.0,
        19.0,
        17.0,
        18.0,
        19.0,
        20.0,
        19.0,
        14.0,
        10.0,
        5.0,
    ]

    curve = build_target_long_run_curve(
        12.0,
        0,
        20.0,
        race_date=None,
        taper_weeks=3,
        inc_miles=1.0,
        cutback_every=4,
        cutback_factor=0.85,
        peak_offset_before_taper=1,
        config=marathon_cfg,
        unit_system="imperial",
    )
    assert curve == expected
    assert len(curve) == 28

    spine = build_long_run_spine_weeks(
        12.0,
        0,
        20.0,
        race_date=None,
        taper_weeks=3,
        inc_miles=1.0,
        cutback_every=4,
        cutback_factor=0.85,
        peak_offset_before_taper=1,
        config=marathon_cfg,
        unit_system="imperial",
    )
    assert [float(w["long_run_miles"]) for w in spine] == expected


def test_stage_e_fixed_curve_invariants(marathon_cfg: MarathonConfig) -> None:
    """Pure fixed curve: length, peak in build, cutback cadence, taper shape."""
    taper_w = 3
    peak_target = 18.0
    curve = build_target_long_run_curve(
        10.0,
        20,
        peak_target,
        race_date=date(2026, 10, 10),
        taper_weeks=taper_w,
        inc_miles=1.0,
        cutback_every=4,
        cutback_factor=0.85,
        peak_offset_before_taper=2,
        config=marathon_cfg,
        unit_system="imperial",
    )
    assert len(curve) == 20
    pre = curve[:-taper_w]
    assert max(pre) >= peak_target - 0.05
    cb = lr_spine._curve_cutback_week_indices(curve, taper_weeks=taper_w)
    assert cb, "expected at least one cutback in build"
    assert cb[0] == 4  # week 5 first deload in golden
    for a, b in zip(cb, cb[1:]):
        assert b - a >= marathon_cfg.cutback_every
    tail = curve[-taper_w:]
    assert all(tail[i] >= tail[i + 1] for i in range(len(tail) - 1))


def test_stage_e_executor_matches_build_target_miles(
    marathon_cfg: MarathonConfig,
) -> None:
    """build_long_run_spine_weeks mile list matches build_target_long_run_curve."""
    args = (10.0, 20, 18.0)
    kw = dict(
        race_date=date(2026, 10, 10),
        taper_weeks=3,
        inc_miles=1.0,
        cutback_every=4,
        cutback_factor=0.85,
        peak_offset_before_taper=2,
        config=marathon_cfg,
        unit_system="imperial",
    )
    curve = build_target_long_run_curve(*args, **kw)
    weeks = build_long_run_spine_weeks(*args, **kw)
    assert [float(w["long_run_miles"]) for w in weeks] == curve
