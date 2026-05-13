"""Phase 5: banned coach vocabulary must not appear in user-facing readiness strings."""

from __future__ import annotations

import re
from typing import Any, Callable, Iterable

import pytest

from src.coaching_intelligence.plan_generation_readiness import (
    evaluate_plan_generation_readiness,
)
from src.coaching_intelligence.pre_generation_runner_review import (
    build_pre_generation_runner_review_v1,
)
from tests.coaching_intelligence.ambition_gap_fixtures import (
    synthetic_ambition_attributions,
)

_BANNED_RE = re.compile(
    r"(?i)\b(?:tradeoff|path|tension|commitment|coherence)\b",
)


def _walk_string_values(obj: Any) -> Iterable[str]:
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_string_values(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_string_values(v)


def _assert_no_banned(s: str, *, context: str) -> None:
    if _BANNED_RE.search(s):
        m = _BANNED_RE.search(s)
        assert m is None, f"{context}: banned term near {m.group(0)!r} in {s!r}"


def _case_just_finish_display() -> dict[str, Any]:
    plan = {
        "race_distance": "Marathon",
        "race_date": "2030-06-01",
        "primary_goal": "Just Finish",
        "training_days": ["Mon", "Wed", "Fri"],
    }
    assessment = {
        "activity_summary": {
            "avg_miles_per_week_approx": 28.0,
            "longest_run_miles": 10.0,
            "activities_found": 8,
            "lookback_weeks": 6,
            "completed_calendar_weeks_count": 4,
        },
        "ambition_gap": {
            "stance": "COHERENT",
            "baseline_band": "MODERATE",
            "goal_demand": "FINISH",
            "thin_baseline_data": False,
            "attributions": synthetic_ambition_attributions(
                baseline_band="MODERATE",
                goal_demand="FINISH",
                thin_baseline_data=False,
                longest_run_miles=10.0,
            ),
        },
        "intake_alignment_state": {"generation_ready": True, "unresolved_flags": []},
    }
    out = evaluate_plan_generation_readiness(
        plan_request=plan, assessment_api=assessment
    )
    return out["runner_analysis_display"]


def _case_sub3_review_lines() -> list[str]:
    plan_request = {
        "race_distance": "Marathon",
        "race_date": "2030-06-01",
        "primary_goal": "Target Time",
        "target_time": "3:00:00",
        "training_days": ["Mon", "Wed", "Sat"],
    }
    assessment_api = {
        "activity_summary": {
            "avg_miles_per_week_approx": 24.0,
            "longest_run_miles": 12.0,
            "activities_found": 8,
            "lookback_weeks": 6,
            "active_weeks": 4,
            "completed_calendar_weeks_count": 4,
        },
        "ambition_gap": {
            "stance": "COHERENT",
            "baseline_band": "MODERATE",
            "goal_demand": "TIME_TARGET",
            "thin_baseline_data": False,
            "attributions": synthetic_ambition_attributions(
                baseline_band="MODERATE",
                goal_demand="TIME_TARGET",
                thin_baseline_data=False,
                longest_run_miles=12.0,
            ),
        },
        "intake_alignment_state": {"generation_ready": True, "unresolved_flags": []},
    }
    readiness = evaluate_plan_generation_readiness(
        plan_request=plan_request, assessment_api=assessment_api
    )
    review = build_pre_generation_runner_review_v1(
        assessment_api=assessment_api,
        plan_request=plan_request,
        plan_generation_readiness=readiness,
    )
    return [*review.summary_lines, *review.concerns]


@pytest.mark.parametrize(
    "name,factory",
    [
        ("runner_analysis_display_just_finish", _case_just_finish_display),
        ("review_summary_concerns_sub3", _case_sub3_review_lines),
    ],
)
def test_no_banned_vocabulary(name: str, factory: Callable[[], Any]):
    payload = factory()
    if isinstance(payload, dict):
        strings = list(_walk_string_values(payload))
    else:
        strings = list(payload)
    for i, s in enumerate(strings):
        _assert_no_banned(s, context=f"{name}[{i}]")
