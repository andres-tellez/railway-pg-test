"""Golden tests for build_target_long_run_curve vs build_long_run_spine_weeks mile lists."""

from datetime import date

import pytest

from src.services.training_plan.v2.race_configs.marathon_config import MarathonConfig
from src.services.training_plan.v2.shared_v2 import long_run_spine_v2 as lr_spine
from src.services.training_plan.v2.shared_v2.long_run_spine_v2 import (
    LR_CURVE_SOURCE_ENV,
    build_long_run_spine_weeks,
    build_target_long_run_curve,
    lr_curve_source_name,
)


@pytest.fixture
def marathon_cfg() -> MarathonConfig:
    return MarathonConfig()


def test_build_target_long_run_curve_matches_spine_fixed_length_golden(
    marathon_cfg: MarathonConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deterministic fixed-length plan: explicit weeks + race_date (no utcnow path)."""
    monkeypatch.delenv(LR_CURVE_SOURCE_ENV, raising=False)
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
        17.0,
        18.0,
        13.5,
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
    marathon_cfg: MarathonConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dynamic mode (total_weeks=0): length derived only from spine policy + config (no race_date)."""
    monkeypatch.delenv(LR_CURVE_SOURCE_ENV, raising=False)
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


def test_stage_d_default_env_uses_curve_source(
    marathon_cfg: MarathonConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(LR_CURVE_SOURCE_ENV, raising=False)
    assert lr_curve_source_name(marathon_cfg) == "curve"
    assert lr_curve_source_name(None) == "curve"


def test_stage_d_legacy_env_override(
    marathon_cfg: MarathonConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(LR_CURVE_SOURCE_ENV, "legacy")
    assert lr_curve_source_name(marathon_cfg) == "legacy"


def test_stage_d_config_lr_curve_source_overrides_env(
    marathon_cfg: MarathonConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(LR_CURVE_SOURCE_ENV, "curve")
    marathon_cfg.lr_curve_source = "legacy"
    assert lr_curve_source_name(marathon_cfg) == "legacy"


def test_stage_d_golden_parity_curve_vs_legacy_executor(
    marathon_cfg: MarathonConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Primary curve path and legacy spine path produce identical mile lists (golden)."""
    monkeypatch.delenv(LR_CURVE_SOURCE_ENV, raising=False)
    start, total_weeks, peak = 10.0, 20, 18.0
    race_date = date(2026, 10, 10)
    kw = dict(
        race_date=race_date,
        taper_weeks=3,
        inc_miles=1.0,
        cutback_every=4,
        cutback_factor=0.85,
        peak_offset_before_taper=2,
        config=marathon_cfg,
        unit_system="imperial",
    )
    curve_miles = build_long_run_spine_weeks(start, total_weeks, peak, **kw)
    curve_list = [float(w["long_run_miles"]) for w in curve_miles]

    monkeypatch.setenv(LR_CURVE_SOURCE_ENV, "legacy")
    legacy_miles = build_long_run_spine_weeks(start, total_weeks, peak, **kw)
    legacy_list = [float(w["long_run_miles"]) for w in legacy_miles]
    assert legacy_list == curve_list


def test_stage_c_use_global_curve_matches_legacy_golden(
    marathon_cfg: MarathonConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Default curve path matches legacy golden (Stage C2 / D)."""
    monkeypatch.delenv(LR_CURVE_SOURCE_ENV, raising=False)
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
        17.0,
        18.0,
        13.5,
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


def test_stage_c2_pure_matches_legacy_fixed_golden(
    marathon_cfg: MarathonConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pure curve path matches legacy spine for fixed-length golden."""
    start, total_weeks, peak = 10.0, 20, 18.0
    race_date = date(2026, 10, 10)
    kw = dict(
        race_date=race_date,
        taper_weeks=3,
        inc_miles=1.0,
        cutback_every=4,
        cutback_factor=0.85,
        peak_offset_before_taper=2,
        config=marathon_cfg,
        unit_system="imperial",
    )
    monkeypatch.setenv(LR_CURVE_SOURCE_ENV, "legacy")
    legacy = build_target_long_run_curve(start, total_weeks, peak, **kw)
    monkeypatch.delenv(LR_CURVE_SOURCE_ENV, raising=False)
    pure = build_target_long_run_curve(start, total_weeks, peak, **kw)
    assert pure == legacy


def test_stage_c2_pure_matches_legacy_dynamic_golden(
    marathon_cfg: MarathonConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pure curve path matches legacy for dynamic-length golden."""
    kw = dict(
        race_date=None,
        taper_weeks=3,
        inc_miles=1.0,
        cutback_every=4,
        cutback_factor=0.85,
        peak_offset_before_taper=1,
        config=marathon_cfg,
        unit_system="imperial",
    )
    monkeypatch.setenv(LR_CURVE_SOURCE_ENV, "legacy")
    legacy = build_target_long_run_curve(12.0, 0, 20.0, **kw)
    monkeypatch.delenv(LR_CURVE_SOURCE_ENV, raising=False)
    pure = build_target_long_run_curve(12.0, 0, 20.0, **kw)
    assert pure == legacy
    assert len(pure) == 28


def test_stage_c2_fixed_curve_invariants(
    marathon_cfg: MarathonConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pure fixed curve: length, peak in build, cutback cadence, taper shape."""
    monkeypatch.delenv(LR_CURVE_SOURCE_ENV, raising=False)
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


def test_stage_c2_executor_matches_pure_miles(
    marathon_cfg: MarathonConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """build_long_run_spine_weeks (curve path) matches build_target miles."""
    monkeypatch.delenv(LR_CURVE_SOURCE_ENV, raising=False)
    args = (
        10.0,
        20,
        18.0,
    )
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
