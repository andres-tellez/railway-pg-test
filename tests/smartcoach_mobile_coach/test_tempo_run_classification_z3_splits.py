"""Tempo classification aligns with execution_analytics (Python SSOT)."""

from __future__ import annotations

from src.smartcoach_mobile_coach.execution_analytics.classification import (
    classify_insights_system,
)
from src.smartcoach_mobile_coach.execution_analytics.kpi_primitives import (
    SplitKpiResult,
    compute_split_kpis,
)
from src.smartcoach_mobile_coach.execution_analytics.thresholds import (
    TEMPO_RUN_MIN_SPLITS_WITH_HR,
    TEMPO_RUN_MIN_Z3_SPLITS,
)
from src.smartcoach_mobile_coach.execution_analytics.tempo_segment import (
    TempoHrZoneBounds,
    TempoSplitRow,
    compute_run_tempo_segment_pace,
    select_qualifying_tempo_splits,
)

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


def test_execution_analytics_classifies_tempo_via_z3_split_count():
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
    kpis = compute_split_kpis(
        splits,
        z2_low=124.0,
        z2_high=143.0,
        z3_low=143.0,
        z3_high=155.0,
        z4_low=155.0,
    )
    system = classify_insights_system(
        moving_time_seconds=3600,
        avg_hr=145.0,
        z2_high=143.0,
        kpis=kpis,
    )
    assert system == "tempo"
    assert kpis.n_z3_splits >= TEMPO_RUN_MIN_Z3_SPLITS


def test_easy_run_not_classified_when_easy_pct_high():
    kpis = SplitKpiResult(
        easy_pct=0.85,
        z2_band_pct=0.8,
        hr_drift_pct=5.0,
        pace_spread=0.5,
        n_hr_splits=4,
        n_above_z2_ceiling=0,
        n_z3_splits=0,
        n_quality_splits=0,
        median_hr_after_split_1=None,
    )
    assert (
        classify_insights_system(
            moving_time_seconds=3600,
            avg_hr=130.0,
            z2_high=143.0,
            kpis=kpis,
        )
        == "easy"
    )
