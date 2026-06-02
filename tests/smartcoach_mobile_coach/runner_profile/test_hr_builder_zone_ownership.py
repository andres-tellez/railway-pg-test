"""Unit tests for post-rounding integer HR zone ownership."""

from __future__ import annotations

import pytest

from src.smartcoach_mobile_coach.runner_profile.hr_builder import (
    apply_integer_zone_ownership,
)
from src.smartcoach_mobile_coach.runner_profile.models import HrZoneBand


def _bands(**kwargs: HrZoneBand) -> dict[str, HrZoneBand]:
    return dict(kwargs)


def test_resolves_adjacent_z2_z3_overlap():
    result = apply_integer_zone_ownership(
        _bands(
            z1=HrZoneBand(90, 109),
            z2=HrZoneBand(110, 123),
            z3=HrZoneBand(123, 142),
            z4=HrZoneBand(142, 155),
            z5=HrZoneBand(155, 174),
        )
    )

    assert result["z1"] == HrZoneBand(90, 109)
    assert result["z2"] == HrZoneBand(110, 123)
    assert result["z3"] == HrZoneBand(124, 142)
    assert result["z4"] == HrZoneBand(143, 155)
    assert result["z5"] == HrZoneBand(156, 174)


def test_preserves_z1_low_and_z5_high():
    result = apply_integer_zone_ownership(
        _bands(
            z1=HrZoneBand(88, 100),
            z2=HrZoneBand(100, 120),
            z5=HrZoneBand(160, 190),
        )
    )

    assert result["z1"].low == 88
    assert result["z5"].high == 190
    assert result["z2"].low == 101


def test_non_overlapping_bands_unchanged():
    bands = _bands(
        z1=HrZoneBand(90, 109),
        z2=HrZoneBand(110, 123),
        z3=HrZoneBand(124, 142),
    )
    assert apply_integer_zone_ownership(bands) == bands


def test_empty_dict_unchanged():
    assert apply_integer_zone_ownership({}) == {}


def test_rejects_invalid_input_band():
    with pytest.raises(ValueError, match="before integer ownership"):
        apply_integer_zone_ownership(_bands(z2=HrZoneBand(130, 120)))


def test_rejects_impossible_overlap_repair():
    with pytest.raises(ValueError, match="after integer ownership"):
        apply_integer_zone_ownership(
            _bands(
                z2=HrZoneBand(120, 123),
                z3=HrZoneBand(123, 123),
            )
        )


def test_no_adjacent_duplicate_integers():
    result = apply_integer_zone_ownership(
        _bands(
            z1=HrZoneBand(90, 109),
            z2=HrZoneBand(110, 123),
            z3=HrZoneBand(123, 142),
            z4=HrZoneBand(142, 155),
            z5=HrZoneBand(155, 174),
        )
    )
    ordered = [result[k] for k in ("z1", "z2", "z3", "z4", "z5")]
    for lower, upper in zip(ordered, ordered[1:]):
        assert lower.high < upper.low
