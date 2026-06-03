"""
HR-qualified split segment mechanics shared by Insights pace systems (Tempo/Z3, etc.).

Zone-specific split classification and source labels live in per-system wrappers
(e.g. ``tempo_segment``). This module holds only generic selection, weighting,
confidence, and aggregation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Sequence

SegmentConfidence = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class SplitRow:
    split_index: int
    avg_hr: float | None
    pace_min_per_mi: float | None
    distance_mi: float | None


@dataclass(frozen=True)
class QualifyingSplit:
    split_index: int
    pace_min_per_mi: float
    distance_mi: float
    avg_hr_bpm: float
    tier: str


@dataclass(frozen=True)
class SourceConfidencePolicy:
    """Maps qualifying tier labels to pace source strings for chart eligibility."""

    primary_tier: str
    primary_source: str
    fallback_source: str


@dataclass(frozen=True)
class SegmentAggregateResult:
    segment_pace_min_per_mi: float | None
    segment_avg_hr_bpm: float | None
    segment_pace_source: str | None
    segment_split_count: int
    segment_confidence: SegmentConfidence | None


def eligible_split_indices(
    split_indices: list[int],
    *,
    min_splits_for_warmup_trim: int,
) -> set[int]:
    if len(split_indices) < min_splits_for_warmup_trim:
        return set(split_indices)
    ordered = sorted(split_indices)
    return set(ordered[1:-1])


def distance_weighted_pace_min_per_mi(
    qualifying: Sequence[QualifyingSplit],
) -> float | None:
    if not qualifying:
        return None
    num = 0.0
    den = 0.0
    for split in qualifying:
        num += split.pace_min_per_mi * split.distance_mi
        den += split.distance_mi
    if den <= 0:
        return None
    return round(num / den, 4)


def distance_weighted_avg_hr_bpm(
    qualifying: Sequence[QualifyingSplit],
) -> float | None:
    if not qualifying:
        return None
    num = 0.0
    den = 0.0
    for split in qualifying:
        num += split.avg_hr_bpm * split.distance_mi
        den += split.distance_mi
    if den <= 0:
        return None
    return round(num / den, 2)


def qualifying_miles(qualifying: Sequence[QualifyingSplit]) -> float:
    return sum(split.distance_mi for split in qualifying)


def has_strong_qualifying_volume(
    qualifying: Sequence[QualifyingSplit],
    *,
    min_splits: int,
    min_miles: float,
) -> bool:
    return len(qualifying) >= min_splits and qualifying_miles(qualifying) >= min_miles


def resolve_source_and_confidence(
    qualifying: Sequence[QualifyingSplit],
    policy: SourceConfidencePolicy,
    *,
    min_splits: int,
    min_miles: float,
) -> tuple[str, SegmentConfidence]:
    has_primary = any(split.tier == policy.primary_tier for split in qualifying)
    strong = has_strong_qualifying_volume(
        qualifying, min_splits=min_splits, min_miles=min_miles
    )
    if has_primary:
        return (
            policy.primary_source,
            "high" if strong else "medium",
        )
    return (
        policy.fallback_source,
        "medium" if strong else "low",
    )


def select_qualifying_splits(
    splits: Sequence[SplitRow],
    *,
    classify_split_hr: Callable[[float], str | None],
    primary_tier: str,
    quality_tier: str,
    min_splits_for_warmup_trim: int,
) -> list[QualifyingSplit]:
    if not splits:
        return []

    eligible = eligible_split_indices(
        [s.split_index for s in splits],
        min_splits_for_warmup_trim=min_splits_for_warmup_trim,
    )
    tiered: list[tuple[str, SplitRow]] = []

    for row in splits:
        if row.split_index not in eligible:
            continue
        if row.avg_hr is None or row.pace_min_per_mi is None or row.distance_mi is None:
            continue
        if row.distance_mi <= 0 or row.pace_min_per_mi <= 0:
            continue
        tier = classify_split_hr(float(row.avg_hr))
        if tier is not None:
            tiered.append((tier, row))

    primary = [
        QualifyingSplit(
            split_index=row.split_index,
            pace_min_per_mi=float(row.pace_min_per_mi),
            distance_mi=float(row.distance_mi),
            avg_hr_bpm=float(row.avg_hr),
            tier=primary_tier,
        )
        for tier, row in tiered
        if tier == primary_tier
    ]
    if primary:
        return primary

    return [
        QualifyingSplit(
            split_index=row.split_index,
            pace_min_per_mi=float(row.pace_min_per_mi),
            distance_mi=float(row.distance_mi),
            avg_hr_bpm=float(row.avg_hr),
            tier=quality_tier,
        )
        for tier, row in tiered
        if tier == quality_tier
    ]


def aggregate_qualifying_splits(
    qualifying: Sequence[QualifyingSplit],
    policy: SourceConfidencePolicy,
    *,
    min_splits_strong: int,
    min_miles_strong: float,
) -> SegmentAggregateResult:
    pace = distance_weighted_pace_min_per_mi(qualifying)
    avg_hr = distance_weighted_avg_hr_bpm(qualifying)
    if pace is None or avg_hr is None:
        return SegmentAggregateResult(
            segment_pace_min_per_mi=None,
            segment_avg_hr_bpm=None,
            segment_pace_source=None,
            segment_split_count=0,
            segment_confidence=None,
        )

    source, confidence = resolve_source_and_confidence(
        qualifying,
        policy,
        min_splits=min_splits_strong,
        min_miles=min_miles_strong,
    )

    return SegmentAggregateResult(
        segment_pace_min_per_mi=pace,
        segment_avg_hr_bpm=avg_hr,
        segment_pace_source=source,
        segment_split_count=len(qualifying),
        segment_confidence=confidence,
    )


def combine_weekly_qualifying_splits(
    per_run_qualifying: Sequence[Sequence[QualifyingSplit]],
    policy: SourceConfidencePolicy,
    *,
    min_splits_strong: int,
    min_miles_strong: float,
) -> SegmentAggregateResult:
    """Distance-weighted rollup across all qualifying splits in the week."""
    combined = [split for run in per_run_qualifying for split in run]
    return aggregate_qualifying_splits(
        combined,
        policy,
        min_splits_strong=min_splits_strong,
        min_miles_strong=min_miles_strong,
    )
