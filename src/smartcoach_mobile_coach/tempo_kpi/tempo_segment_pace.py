"""
Executed Tempo/Z3 pace from split/lap HR qualification (SSOT).

Selects Tempo-quality splits by HR zone (never by goal pace corridor), then
distance-weighted aggregation. Full-activity average pace is diagnostic only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.smartcoach_mobile_coach.insights_systems import TEMPO_RUN_MIN_SPLITS_WITH_HR

TempoSegmentPaceSource = Literal[
    "splits_hr_z3",
    "splits_hr_quality",
    "splits_trimmed",  # deprecated: read-only for old payloads; never emitted
    "activity_avg",
]
TempoSegmentConfidence = Literal["high", "medium", "low"]
QualificationTier = Literal["z3", "quality"]

# Exclude first/last lap only when the run has enough HR splits to trim safely.
_MIN_SPLITS_FOR_WARMUP_TRIM = TEMPO_RUN_MIN_SPLITS_WITH_HR

# Confidence: strong evidence requires both split count and qualifying distance.
_MIN_SPLITS_STRONG_EVIDENCE = 2
_MIN_QUALIFYING_MILES_STRONG_EVIDENCE = 1.5


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
    tier: QualificationTier


@dataclass(frozen=True)
class TempoSegmentPaceResult:
    tempo_segment_pace_min_per_mi: float | None
    tempo_segment_pace_source: TempoSegmentPaceSource | None
    tempo_segment_split_count: int
    tempo_segment_confidence: TempoSegmentConfidence | None
    activity_avg_pace_min_per_mi: float | None = None

    def allows_full_gyor(self) -> bool:
        return self.tempo_segment_confidence in ("high", "medium")


def _eligible_split_indices(split_indices: list[int]) -> set[int]:
    """Warmup/cooldown guardrail: trim ends only when enough splits exist."""
    if len(split_indices) < _MIN_SPLITS_FOR_WARMUP_TRIM:
        return set(split_indices)
    ordered = sorted(split_indices)
    return set(ordered[1:-1])


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


def select_qualifying_tempo_splits(
    splits: list[TempoSplitRow],
    zones: TempoHrZoneBounds,
) -> list[QualifyingTempoSplit]:
    """
    HR-gated split selection (not pace corridor).

    1. Apply warmup trim to candidacy when n_splits >= 3.
    2. Primary tier: avg HR inside Z3.
    3. Secondary tier: only when no primary splits exist (HR > Z2 high, <= Z4 low).
    """
    if not splits:
        return []

    eligible = _eligible_split_indices([s.split_index for s in splits])
    tiered: list[tuple[QualificationTier, TempoSplitRow]] = []

    for row in splits:
        if row.split_index not in eligible:
            continue
        if row.avg_hr is None or row.pace_min_per_mi is None or row.distance_mi is None:
            continue
        if row.distance_mi <= 0 or row.pace_min_per_mi <= 0:
            continue
        tier = _classify_split_hr(float(row.avg_hr), zones)
        if tier is not None:
            tiered.append((tier, row))

    primary = [
        QualifyingTempoSplit(
            split_index=row.split_index,
            pace_min_per_mi=float(row.pace_min_per_mi),
            distance_mi=float(row.distance_mi),
            tier="z3",
        )
        for tier, row in tiered
        if tier == "z3"
    ]
    if primary:
        return primary

    return [
        QualifyingTempoSplit(
            split_index=row.split_index,
            pace_min_per_mi=float(row.pace_min_per_mi),
            distance_mi=float(row.distance_mi),
            tier="quality",
        )
        for tier, row in tiered
        if tier == "quality"
    ]


def distance_weighted_pace_min_per_mi(
    qualifying: list[QualifyingTempoSplit],
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


def _qualifying_miles(qualifying: list[QualifyingTempoSplit]) -> float:
    return sum(split.distance_mi for split in qualifying)


def _has_strong_qualifying_volume(qualifying: list[QualifyingTempoSplit]) -> bool:
    return (
        len(qualifying) >= _MIN_SPLITS_STRONG_EVIDENCE
        and _qualifying_miles(qualifying) >= _MIN_QUALIFYING_MILES_STRONG_EVIDENCE
    )


def _source_and_confidence(
    qualifying: list[QualifyingTempoSplit],
) -> tuple[TempoSegmentPaceSource, TempoSegmentConfidence]:
    has_z3 = any(split.tier == "z3" for split in qualifying)
    strong = _has_strong_qualifying_volume(qualifying)
    if has_z3:
        return (
            "splits_hr_z3",
            "high" if strong else "medium",
        )
    return (
        "splits_hr_quality",
        "medium" if strong else "low",
    )


def aggregate_qualifying_tempo_splits(
    qualifying: list[QualifyingTempoSplit],
) -> TempoSegmentPaceResult:
    pace = distance_weighted_pace_min_per_mi(qualifying)
    if pace is None:
        return TempoSegmentPaceResult(
            tempo_segment_pace_min_per_mi=None,
            tempo_segment_pace_source=None,
            tempo_segment_split_count=0,
            tempo_segment_confidence=None,
        )

    source, confidence = _source_and_confidence(qualifying)

    return TempoSegmentPaceResult(
        tempo_segment_pace_min_per_mi=pace,
        tempo_segment_pace_source=source,
        tempo_segment_split_count=len(qualifying),
        tempo_segment_confidence=confidence,
    )


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
    combined = [split for run in per_run_qualifying for split in run]
    return aggregate_qualifying_tempo_splits(combined)
