from __future__ import annotations

from typing import List

from src.services.training_plan.long_run_spine import (
    generate_long_run_spine,
    validate_phase_quality,
)


def extract_lr(seq: List[dict]) -> List[float]:
    return [float(w.get("long_run_miles", 0)) for w in seq]


def test_spine_from_start_15_matches_expected_sequence():
    weeks = generate_long_run_spine(
        starting_long_run_miles=15.0,
        total_weeks_in_plan=0,  # derive length from policy
        peak_long_run_target=20.0,
        taper_weeks=3,
        cutback_every=3,
    )
    lr = extract_lr(weeks)
    # Expected: build to peak (20), then non-increasing post-peak: 19, 14, 10, 5
    assert lr == [15, 16, 17, 12, 18, 19, 20, 19, 14, 10, 5]


def test_spine_post_peak_is_non_increasing():
    weeks = generate_long_run_spine(
        starting_long_run_miles=14.0,
        total_weeks_in_plan=0,
        peak_long_run_target=20.0,
        taper_weeks=3,
        cutback_every=3,
    )
    lr = extract_lr(weeks)
    peak_idx = lr.index(max(lr))
    tail = lr[peak_idx:]
    assert all(tail[i] >= tail[i + 1] for i in range(len(tail) - 1))


def test_spine_taper_targets():
    weeks = generate_long_run_spine(
        starting_long_run_miles=15.0,
        total_weeks_in_plan=0,
        peak_long_run_target=20.0,
        taper_weeks=3,
        cutback_every=3,
    )
    lr = extract_lr(weeks)
    last3 = lr[-3:]
    # 70/50/25% of 20 rounded to .5 are 14, 10, 5
    assert last3 == [14, 10, 5]


def test_spine_quality_check_passes():
    """Test that quality checks pass for a good spine."""
    weeks = generate_long_run_spine(
        starting_long_run_miles=15.0,
        total_weeks_in_plan=0,
        peak_long_run_target=20.0,
        taper_weeks=3,
        cutback_every=3,
    )
    is_valid, issues = validate_phase_quality(
        weeks, peak=20.0, cutback_every=3, taper_weeks=3
    )
    assert is_valid, f"Quality checks failed: {issues}"
    assert len(issues) == 0
