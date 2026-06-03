"""Direct tests for shared HR-qualified segment mechanics."""

from __future__ import annotations

from src.smartcoach_mobile_coach.execution_analytics.qualified_segment import (
    QualifyingSplit,
    SourceConfidencePolicy,
    SplitRow,
    aggregate_qualifying_splits,
    combine_weekly_qualifying_splits,
    distance_weighted_avg_hr_bpm,
    distance_weighted_pace_min_per_mi,
    eligible_split_indices,
    has_strong_qualifying_volume,
    qualifying_miles,
    resolve_source_and_confidence,
    select_qualifying_splits,
)
from src.smartcoach_mobile_coach.execution_analytics.thresholds import (
    MIN_QUALIFYING_MILES_STRONG_EVIDENCE,
    MIN_SPLITS_STRONG_EVIDENCE,
    TEMPO_RUN_MIN_SPLITS_WITH_HR,
)

ZONES_POLICY = SourceConfidencePolicy(
    primary_tier="z3",
    primary_source="splits_hr_z3",
    fallback_source="splits_hr_quality",
)

Z2_HIGH = 145.0
Z3_LO = 146.0
Z3_HI = 160.0
Z4_LO = 161.0


def _classify_tempo_hr(avg_hr: float) -> str | None:
    if Z3_LO <= avg_hr <= Z3_HI:
        return "z3"
    if Z2_HIGH < avg_hr <= Z4_LO:
        return "quality"
    return None


def _row(
    idx: int,
    *,
    hr: float,
    pace: float,
    distance: float = 1.0,
) -> SplitRow:
    return SplitRow(
        split_index=idx,
        avg_hr=hr,
        pace_min_per_mi=pace,
        distance_mi=distance,
    )


def test_eligible_split_indices_trims_warmup_when_enough_splits():
    assert eligible_split_indices([1, 2, 3, 4, 5], min_splits_for_warmup_trim=3) == {
        2,
        3,
        4,
    }
    assert eligible_split_indices([1, 2], min_splits_for_warmup_trim=3) == {1, 2}


def test_distance_weighted_pace_and_hr():
    qualifying = [
        QualifyingSplit(1, 7.0, 2.0, 150.0, "z3"),
        QualifyingSplit(2, 6.0, 1.0, 152.0, "z3"),
    ]
    assert distance_weighted_pace_min_per_mi(qualifying) == 6.6667
    assert distance_weighted_avg_hr_bpm(qualifying) == 150.67


def test_has_strong_qualifying_volume():
    weak = [QualifyingSplit(1, 7.0, 0.7, 150.0, "z3")]
    assert (
        has_strong_qualifying_volume(
            weak,
            min_splits=MIN_SPLITS_STRONG_EVIDENCE,
            min_miles=MIN_QUALIFYING_MILES_STRONG_EVIDENCE,
        )
        is False
    )
    strong = [
        QualifyingSplit(1, 7.0, 1.0, 150.0, "z3"),
        QualifyingSplit(2, 7.1, 1.0, 151.0, "z3"),
    ]
    assert (
        has_strong_qualifying_volume(
            strong,
            min_splits=MIN_SPLITS_STRONG_EVIDENCE,
            min_miles=MIN_QUALIFYING_MILES_STRONG_EVIDENCE,
        )
        is True
    )
    assert qualifying_miles(strong) == 2.0


def test_resolve_source_and_confidence_z3_vs_quality():
    z3 = [QualifyingSplit(1, 7.0, 2.0, 150.0, "z3")]
    assert resolve_source_and_confidence(
        z3,
        ZONES_POLICY,
        min_splits=MIN_SPLITS_STRONG_EVIDENCE,
        min_miles=MIN_QUALIFYING_MILES_STRONG_EVIDENCE,
    ) == ("splits_hr_z3", "medium")

    quality = [
        QualifyingSplit(1, 7.0, 2.0, 161.0, "quality"),
        QualifyingSplit(2, 7.1, 2.0, 161.0, "quality"),
    ]
    assert resolve_source_and_confidence(
        quality,
        ZONES_POLICY,
        min_splits=MIN_SPLITS_STRONG_EVIDENCE,
        min_miles=MIN_QUALIFYING_MILES_STRONG_EVIDENCE,
    ) == ("splits_hr_quality", "medium")


def test_select_qualifying_splits_matches_tempo_z3_rules():
    splits = [
        _row(1, hr=125.0, pace=9.5),
        _row(2, hr=155.0, pace=7.5),
        _row(3, hr=157.0, pace=7.3),
        _row(4, hr=130.0, pace=9.0),
    ]
    qualifying = select_qualifying_splits(
        splits,
        classify_split_hr=_classify_tempo_hr,
        primary_tier="z3",
        quality_tier="quality",
        min_splits_for_warmup_trim=TEMPO_RUN_MIN_SPLITS_WITH_HR,
    )
    assert [q.split_index for q in qualifying] == [2, 3]
    result = aggregate_qualifying_splits(
        qualifying,
        ZONES_POLICY,
        min_splits_strong=MIN_SPLITS_STRONG_EVIDENCE,
        min_miles_strong=MIN_QUALIFYING_MILES_STRONG_EVIDENCE,
    )
    assert result.segment_pace_source == "splits_hr_z3"
    assert result.segment_confidence == "high"
    assert result.segment_pace_min_per_mi == 7.4
    assert result.segment_avg_hr_bpm == 156.0


def test_combine_weekly_qualifying_splits():
    run_a = [
        QualifyingSplit(1, 7.0, 2.0, 150.0, "z3"),
        QualifyingSplit(2, 6.0, 1.0, 151.0, "z3"),
    ]
    run_b = [QualifyingSplit(1, 8.0, 1.0, 152.0, "z3")]
    weekly = combine_weekly_qualifying_splits(
        [run_a, run_b],
        ZONES_POLICY,
        min_splits_strong=MIN_SPLITS_STRONG_EVIDENCE,
        min_miles_strong=MIN_QUALIFYING_MILES_STRONG_EVIDENCE,
    )
    assert weekly.segment_split_count == 3
    assert weekly.segment_pace_source == "splits_hr_z3"
    assert weekly.segment_confidence == "high"
    assert weekly.segment_pace_min_per_mi == 7.0
