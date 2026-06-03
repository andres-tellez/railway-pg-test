"""Week-level threshold segment rollup from stored facts."""

from __future__ import annotations

from src.smartcoach_mobile_coach.execution_analytics.combine import (
    StoredThresholdRunFact,
    combine_threshold_weekly_from_stored_run_facts,
    threshold_run_fact_eligible_for_week_chart,
)


def _fact(
    *,
    confidence: str = "high",
    source: str = "splits_hr_z4",
    miles: float = 1.0,
    splits: int = 1,
    pace: float = 7.0,
    hr: float = 165.0,
) -> StoredThresholdRunFact:
    return StoredThresholdRunFact(
        threshold_segment_pace_min_per_mi=pace,
        threshold_segment_avg_hr_bpm=hr,
        threshold_segment_pace_source=source,
        threshold_segment_confidence=confidence,
        threshold_segment_split_count=splits,
        threshold_qualifying_distance_mi=miles,
    )


def test_low_confidence_excluded():
    fact = _fact(confidence="low", source="splits_hr_quality")
    assert threshold_run_fact_eligible_for_week_chart(fact) is False


def test_weekly_z4_rollup_high_confidence():
    facts = [
        _fact(confidence="high", miles=1.0, splits=2, pace=7.0, hr=165.0),
        _fact(confidence="medium", miles=1.0, splits=1, pace=7.2, hr=167.0),
    ]
    result = combine_threshold_weekly_from_stored_run_facts(facts)
    assert result.threshold_segment_pace_source == "splits_hr_z4"
    assert result.threshold_segment_confidence == "high"
    assert result.threshold_segment_pace_min_per_mi == 7.1
