"""
Executed Tempo/Z3 pace from split/lap HR qualification (Tier 2 SSOT).

Selects Tempo-quality splits by HR zone (never by goal pace corridor), then
distance-weighted aggregation. Full-activity average pace is diagnostic only.

Generic mechanics live in ``qualified_segment``; this module is the Tempo public API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from src.smartcoach_mobile_coach.execution_analytics.qualified_segment import (
    QualifyingSplit,
    SegmentAggregateResult,
    SourceConfidencePolicy,
    SplitRow,
    aggregate_qualifying_splits as _aggregate_qualifying_splits,
    combine_weekly_qualifying_splits,
    distance_weighted_avg_hr_bpm as _distance_weighted_avg_hr_bpm,
    distance_weighted_pace_min_per_mi as _distance_weighted_pace_min_per_mi,
    select_qualifying_splits,
)
from src.smartcoach_mobile_coach.execution_analytics.thresholds import (
    MIN_QUALIFYING_MILES_STRONG_EVIDENCE,
    MIN_SPLITS_STRONG_EVIDENCE,
    TEMPO_RUN_MIN_SPLITS_WITH_HR,
)

TempoSegmentPaceSource = Literal[
    "splits_hr_z3",
    "splits_hr_quality",
    "splits_trimmed",  # deprecated: read-only for old payloads; never emitted
    "activity_avg",
]
TempoSegmentConfidence = Literal["high", "medium", "low"]
QualificationTier = Literal["z3", "quality"]

_TEMPO_POLICY = SourceConfidencePolicy(
    primary_tier="z3",
    primary_source="splits_hr_z3",
    fallback_source="splits_hr_quality",
)
_TEMPO_PRIMARY_TIER = "z3"
_TEMPO_QUALITY_TIER = "quality"


@dataclass(frozen=True)
class TempoHrZoneBounds:
    z2_high: float | None
    z3_low: float | None
    z3_high: float | None
    z4_low: float | None


@dataclass(frozen=True)
class TempoSplitRow:
    split_index: int
    avg_hr: float | None
    pace_min_per_mi: float | None
    distance_mi: float | None


@dataclass(frozen=True)
class QualifyingTempoSplit:
    split_index: int
    pace_min_per_mi: float
    distance_mi: float
    avg_hr_bpm: float
    tier: QualificationTier


@dataclass(frozen=True)
class TempoSegmentPaceResult:
    tempo_segment_pace_min_per_mi: float | None
    tempo_segment_avg_hr_bpm: float | None
    tempo_segment_pace_source: TempoSegmentPaceSource | None
    tempo_segment_split_count: int
    tempo_segment_confidence: TempoSegmentConfidence | None
    activity_avg_pace_min_per_mi: float | None = None

    def allows_full_gyor(self) -> bool:
        return self.tempo_segment_confidence in ("high", "medium")


def _classify_split_hr(
    avg_hr: float,
    zones: TempoHrZoneBounds,
) -> QualificationTier | None:
    z3_lo, z3_hi = zones.z3_low, zones.z3_high
    if z3_lo is not None and z3_hi is not None and z3_lo <= avg_hr <= z3_hi:
        return "z3"
    z2_hi, z4_lo = zones.z2_high, zones.z4_low
    if z2_hi is not None and z4_lo is not None and avg_hr > z2_hi and avg_hr <= z4_lo:
        return "quality"
    return None


def _split_rows_from_tempo(splits: list[TempoSplitRow]) -> list[SplitRow]:
    return [
        SplitRow(
            split_index=row.split_index,
            avg_hr=row.avg_hr,
            pace_min_per_mi=row.pace_min_per_mi,
            distance_mi=row.distance_mi,
        )
        for row in splits
    ]


def _qualifying_from_core(splits: list[QualifyingSplit]) -> list[QualifyingTempoSplit]:
    return [
        QualifyingTempoSplit(
            split_index=split.split_index,
            pace_min_per_mi=split.pace_min_per_mi,
            distance_mi=split.distance_mi,
            avg_hr_bpm=split.avg_hr_bpm,
            tier=cast(QualificationTier, split.tier),
        )
        for split in splits
    ]


def _qualifying_to_core(
    qualifying: list[QualifyingTempoSplit],
) -> list[QualifyingSplit]:
    return [
        QualifyingSplit(
            split_index=split.split_index,
            pace_min_per_mi=split.pace_min_per_mi,
            distance_mi=split.distance_mi,
            avg_hr_bpm=split.avg_hr_bpm,
            tier=split.tier,
        )
        for split in qualifying
    ]


def _tempo_result_from_aggregate(agg: SegmentAggregateResult) -> TempoSegmentPaceResult:
    source = cast(TempoSegmentPaceSource | None, agg.segment_pace_source)
    confidence = cast(TempoSegmentConfidence | None, agg.segment_confidence)
    return TempoSegmentPaceResult(
        tempo_segment_pace_min_per_mi=agg.segment_pace_min_per_mi,
        tempo_segment_avg_hr_bpm=agg.segment_avg_hr_bpm,
        tempo_segment_pace_source=source,
        tempo_segment_split_count=agg.segment_split_count,
        tempo_segment_confidence=confidence,
    )


def select_qualifying_tempo_splits(
    splits: list[TempoSplitRow],
    zones: TempoHrZoneBounds,
) -> list[QualifyingTempoSplit]:
    def classify(avg_hr: float) -> str | None:
        tier = _classify_split_hr(avg_hr, zones)
        return tier

    core = select_qualifying_splits(
        _split_rows_from_tempo(splits),
        classify_split_hr=classify,
        primary_tier=_TEMPO_PRIMARY_TIER,
        quality_tier=_TEMPO_QUALITY_TIER,
        min_splits_for_warmup_trim=TEMPO_RUN_MIN_SPLITS_WITH_HR,
    )
    return _qualifying_from_core(core)


def distance_weighted_pace_min_per_mi(
    qualifying: list[QualifyingTempoSplit],
) -> float | None:
    return _distance_weighted_pace_min_per_mi(_qualifying_to_core(qualifying))


def distance_weighted_avg_hr_bpm(
    qualifying: list[QualifyingTempoSplit],
) -> float | None:
    return _distance_weighted_avg_hr_bpm(_qualifying_to_core(qualifying))


def aggregate_qualifying_tempo_splits(
    qualifying: list[QualifyingTempoSplit],
) -> TempoSegmentPaceResult:
    agg = _aggregate_qualifying_splits(
        _qualifying_to_core(qualifying),
        _TEMPO_POLICY,
        min_splits_strong=MIN_SPLITS_STRONG_EVIDENCE,
        min_miles_strong=MIN_QUALIFYING_MILES_STRONG_EVIDENCE,
    )
    return _tempo_result_from_aggregate(agg)


def compute_run_tempo_segment_pace(
    splits: list[TempoSplitRow],
    zones: TempoHrZoneBounds,
    *,
    activity_avg_pace_min_per_mi: float | None = None,
) -> tuple[TempoSegmentPaceResult, list[QualifyingTempoSplit]]:
    qualifying = select_qualifying_tempo_splits(splits, zones)
    result = aggregate_qualifying_tempo_splits(qualifying)
    if (
        result.tempo_segment_pace_min_per_mi is None
        and activity_avg_pace_min_per_mi is not None
    ):
        return (
            TempoSegmentPaceResult(
                tempo_segment_pace_min_per_mi=None,
                tempo_segment_avg_hr_bpm=None,
                tempo_segment_pace_source="activity_avg",
                tempo_segment_split_count=0,
                tempo_segment_confidence=None,
                activity_avg_pace_min_per_mi=activity_avg_pace_min_per_mi,
            ),
            [],
        )
    return result, qualifying


def combine_weekly_tempo_segment_pace(
    per_run_qualifying: list[list[QualifyingTempoSplit]],
) -> TempoSegmentPaceResult:
    """Distance-weighted rollup across all qualifying tempo splits in the week."""
    core_runs = [_qualifying_to_core(run) for run in per_run_qualifying]
    agg = combine_weekly_qualifying_splits(
        core_runs,
        _TEMPO_POLICY,
        min_splits_strong=MIN_SPLITS_STRONG_EVIDENCE,
        min_miles_strong=MIN_QUALIFYING_MILES_STRONG_EVIDENCE,
    )
    return _tempo_result_from_aggregate(agg)
