"""Split-level KPI primitives for execution_analytics."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from src.smartcoach_mobile_coach.execution_analytics.tempo_segment import TempoSplitRow


@dataclass(frozen=True)
class SplitKpiResult:
    easy_pct: float | None
    z2_band_pct: float | None
    hr_drift_pct: float | None
    pace_spread: float | None
    n_hr_splits: int
    n_above_z2_ceiling: int
    n_above_z3_ceiling: int
    n_z3_splits: int
    n_quality_splits: int
    n_z4_splits: int
    n_threshold_quality_splits: int
    median_hr_after_split_1: float | None


def _split_index(row: TempoSplitRow) -> int:
    return row.split_index


def compute_split_kpis(
    splits: list[TempoSplitRow],
    *,
    z2_low: float | None,
    z2_high: float | None,
    z3_low: float | None,
    z3_high: float | None,
    z4_low: float | None,
    z4_high: float | None = None,
    z5_low: float | None = None,
) -> SplitKpiResult:
    hr_splits = [s for s in splits if s.avg_hr is not None and _split_index(s) >= 1]
    n_hr = len(hr_splits)
    if n_hr == 0:
        return SplitKpiResult(
            easy_pct=None,
            z2_band_pct=None,
            hr_drift_pct=None,
            pace_spread=None,
            n_hr_splits=0,
            n_above_z2_ceiling=0,
            n_above_z3_ceiling=0,
            n_z3_splits=0,
            n_quality_splits=0,
            n_z4_splits=0,
            n_threshold_quality_splits=0,
            median_hr_after_split_1=None,
        )

    n_easy = 0
    n_z2_band = 0
    n_above = 0
    n_above_z3 = 0
    n_z3 = 0
    n_quality = 0
    n_z4 = 0
    n_threshold_quality = 0
    pace_values: list[float] = []

    for row in hr_splits:
        hr = float(row.avg_hr)
        if z2_high is not None and hr <= z2_high:
            n_easy += 1
        if z2_low is not None and z2_high is not None and z2_low <= hr <= z2_high:
            n_z2_band += 1
        if z2_high is not None and hr > z2_high:
            n_above += 1
        if z3_high is not None and hr > z3_high:
            n_above_z3 += 1
        if z3_low is not None and z3_high is not None and z3_low <= hr <= z3_high:
            n_z3 += 1
        if z2_high is not None and z4_low is not None and hr > z2_high and hr <= z4_low:
            n_quality += 1
        if z4_low is not None and z4_high is not None and z4_low <= hr <= z4_high:
            n_z4 += 1
        if z3_high is not None and z5_low is not None and hr > z3_high and hr <= z5_low:
            n_threshold_quality += 1
        if row.pace_min_per_mi is not None and row.pace_min_per_mi > 0:
            pace_values.append(float(row.pace_min_per_mi))

    easy_pct = n_easy / n_hr if z2_high is not None else None
    z2_band_pct = (
        n_z2_band / n_hr if z2_low is not None and z2_high is not None else None
    )

    ordered = sorted(hr_splits, key=_split_index)
    half = len(ordered) / 2.0
    early_hrs = [float(s.avg_hr) for s in ordered if _split_index(s) <= half]
    late_hrs = [float(s.avg_hr) for s in ordered if _split_index(s) > half]
    hr_drift_pct: float | None = None
    if early_hrs and late_hrs:
        early_avg = sum(early_hrs) / len(early_hrs)
        late_avg = sum(late_hrs) / len(late_hrs)
        if early_avg > 0:
            hr_drift_pct = round((late_avg - early_avg) / early_avg * 100.0, 2)

    pace_spread: float | None = None
    if len(pace_values) >= 2:
        pace_spread = round(max(pace_values) - min(pace_values), 4)

    after_warmup = [float(s.avg_hr) for s in hr_splits if _split_index(s) > 1]
    median_after_1 = round(median(after_warmup), 2) if after_warmup else None

    return SplitKpiResult(
        easy_pct=round(easy_pct, 4) if easy_pct is not None else None,
        z2_band_pct=round(z2_band_pct, 4) if z2_band_pct is not None else None,
        hr_drift_pct=hr_drift_pct,
        pace_spread=pace_spread,
        n_hr_splits=n_hr,
        n_above_z2_ceiling=n_above,
        n_above_z3_ceiling=n_above_z3,
        n_z3_splits=n_z3,
        n_quality_splits=n_quality,
        n_z4_splits=n_z4,
        n_threshold_quality_splits=n_threshold_quality,
        median_hr_after_split_1=median_after_1,
    )
