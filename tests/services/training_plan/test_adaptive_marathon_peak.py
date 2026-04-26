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
