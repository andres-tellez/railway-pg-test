"""Tests for :mod:`src.services.training_plan.v2.shared_v2.rounding_utils`."""

from src.services.training_plan.v2.shared_v2.rounding_utils import whole_miles_half_up


def test_whole_miles_half_up_python_round_would_have_wrong_peak_lr():
    # Python round(18.5) is 18 (banker's rounding); long-run targets must not collapse.
    assert whole_miles_half_up(18.5) == 19
    assert whole_miles_half_up(19.5) == 20


def test_whole_miles_half_up_non_positive():
    assert whole_miles_half_up(0) == 0
    assert whole_miles_half_up(-1) == 0
