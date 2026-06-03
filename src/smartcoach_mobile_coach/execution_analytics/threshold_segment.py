"""
Executed Threshold/Z4 pace from split/lap HR qualification (Tier 2 SSOT).

Generic mechanics live in ``qualified_segment``; this module is the Threshold public API.
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
    THRESHOLD_RUN_MIN_SPLITS_WITH_HR,
)

ThresholdSegmentPaceSource = Literal[
    "splits_hr_z4",
    "splits_hr_quality",
    "activity_avg",
]
ThresholdSegmentConfidence = Literal["high", "medium", "low"]
QualificationTier = Literal["z4", "quality"]

_THRESHOLD_POLICY = SourceConfidencePolicy(
    primary_tier="z4",
    primary_source="splits_hr_z4",
    fallback_source="splits_hr_quality",
)
_THRESHOLD_PRIMARY_TIER = "z4"
_THRESHOLD_QUALITY_TIER = "quality"


@dataclass(frozen=True)
class ThresholdHrZoneBounds:
    z3_high: float | None
    z4_low: float | None
    z4_high: float | None
    z5_low: float | None


@dataclass(frozen=True)
class ThresholdSplitRow:
    split_index: int
    avg_hr: float | None
    pace_min_per_mi: float | None
    distance_mi: float | None


@dataclass(frozen=True)
class QualifyingThresholdSplit:
    split_index: int
    pace_min_per_mi: float
    distance_mi: float
    avg_hr_bpm: float
    tier: QualificationTier


@dataclass(frozen=True)
class ThresholdSegmentPaceResult:
    threshold_segment_pace_min_per_mi: float | None
    threshold_segment_avg_hr_bpm: float | None
    threshold_segment_pace_source: ThresholdSegmentPaceSource | None
    threshold_segment_split_count: int
    threshold_segment_confidence: ThresholdSegmentConfidence | None
    activity_avg_pace_min_per_mi: float | None = None

    def allows_full_gyor(self) -> bool:
        return self.threshold_segment_confidence in ("high", "medium")


def _classify_split_hr(
    avg_hr: float,
    zones: ThresholdHrZoneBounds,
) -> QualificationTier | None:
    z4_lo, z4_hi = zones.z4_low, zones.z4_high
    if z4_lo is not None and z4_hi is not None and z4_lo <= avg_hr <= z4_hi:
        return "z4"
    z3_hi, z5_lo = zones.z3_high, zones.z5_low
    if z3_hi is not None and z5_lo is not None and avg_hr > z3_hi and avg_hr <= z5_lo:
        return "quality"
    return None


def _split_rows_from_threshold(splits: list[ThresholdSplitRow]) -> list[SplitRow]:
    return [
        SplitRow(
            split_index=row.split_index,
            avg_hr=row.avg_hr,
            pace_min_per_mi=row.pace_min_per_mi,
            distance_mi=row.distance_mi,
        )
        for row in splits
    ]


def _qualifying_from_core(
    splits: list[QualifyingSplit],
) -> list[QualifyingThresholdSplit]:
    return [
        QualifyingThresholdSplit(
            split_index=split.split_index,
            pace_min_per_mi=split.pace_min_per_mi,
            distance_mi=split.distance_mi,
            avg_hr_bpm=split.avg_hr_bpm,
            tier=cast(QualificationTier, split.tier),
        )
        for split in splits
    ]


def _qualifying_to_core(
    qualifying: list[QualifyingThresholdSplit],
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


def _threshold_result_from_aggregate(
    agg: SegmentAggregateResult,
) -> ThresholdSegmentPaceResult:
    source = cast(ThresholdSegmentPaceSource | None, agg.segment_pace_source)
    confidence = cast(ThresholdSegmentConfidence | None, agg.segment_confidence)
    return ThresholdSegmentPaceResult(
        threshold_segment_pace_min_per_mi=agg.segment_pace_min_per_mi,
        threshold_segment_avg_hr_bpm=agg.segment_avg_hr_bpm,
        threshold_segment_pace_source=source,
        threshold_segment_split_count=agg.segment_split_count,
        threshold_segment_confidence=confidence,
    )


def select_qualifying_threshold_splits(
    splits: list[ThresholdSplitRow],
    zones: ThresholdHrZoneBounds,
) -> list[QualifyingThresholdSplit]:
    def classify(avg_hr: float) -> str | None:
        return _classify_split_hr(avg_hr, zones)

    core = select_qualifying_splits(
        _split_rows_from_threshold(splits),
        classify_split_hr=classify,
        primary_tier=_THRESHOLD_PRIMARY_TIER,
        quality_tier=_THRESHOLD_QUALITY_TIER,
        min_splits_for_warmup_trim=THRESHOLD_RUN_MIN_SPLITS_WITH_HR,
    )
    return _qualifying_from_core(core)


def distance_weighted_pace_min_per_mi(
    qualifying: list[QualifyingThresholdSplit],
) -> float | None:
    return _distance_weighted_pace_min_per_mi(_qualifying_to_core(qualifying))


def distance_weighted_avg_hr_bpm(
    qualifying: list[QualifyingThresholdSplit],
) -> float | None:
    return _distance_weighted_avg_hr_bpm(_qualifying_to_core(qualifying))


def aggregate_qualifying_threshold_splits(
    qualifying: list[QualifyingThresholdSplit],
) -> ThresholdSegmentPaceResult:
    agg = _aggregate_qualifying_splits(
        _qualifying_to_core(qualifying),
        _THRESHOLD_POLICY,
        min_splits_strong=MIN_SPLITS_STRONG_EVIDENCE,
        min_miles_strong=MIN_QUALIFYING_MILES_STRONG_EVIDENCE,
    )
    return _threshold_result_from_aggregate(agg)


def compute_run_threshold_segment_pace(
    splits: list[ThresholdSplitRow],
    zones: ThresholdHrZoneBounds,
    *,
    activity_avg_pace_min_per_mi: float | None = None,
) -> tuple[ThresholdSegmentPaceResult, list[QualifyingThresholdSplit]]:
    qualifying = select_qualifying_threshold_splits(splits, zones)
    result = aggregate_qualifying_threshold_splits(qualifying)
    if (
        result.threshold_segment_pace_min_per_mi is None
        and activity_avg_pace_min_per_mi is not None
    ):
        return (
            ThresholdSegmentPaceResult(
                threshold_segment_pace_min_per_mi=None,
                threshold_segment_avg_hr_bpm=None,
                threshold_segment_pace_source="activity_avg",
                threshold_segment_split_count=0,
                threshold_segment_confidence=None,
                activity_avg_pace_min_per_mi=activity_avg_pace_min_per_mi,
            ),
            [],
        )
    return result, qualifying


def combine_weekly_threshold_segment_pace(
    per_run_qualifying: list[list[QualifyingThresholdSplit]],
) -> ThresholdSegmentPaceResult:
    """Distance-weighted rollup across all qualifying threshold splits in the week."""
    core_runs = [_qualifying_to_core(run) for run in per_run_qualifying]
    agg = combine_weekly_qualifying_splits(
        core_runs,
        _THRESHOLD_POLICY,
        min_splits_strong=MIN_SPLITS_STRONG_EVIDENCE,
        min_miles_strong=MIN_QUALIFYING_MILES_STRONG_EVIDENCE,
    )
    return _threshold_result_from_aggregate(agg)
