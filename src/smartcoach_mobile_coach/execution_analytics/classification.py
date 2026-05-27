"""Insights system classification (easy / tempo) from profile zones + split KPIs."""

from __future__ import annotations

from src.smartcoach_mobile_coach.execution_analytics.kpi_primitives import (
    SplitKpiResult,
)
from src.smartcoach_mobile_coach.execution_analytics.thresholds import (
    MIN_EASY_PCT,
    MIN_RUN_DURATION_SECONDS,
    TEMPO_RUN_MIN_FRACTION_SPLITS_ABOVE_Z2_HIGH,
    TEMPO_RUN_MIN_SPLITS_WITH_HR,
    TEMPO_RUN_MIN_Z3_SPLITS,
)


def is_easy_run(
    *,
    moving_time_seconds: int | None,
    easy_pct: float | None,
    z2_high: float | None,
) -> bool:
    if moving_time_seconds is None or moving_time_seconds < MIN_RUN_DURATION_SECONDS:
        return False
    if easy_pct is None or z2_high is None:
        return False
    return easy_pct >= MIN_EASY_PCT


def classify_insights_system(
    *,
    moving_time_seconds: int | None,
    avg_hr: float | None,
    z2_high: float | None,
    kpis: SplitKpiResult,
) -> str | None:
    if is_easy_run(
        moving_time_seconds=moving_time_seconds,
        easy_pct=kpis.easy_pct,
        z2_high=z2_high,
    ):
        return "easy"

    if moving_time_seconds is None or moving_time_seconds < MIN_RUN_DURATION_SECONDS:
        return None
    if kpis.easy_pct is None or kpis.easy_pct >= MIN_EASY_PCT:
        return None

    if kpis.n_z3_splits >= TEMPO_RUN_MIN_Z3_SPLITS:
        return "tempo"

    if kpis.n_z3_splits == 0 and kpis.n_quality_splits >= TEMPO_RUN_MIN_SPLITS_WITH_HR:
        return "tempo"

    if z2_high is not None:
        if avg_hr is not None and avg_hr > z2_high:
            return "tempo"
        if kpis.n_hr_splits >= TEMPO_RUN_MIN_SPLITS_WITH_HR:
            frac_above = kpis.n_above_z2_ceiling / kpis.n_hr_splits
            if frac_above >= TEMPO_RUN_MIN_FRACTION_SPLITS_ABOVE_Z2_HIGH:
                return "tempo"
            if (
                kpis.median_hr_after_split_1 is not None
                and kpis.median_hr_after_split_1 > z2_high
            ):
                return "tempo"

    return None
