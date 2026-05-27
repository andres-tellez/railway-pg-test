"""Week-level tempo segment rollup from stored activity execution facts."""

from __future__ import annotations

from dataclasses import dataclass

from src.smartcoach_mobile_coach.execution_analytics.tempo_segment import (
    TempoSegmentPaceResult,
)
from src.smartcoach_mobile_coach.execution_analytics.thresholds import (
    CHART_ELIGIBLE_TEMPO_CONFIDENCE,
    CHART_ELIGIBLE_TEMPO_SOURCES,
    MIN_QUALIFYING_MILES_STRONG_EVIDENCE,
    MIN_SPLITS_STRONG_EVIDENCE,
)


@dataclass(frozen=True)
class StoredTempoRunFact:
    tempo_segment_pace_min_per_mi: float | None
    tempo_segment_avg_hr_bpm: float | None
    tempo_segment_pace_source: str | None
    tempo_segment_confidence: str | None
    tempo_segment_split_count: int | None
    tempo_qualifying_distance_mi: float | None


def run_fact_eligible_for_week_chart(fact: StoredTempoRunFact) -> bool:
    if fact.tempo_segment_pace_source not in CHART_ELIGIBLE_TEMPO_SOURCES:
        return False
    if fact.tempo_segment_confidence not in CHART_ELIGIBLE_TEMPO_CONFIDENCE:
        return False
    if fact.tempo_segment_pace_min_per_mi is None:
        return False
    if (
        fact.tempo_qualifying_distance_mi is None
        or fact.tempo_qualifying_distance_mi <= 0
    ):
        return False
    return True


def _empty_week_result() -> TempoSegmentPaceResult:
    return TempoSegmentPaceResult(
        tempo_segment_pace_min_per_mi=None,
        tempo_segment_avg_hr_bpm=None,
        tempo_segment_pace_source=None,
        tempo_segment_split_count=0,
        tempo_segment_confidence=None,
    )


def combine_weekly_from_stored_run_facts(
    facts: list[StoredTempoRunFact],
) -> TempoSegmentPaceResult:
    """
    Distance-weighted week rollup from persisted per-run tempo segment facts.

    Excludes activity_avg and low-confidence runs. activity_avg is diagnostic
    only and cannot produce chart dots or GYOR bands.
    """
    eligible = [f for f in facts if run_fact_eligible_for_week_chart(f)]
    if not eligible:
        return _empty_week_result()

    total_miles = sum(float(f.tempo_qualifying_distance_mi or 0) for f in eligible)
    total_splits = sum(int(f.tempo_segment_split_count or 0) for f in eligible)
    if total_miles <= 0:
        return _empty_week_result()

    pace_num = 0.0
    hr_num = 0.0
    for fact in eligible:
        miles = float(fact.tempo_qualifying_distance_mi or 0)
        pace_num += float(fact.tempo_segment_pace_min_per_mi or 0) * miles
        if fact.tempo_segment_avg_hr_bpm is not None:
            hr_num += float(fact.tempo_segment_avg_hr_bpm) * miles

    combined_pace = round(pace_num / total_miles, 4)
    combined_hr = round(hr_num / total_miles, 2) if hr_num > 0 else None

    has_z3 = any(f.tempo_segment_pace_source == "splits_hr_z3" for f in eligible)
    combined_source = "splits_hr_z3" if has_z3 else "splits_hr_quality"

    all_high = all(f.tempo_segment_confidence == "high" for f in eligible)
    strong_volume = (
        total_miles >= MIN_QUALIFYING_MILES_STRONG_EVIDENCE
        and total_splits >= MIN_SPLITS_STRONG_EVIDENCE
    )
    if strong_volume and (has_z3 or all_high):
        combined_confidence = "high"
    else:
        combined_confidence = "medium"

    return TempoSegmentPaceResult(
        tempo_segment_pace_min_per_mi=combined_pace,
        tempo_segment_avg_hr_bpm=combined_hr,
        tempo_segment_pace_source=combined_source,
        tempo_segment_split_count=total_splits,
        tempo_segment_confidence=combined_confidence,
    )
