"""Unit tests for age-adjusted manual max HR rails."""

from datetime import date

from src.utils.hr_zone_constants import manual_max_hr_bpm_bounds


def test_manual_max_hr_fallback_when_no_birth_year():
    lo, hi = manual_max_hr_bpm_bounds(None)
    assert lo == 120 and hi == 220


def test_manual_max_hr_tanaka_window_midlife():
    # Age 43 on 2020-06-01: birth_year 1977 → age 43; pred round(208 - 30.1) = 178
    lo, hi = manual_max_hr_bpm_bounds(1977, today=date(2020, 6, 1))
    assert lo == max(120, 178 - 35)
    assert hi == min(220, 178 + 35)
    assert lo <= hi


def test_manual_max_hr_older_runner_narrows_below_flat_max():
    # ~70 yo: Tanaka midpoint ~159; hi should be below 220 and reflect age
    lo, hi = manual_max_hr_bpm_bounds(1955, today=date(2025, 6, 1))
    assert lo >= 120
    assert hi <= 220
    assert hi <= 200
