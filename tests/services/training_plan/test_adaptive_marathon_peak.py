"""Tests for adaptive marathon peak long-run target."""

import pytest

from src.schemas.plan_schema import PrimaryGoal
from src.services.training_plan.v2.marathon.adaptive_marathon_peak import (
    RaceConfigPeakOverride,
    resolve_marathon_adaptive_target_peak_miles,
)
from src.services.training_plan.v2.race_configs.marathon_config import MarathonConfig


@pytest.mark.parametrize(
    "mpw,goal,weeks,expected",
    [
        (30.0, PrimaryGoal.JUST_FINISH.value, 20, 16.5),
        (30.0, PrimaryGoal.TARGET_TIME.value, 20, 17.5),
        (45.0, PrimaryGoal.JUST_FINISH.value, 20, 18.5),
        (45.0, PrimaryGoal.TARGET_TIME.value, 20, 19.5),
        (60.0, PrimaryGoal.JUST_FINISH.value, 20, 20.0),
        (35.0, None, 12, 15.5),
        (50.0, PrimaryGoal.TARGET_TIME.value, 12, 18.0),
    ],
)
def test_resolve_marathon_adaptive_target_peak_miles(
    mpw: float, goal: str | None, weeks: int, expected: float
) -> None:
    got = resolve_marathon_adaptive_target_peak_miles(
        weekly_mileage=mpw,
        primary_goal=goal,
        plan_length_weeks=weeks,
    )
    assert got == pytest.approx(expected, abs=0.01)


def test_race_config_peak_override_pre_taper_below_peak() -> None:
    base = MarathonConfig()
    ov = RaceConfigPeakOverride(base, 16.0)
    assert ov.target_peak_miles == 16.0
    assert ov.pre_taper_cap_miles < ov.target_peak_miles
    assert ov.taper_weeks == base.taper_weeks


def test_raised_peak_low_current_mpw_target_time() -> None:
    caps = MarathonConfig().peak_caps
    got = resolve_marathon_adaptive_target_peak_miles(
        weekly_mileage=37.0,
        primary_goal=PrimaryGoal.TARGET_TIME.value,
        plan_length_weeks=24,
        runs_per_week=5,
        peak_caps=caps,
        target_time="3:40:00",
    )
    assert got == pytest.approx(19.5, abs=0.01)


def test_raised_peak_requires_target_time() -> None:
    caps = MarathonConfig().peak_caps
    with_tt = resolve_marathon_adaptive_target_peak_miles(
        weekly_mileage=37.0,
        primary_goal=PrimaryGoal.TARGET_TIME.value,
        plan_length_weeks=24,
        runs_per_week=5,
        peak_caps=caps,
        target_time="3:40:00",
    )
    without_tt = resolve_marathon_adaptive_target_peak_miles(
        weekly_mileage=37.0,
        primary_goal=PrimaryGoal.TARGET_TIME.value,
        plan_length_weeks=24,
        runs_per_week=5,
        peak_caps=caps,
        target_time=None,
    )
    assert with_tt > without_tt
    assert without_tt == pytest.approx(17.5, abs=0.01)


def test_raised_peak_off_short_plan() -> None:
    caps = MarathonConfig().peak_caps
    short = resolve_marathon_adaptive_target_peak_miles(
        weekly_mileage=37.0,
        primary_goal=PrimaryGoal.TARGET_TIME.value,
        plan_length_weeks=16,
        runs_per_week=5,
        peak_caps=caps,
        target_time="3:40:00",
    )
    long_enough = resolve_marathon_adaptive_target_peak_miles(
        weekly_mileage=37.0,
        primary_goal=PrimaryGoal.TARGET_TIME.value,
        plan_length_weeks=18,
        runs_per_week=5,
        peak_caps=caps,
        target_time="3:40:00",
    )
    assert short == pytest.approx(17.0, abs=0.01)
    assert long_enough == pytest.approx(19.5, abs=0.01)


def test_volume_ceiling_clamps_three_day_runner() -> None:
    caps = MarathonConfig().peak_caps
    got = resolve_marathon_adaptive_target_peak_miles(
        weekly_mileage=30.0,
        primary_goal=PrimaryGoal.TARGET_TIME.value,
        plan_length_weeks=24,
        runs_per_week=3,
        peak_caps=caps,
        target_time="4:00:00",
    )
    assert got == pytest.approx(16.8, abs=0.01)


def test_just_finish_no_raise_even_with_target_time_fields() -> None:
    caps = MarathonConfig().peak_caps
    got = resolve_marathon_adaptive_target_peak_miles(
        weekly_mileage=37.0,
        primary_goal=PrimaryGoal.JUST_FINISH.value,
        plan_length_weeks=24,
        runs_per_week=5,
        peak_caps=caps,
        target_time="3:40:00",
    )
    assert got == pytest.approx(16.5, abs=0.01)
