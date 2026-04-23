"""
Tests for the Phase E structured plan-adjustment tool wrapper.
"""

from __future__ import annotations

import json
import uuid
from datetime import date

import pytest

from src.db.models.plan_workouts import PlanWorkout
from src.db.models.plans import Plan
from src.db.models.user_athletes import UserAthleteLink
from src.smartcoach_mobile_coach.agent_tools import (
    execute_tool,
    tool_apply_plan_adjustments,
)

USER_ID = uuid.UUID("0b5e5a42-0000-4000-8000-0000003e2001")


@pytest.fixture
def seeded_plan(test_db_session):
    session = test_db_session
    session.add(UserAthleteLink(user_id=str(USER_ID), athlete_id=8201))
    plan = Plan(
        user_id=USER_ID,
        plan_name="Phase E tool fixture",
        race_date=date(2026, 6, 7),
        race_distance="Marathon",
        is_active=True,
        training_days=["Tue", "Wed", "Thu", "Fri", "Sat"],
    )
    session.add(plan)
    session.flush()

    rows = [
        (date(2026, 4, 13), "Easy Run", 4.0, "E", "easy"),
        (date(2026, 4, 14), "Easy Run", 4.0, "E", "easy"),
        (date(2026, 4, 15), "Tempo", 5.0, "T", "endurance"),
        (date(2026, 4, 16), "Easy Run", 4.0, "E", "easy"),
        (date(2026, 4, 18), "Long Run", 8.0, "E", "long"),
        (date(2026, 4, 21), "Easy Run", 4.0, "E", "easy"),
        (date(2026, 4, 22), "Easy Run", 4.0, "E", "easy"),
        (date(2026, 4, 23), "Tempo", 5.0, "T", "endurance"),
        (date(2026, 4, 24), "Easy Run", 4.0, "E", "easy"),
        (date(2026, 4, 25), "Long Run", 8.0, "E", "long"),
    ]
    for d, workout_type, miles, intensity, run_type_key in rows:
        session.add(
            PlanWorkout(
                plan_id=plan.id,
                date=d,
                workout_type=workout_type,
                description=workout_type,
                miles=miles,
                intensity=intensity,
                run_type_key=run_type_key,
                phase="Build",
            )
        )
    session.flush()
    return plan


def test_tool_rejects_non_uuid_user_id(test_db_session, seeded_plan):
    out = tool_apply_plan_adjustments(
        test_db_session,
        "not-a-uuid",
        {
            "week_start_date": "2026-04-20",
            "operations": [{"op": "adjust_volume", "delta_pct": 5}],
        },
    )
    assert out == {
        "error": "invalid_user_id",
        "message": "internal_user_id must be a UUID string.",
    }


def test_tool_applies_structured_adjustments_and_commits(test_db_session, seeded_plan):
    out = tool_apply_plan_adjustments(
        test_db_session,
        str(USER_ID),
        {
            "week_start_date": "2026-04-20",
            "operations": [{"op": "adjust_volume", "delta_pct": 10}],
        },
    )
    assert out["saved"] is True
    assert out["applied_count"] == 1
    assert out["week_total_miles_after"] == 27.5

    monday_run = (
        test_db_session.query(PlanWorkout)
        .filter(
            PlanWorkout.plan_id == seeded_plan.id, PlanWorkout.date == date(2026, 4, 21)
        )
        .one()
    )
    assert float(monday_run.miles) >= 4.0


def test_execute_tool_routes_apply_plan_adjustments(
    test_db_session, seeded_plan, monkeypatch
):
    from src.smartcoach_mobile_coach import agent_tools as _agent_tools

    monkeypatch.setattr(
        _agent_tools, "_increment_tool_call_count", lambda session, name: None
    )

    out = execute_tool(
        test_db_session,
        str(USER_ID),
        "apply_plan_adjustments",
        json.dumps(
            {
                "week_start_date": "2026-04-20",
                "operations": [{"op": "adjust_volume", "delta_pct": 5}],
            }
        ),
    )
    assert out["applied_count"] == 1, f"unexpected result: {out}"
    assert out["operations"][0]["status"] == "applied"
