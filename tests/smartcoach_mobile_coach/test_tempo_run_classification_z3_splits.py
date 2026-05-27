"""Tempo run SQL classification aligns with profile Z3 split SSOT."""

from __future__ import annotations

from src.smartcoach_mobile_coach.insights_systems import (
    TEMPO_RUN_MIN_SPLITS_WITH_HR,
    TEMPO_RUN_MIN_Z3_SPLITS,
)
from src.smartcoach_mobile_coach.tempo_kpi.tempo_segment_pace import (
    TempoHrZoneBounds,
    TempoSplitRow,
    compute_run_tempo_segment_pace,
    select_qualifying_tempo_splits,
)
from src.smartcoach_mobile_coach.weekly_insights_service import (
    _WEEK_TEMPO_RUN_SPLITS_SQL,
    _tempo_week_classified_runs_sql,
)

# Profile zones matching user e3362637 / activity 18676236641 investigation.
_PROFILE_ZONES = TempoHrZoneBounds(
    z2_high=143.0,
    z3_low=143.0,
    z3_high=155.0,
    z4_low=155.0,
)


def _split(idx: int, hr: float, pace: float) -> TempoSplitRow:
    return TempoSplitRow(
        split_index=idx,
        avg_hr=hr,
        pace_min_per_mi=pace,
        distance_mi=1.0,
    )


def test_tempo_week_sql_includes_profile_z3_split_path():
    sql = _tempo_week_classified_runs_sql()
    assert "profile_split_tiers" in sql
    assert "runner_zone_profiles" in sql
    assert "n_z3_splits" in sql
    assert f">= {TEMPO_RUN_MIN_Z3_SPLITS}" in sql
    assert f">= {TEMPO_RUN_MIN_SPLITS_WITH_HR}" in sql
    assert "profile_split_tiers" in _WEEK_TEMPO_RUN_SPLITS_SQL


def test_mixed_wtc_run_has_three_z3_splits_for_ssot_path():
    """Mirrors activity 18676236641: 3 Z3 miles in an 8-mile W/T/C run."""
    splits = [
        _split(1, 126.9, 9.0),
        _split(2, 142.6, 8.8),
        _split(3, 142.2, 8.7),
        _split(4, 144.5, 8.57),
        _split(5, 144.8, 8.52),
        _split(6, 145.3, 8.41),
        _split(7, 138.2, 9.0),
        _split(8, 137.5, 9.2),
    ]
    qualifying = select_qualifying_tempo_splits(splits, _PROFILE_ZONES)
    assert len(qualifying) == 3
    assert all(q.tier == "z3" for q in qualifying)
    assert len(qualifying) >= TEMPO_RUN_MIN_Z3_SPLITS

    result, _ = compute_run_tempo_segment_pace(splits, _PROFILE_ZONES)
    assert result.tempo_segment_pace_min_per_mi is not None
    assert result.tempo_segment_avg_hr_bpm is not None
    assert result.tempo_segment_pace_source == "splits_hr_z3"
