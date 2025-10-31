from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

import pytest

from src.services.training_plan.long_run_spine import generate_long_run_spine
from src.services.training_plan.pass1_longrun_first import Pass1LongRunFirst


class _FakeCollector:
    def __init__(self, activities: List[Dict[str, Any]], plan_request: Dict[str, Any]):
        self._activities = activities
        self._plan_request = plan_request

    def collect_all_data(
        self,
        *,
        session,
        user_id: str,
        plan_request: Dict[str, Any],
        activity_weeks: int = 12,
    ) -> Dict[str, Any]:  # noqa: D401
        return {
            "user_profile": {},
            "strava_activities": self._activities,
            "plan_request": self._plan_request,
            "metadata": {},
        }


class _FakeInsights:
    def __init__(self, weekly_mileage: float, longest_run: float):
        self._weekly_mileage = weekly_mileage
        self._longest_run = longest_run

    def calculate_all_insights(
        self, raw_data: Dict[str, Any]
    ) -> Dict[str, Any]:  # noqa: D401
        return {
            "current_fitness": {
                "weekly_mileage": self._weekly_mileage,
                "longest_run": self._longest_run,
            }
        }


def _mk_activity(miles: float, days_ago: int) -> Dict[str, Any]:
    when = (datetime.utcnow() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
    return {"date": when, "distance": miles, "moving_time": int(miles * 10) * 60}


def test_spine_preserves_exact_start():
    weeks = generate_long_run_spine(
        starting_long_run_miles=15.0,
        total_weeks_in_plan=14,
        peak_long_run_target=20.0,
        inc_miles=1.0,
        taper_weeks=2,
    )
    assert weeks[0]["long_run_miles"] == 15.0


def test_lr_first_prefers_recent_3w_window_over_race_outlier(monkeypatch):
    # Activities: recent window has a 14-miler 7 days ago; include an older marathon (26.2)
    activities = [
        _mk_activity(14.0, 7),
        _mk_activity(5.0, 10),
        _mk_activity(3.0, 14),
        _mk_activity(26.2, 40),  # outlier/race outside 3-week window
    ]
    # Fake services: weekly mileage modest, longest_run incorrectly 26.2 from the outlier
    collector = _FakeCollector(
        activities, {"race_date": (datetime.utcnow() + timedelta(weeks=16)).date()}
    )
    insights = _FakeInsights(weekly_mileage=30.0, longest_run=26.2)

    svc = Pass1LongRunFirst(data_collector=collector, insights_service=insights)

    # Use a dummy session and user_id; services don't touch DB in this test
    result = svc.build(
        session=None,
        user_id="00000000-0000-0000-0000-000000000000",
        plan_request={"race_date": (datetime.utcnow() + timedelta(weeks=16)).date()},
    )
    weeks = result["weeks"]
    # Expect Week 1 to be 15.0 (recent 14 + 1), not 27
    assert weeks[0]["long_run_miles"] == 15.0
