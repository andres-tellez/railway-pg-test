"""Regression: Tempo wrapper outputs match shared qualified_segment + Tempo policy."""

from __future__ import annotations

from src.smartcoach_mobile_coach.execution_analytics.qualified_segment import (
    SourceConfidencePolicy,
    SplitRow,
    aggregate_qualifying_splits,
    combine_weekly_qualifying_splits,
    select_qualifying_splits,
)
from src.smartcoach_mobile_coach.execution_analytics.tempo_segment import (
    TempoHrZoneBounds,
    TempoSplitRow,
    _classify_split_hr,
    aggregate_qualifying_tempo_splits,
    combine_weekly_tempo_segment_pace,
    compute_run_tempo_segment_pace,
    select_qualifying_tempo_splits,
)
from src.smartcoach_mobile_coach.execution_analytics.thresholds import (
    MIN_QUALIFYING_MILES_STRONG_EVIDENCE,
    MIN_SPLITS_STRONG_EVIDENCE,
    TEMPO_RUN_MIN_SPLITS_WITH_HR,
)

ZONES = TempoHrZoneBounds(
    z2_high=145.0,
    z3_low=146.0,
    z3_high=160.0,
    z4_low=161.0,
)

TEMPO_POLICY = SourceConfidencePolicy(
    primary_tier="z3",
    primary_source="splits_hr_z3",
    fallback_source="splits_hr_quality",
)

REGRESSION_SCENARIOS = [
    {
        "name": "warmup_middle_z3",
        "splits": [
            (1, 125.0, 9.5, 1.0),
            (2, 155.0, 7.5, 1.0),
            (3, 157.0, 7.3, 1.0),
            (4, 130.0, 9.0, 1.0),
        ],
        "activity_avg": None,
        "expected_pace": 7.4,
        "expected_hr": 156.0,
        "expected_source": "splits_hr_z3",
        "expected_confidence": "high",
        "expected_split_count": 2,
    },
    {
        "name": "quality_fallback_low",
        "splits": [(1, 161.0, 7.0, 1.0)],
        "activity_avg": None,
        "expected_pace": 7.0,
        "expected_hr": 161.0,
        "expected_source": "splits_hr_quality",
        "expected_confidence": "low",
        "expected_split_count": 1,
    },
    {
        "name": "no_qualifying_activity_avg",
        "splits": [(1, 120.0, 8.0, 1.0)],
        "activity_avg": 8.5,
        "expected_pace": None,
        "expected_hr": None,
        "expected_source": "activity_avg",
        "expected_confidence": None,
        "expected_split_count": 0,
    },
]


def _tempo_rows(
    spec: list[tuple[int, float, float, float]],
) -> list[TempoSplitRow]:
    return [
        TempoSplitRow(
            split_index=idx,
            avg_hr=hr,
            pace_min_per_mi=pace,
            distance_mi=distance,
        )
        for idx, hr, pace, distance in spec
    ]


def _core_rows(
    spec: list[tuple[int, float, float, float]],
) -> list[SplitRow]:
    return [
        SplitRow(
            split_index=idx,
            avg_hr=hr,
            pace_min_per_mi=pace,
            distance_mi=distance,
        )
        for idx, hr, pace, distance in spec
    ]


def test_tempo_wrapper_matches_core_aggregate_for_regression_scenarios():
    for scenario in REGRESSION_SCENARIOS:
        tempo_splits = _tempo_rows(scenario["splits"])
        tempo_result, tempo_qualifying = compute_run_tempo_segment_pace(
            tempo_splits,
            ZONES,
            activity_avg_pace_min_per_mi=scenario["activity_avg"],
        )

        if scenario["expected_source"] == "activity_avg":
            assert tempo_result.tempo_segment_pace_source == "activity_avg"
            assert tempo_result.tempo_segment_pace_min_per_mi is None
            continue

        core_qualifying = select_qualifying_splits(
            _core_rows(scenario["splits"]),
            classify_split_hr=lambda hr: _classify_split_hr(hr, ZONES),
            primary_tier="z3",
            quality_tier="quality",
            min_splits_for_warmup_trim=TEMPO_RUN_MIN_SPLITS_WITH_HR,
        )
        core_result = aggregate_qualifying_splits(
            core_qualifying,
            TEMPO_POLICY,
            min_splits_strong=MIN_SPLITS_STRONG_EVIDENCE,
            min_miles_strong=MIN_QUALIFYING_MILES_STRONG_EVIDENCE,
        )

        assert (
            tempo_result.tempo_segment_pace_min_per_mi
            == core_result.segment_pace_min_per_mi
        )
        assert tempo_result.tempo_segment_avg_hr_bpm == core_result.segment_avg_hr_bpm
        assert tempo_result.tempo_segment_pace_source == core_result.segment_pace_source
        assert tempo_result.tempo_segment_confidence == core_result.segment_confidence
        assert tempo_result.tempo_segment_split_count == core_result.segment_split_count

        assert tempo_result.tempo_segment_pace_min_per_mi == scenario["expected_pace"]
        assert tempo_result.tempo_segment_avg_hr_bpm == scenario["expected_hr"]
        assert tempo_result.tempo_segment_pace_source == scenario["expected_source"]
        assert tempo_result.tempo_segment_confidence == scenario["expected_confidence"]
        assert (
            tempo_result.tempo_segment_split_count == scenario["expected_split_count"]
        )
        assert len(tempo_qualifying) == scenario["expected_split_count"]


def test_select_and_weekly_combine_match_core():
    splits = _tempo_rows([(1, 150.0, 7.0, 2.0), (2, 151.0, 6.0, 1.0)])
    tempo_q = select_qualifying_tempo_splits(splits, ZONES)
    core_q = select_qualifying_splits(
        _core_rows([(1, 150.0, 7.0, 2.0), (2, 151.0, 6.0, 1.0)]),
        classify_split_hr=lambda hr: _classify_split_hr(hr, ZONES),
        primary_tier="z3",
        quality_tier="quality",
        min_splits_for_warmup_trim=TEMPO_RUN_MIN_SPLITS_WITH_HR,
    )
    assert [(q.split_index, q.pace_min_per_mi, q.tier) for q in tempo_q] == [
        (q.split_index, q.pace_min_per_mi, q.tier) for q in core_q
    ]

    run_a = select_qualifying_tempo_splits(
        _tempo_rows([(1, 150.0, 7.0, 2.0), (2, 151.0, 6.0, 1.0)]), ZONES
    )
    run_b = select_qualifying_tempo_splits(_tempo_rows([(1, 152.0, 8.0, 1.0)]), ZONES)
    tempo_weekly = combine_weekly_tempo_segment_pace([run_a, run_b])
    core_weekly = combine_weekly_qualifying_splits(
        [
            core_q,
            select_qualifying_splits(
                _core_rows([(1, 152.0, 8.0, 1.0)]),
                classify_split_hr=lambda hr: _classify_split_hr(hr, ZONES),
                primary_tier="z3",
                quality_tier="quality",
                min_splits_for_warmup_trim=TEMPO_RUN_MIN_SPLITS_WITH_HR,
            ),
        ],
        TEMPO_POLICY,
        min_splits_strong=MIN_SPLITS_STRONG_EVIDENCE,
        min_miles_strong=MIN_QUALIFYING_MILES_STRONG_EVIDENCE,
    )
    assert (
        tempo_weekly.tempo_segment_pace_min_per_mi
        == core_weekly.segment_pace_min_per_mi
    )
    assert tempo_weekly.tempo_segment_confidence == core_weekly.segment_confidence
    assert tempo_weekly.tempo_segment_pace_source == core_weekly.segment_pace_source
