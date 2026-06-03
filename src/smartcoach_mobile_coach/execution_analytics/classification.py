"""Insights system classification (easy / tempo / threshold) from profile zones + split KPIs.

Precedence (first match wins):

1. **easy** — ``easy_pct >= MIN_EASY_PCT`` on runs with enough duration and HR splits.
2. **tempo** (split evidence) — ``n_z3_splits >= 2``, or no Z3 splits and
   ``n_quality_splits >= 3`` (between Z2 ceiling and Z4 floor).
3. **threshold** (split evidence) — ``n_z4_splits >= 2``, or no Z4 splits and
   ``n_threshold_quality_splits >= 3`` (between Z3 ceiling and Z5 floor).
4. **threshold** (whole-run) — avg HR or split fraction / median above Z3 high.
5. **tempo** (whole-run) — avg HR or split fraction / median above Z2 high.
6. **null** — otherwise.

Mixed Z3 + Z4: Tempo split evidence is evaluated before Threshold, so runs with
two or more Z3 split miles stay **tempo** even when some miles are in Z4. A single
Z4 spike (``n_z4_splits < 2``) does not qualify as Threshold unless whole-run
heuristics fire.
"""

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
    THRESHOLD_RUN_MIN_FRACTION_SPLITS_ABOVE_Z3_HIGH,
    THRESHOLD_RUN_MIN_SPLITS_WITH_HR,
    THRESHOLD_RUN_MIN_Z4_SPLITS,
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


def _classify_tempo_split_evidence(kpis: SplitKpiResult) -> bool:
    if kpis.n_z3_splits >= TEMPO_RUN_MIN_Z3_SPLITS:
        return True
    return (
        kpis.n_z3_splits == 0 and kpis.n_quality_splits >= TEMPO_RUN_MIN_SPLITS_WITH_HR
    )


def _classify_threshold_split_evidence(kpis: SplitKpiResult) -> bool:
    if kpis.n_z4_splits >= THRESHOLD_RUN_MIN_Z4_SPLITS:
        return True
    return (
        kpis.n_z4_splits == 0
        and kpis.n_threshold_quality_splits >= THRESHOLD_RUN_MIN_SPLITS_WITH_HR
    )


def _classify_tempo_whole_run_heuristics(
    *,
    avg_hr: float | None,
    z2_high: float | None,
    kpis: SplitKpiResult,
) -> bool:
    if z2_high is None:
        return False
    if avg_hr is not None and avg_hr > z2_high:
        return True
    if kpis.n_hr_splits >= TEMPO_RUN_MIN_SPLITS_WITH_HR:
        frac_above = kpis.n_above_z2_ceiling / kpis.n_hr_splits
        if frac_above >= TEMPO_RUN_MIN_FRACTION_SPLITS_ABOVE_Z2_HIGH:
            return True
        if (
            kpis.median_hr_after_split_1 is not None
            and kpis.median_hr_after_split_1 > z2_high
        ):
            return True
    return False


def _classify_threshold_whole_run_heuristics(
    *,
    avg_hr: float | None,
    z3_high: float | None,
    kpis: SplitKpiResult,
) -> bool:
    if z3_high is None:
        return False
    if avg_hr is not None and avg_hr > z3_high:
        return True
    if kpis.n_hr_splits >= THRESHOLD_RUN_MIN_SPLITS_WITH_HR:
        frac_above = kpis.n_above_z3_ceiling / kpis.n_hr_splits
        if frac_above >= THRESHOLD_RUN_MIN_FRACTION_SPLITS_ABOVE_Z3_HIGH:
            return True
        if (
            kpis.median_hr_after_split_1 is not None
            and kpis.median_hr_after_split_1 > z3_high
        ):
            return True
    return False


def classify_insights_system(
    *,
    moving_time_seconds: int | None,
    avg_hr: float | None,
    z2_high: float | None,
    z3_high: float | None,
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

    if _classify_tempo_split_evidence(kpis):
        return "tempo"

    if _classify_threshold_split_evidence(kpis):
        return "threshold"

    if _classify_threshold_whole_run_heuristics(
        avg_hr=avg_hr, z3_high=z3_high, kpis=kpis
    ):
        return "threshold"

    if _classify_tempo_whole_run_heuristics(avg_hr=avg_hr, z2_high=z2_high, kpis=kpis):
        return "tempo"

    return None
