"""Weekly tempo rollup from stored activity execution facts."""

from __future__ import annotations

from src.smartcoach_mobile_coach.execution_analytics.combine import (
    StoredTempoRunFact,
    combine_weekly_from_stored_run_facts,
    run_fact_eligible_for_week_chart,
)


def _fact(
    *,
    pace: float = 7.4,
    hr: float = 156.0,
    source: str = "splits_hr_z3",
    confidence: str = "high",
    splits: int = 2,
    miles: float = 2.0,
) -> StoredTempoRunFact:
    return StoredTempoRunFact(
        tempo_segment_pace_min_per_mi=pace,
        tempo_segment_avg_hr_bpm=hr,
        tempo_segment_pace_source=source,
        tempo_segment_confidence=confidence,
        tempo_segment_split_count=splits,
        tempo_qualifying_distance_mi=miles,
    )


def test_activity_avg_excluded_from_week_chart():
    fact = StoredTempoRunFact(
        tempo_segment_pace_min_per_mi=None,
        tempo_segment_avg_hr_bpm=None,
        tempo_segment_pace_source="activity_avg",
        tempo_segment_confidence=None,
        tempo_segment_split_count=0,
        tempo_qualifying_distance_mi=None,
    )
    assert run_fact_eligible_for_week_chart(fact) is False
    result = combine_weekly_from_stored_run_facts([fact])
    assert result.tempo_segment_pace_min_per_mi is None
    assert result.allows_full_gyor() is False


def test_low_confidence_excluded():
    fact = _fact(confidence="low", source="splits_hr_quality")
    assert run_fact_eligible_for_week_chart(fact) is False


def test_mixed_high_and_medium_runs_yields_medium_week_confidence():
    facts = [
        _fact(confidence="high", miles=0.4, splits=1),
        _fact(confidence="medium", miles=0.4, splits=1),
    ]
    result = combine_weekly_from_stored_run_facts(facts)
    assert result.tempo_segment_confidence == "medium"
    assert result.allows_full_gyor() is True


def test_strong_combined_volume_can_yield_high():
    facts = [
        _fact(confidence="high", miles=1.0, splits=2),
        _fact(confidence="medium", miles=1.0, splits=2, pace=7.2, hr=157.0),
    ]
    result = combine_weekly_from_stored_run_facts(facts)
    assert result.tempo_segment_confidence == "high"
    assert result.tempo_segment_pace_source == "splits_hr_z3"
