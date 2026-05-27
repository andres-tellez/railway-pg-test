"""Deprecated shim — tempo segment math lives in execution_analytics.tempo_segment."""

from src.smartcoach_mobile_coach.execution_analytics.tempo_segment import (
    QualificationTier,
    QualifyingTempoSplit,
    TempoHrZoneBounds,
    TempoSegmentConfidence,
    TempoSegmentPaceResult,
    TempoSegmentPaceSource,
    TempoSplitRow,
    aggregate_qualifying_tempo_splits,
    combine_weekly_tempo_segment_pace,
    compute_run_tempo_segment_pace,
    distance_weighted_avg_hr_bpm,
    distance_weighted_pace_min_per_mi,
    select_qualifying_tempo_splits,
)

__all__ = [
    "QualificationTier",
    "QualifyingTempoSplit",
    "TempoHrZoneBounds",
    "TempoSegmentConfidence",
    "TempoSegmentPaceResult",
    "TempoSegmentPaceSource",
    "TempoSplitRow",
    "aggregate_qualifying_tempo_splits",
    "combine_weekly_tempo_segment_pace",
    "compute_run_tempo_segment_pace",
    "distance_weighted_avg_hr_bpm",
    "distance_weighted_pace_min_per_mi",
    "select_qualifying_tempo_splits",
]
