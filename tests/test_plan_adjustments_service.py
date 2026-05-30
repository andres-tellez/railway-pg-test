"""
Tests for V1.6 Phase E minimal structured plan adjustments.

Focus:

* one canonical service path (`apply_plan_adjustments`)
* structured-op normalization (no free-text)
* volume cap (`±10%`) + 0.5-mile rounding
* quality increase cap (`+1/week`) + phase gates
* quality-floor `reason_code` requirement
* hard day-after-Long-Run protection
* per-operation audit-log rows in `weekly_decision_log`
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from src.db.models.plan_workouts import PlanWorkout
from src.db.models.plans import Plan
from src.db.models.user_athletes import UserAthleteLink
from src.db.models.weekly_decision_log import WeeklyDecisionLog
from src.services.plan.plan_adjustments import (
    PLAN_ADJUSTMENTS_SCHEMA_VERSION,
    apply_plan_adjustments,
)

USER_ID = uuid.UUID("0b5e5a42-0000-4000-8000-0000003e1001")
WEEK_START = date(2026, 4, 20)
PREV_WEEK_START = date(2026, 4, 13)


@pytest.fixture
def seeded_plan(test_db_session):
    session = test_db_session
    session.add(UserAthleteLink(user_id=str(USER_ID), athlete_id=8101))
    plan = Plan(
        user_id=USER_ID,
        plan_name="Phase E fixture",
        race_date=date(2026, 6, 7),
        race_distance="Marathon",
        is_active=True,
        training_days=["Tue", "Wed", "Thu", "Fri", "Sat"],
    )
    session.add(plan)
    session.flush()

    def _add(
        day: date, workout_type: str, miles: float, intensity: str, run_type_key: str
    ):
        session.add(
            PlanWorkout(
                plan_id=plan.id,
                date=day,
                workout_type=workout_type,
                description=workout_type,
                miles=miles,
                intensity=intensity,
                run_type_key=run_type_key,
                phase="Build",
            )
        )

    # Prior week baseline total = 25.0
    _add(date(2026, 4, 15), "Easy Run", 4.0, "z2", "easy")
    _add(date(2026, 4, 16), "Easy Run", 4.0, "z2", "easy")
    _add(date(2026, 4, 17), "Tempo", 5.0, "z3", "tempo")
    _add(date(2026, 4, 18), "Easy Run", 4.0, "z2", "easy")
    _add(date(2026, 4, 19), "Long Run", 8.0, "z2", "long_run")

    # Current week total = 25.0, one quality run, Sunday empty.
    _add(date(2026, 4, 21), "Easy Run", 4.0, "z2", "easy")
    _add(date(2026, 4, 22), "Easy Run", 4.0, "z2", "easy")
    _add(date(2026, 4, 23), "Tempo", 5.0, "z3", "tempo")
    _add(date(2026, 4, 24), "Easy Run", 4.0, "z2", "easy")
    _add(date(2026, 4, 25), "Long Run", 8.0, "z2", "long_run")

    session.flush()
    return plan


def test_adjust_volume_caps_to_plus_10_and_rounds_to_half_miles(
    test_db_session, seeded_plan
):
    status, payload = apply_plan_adjustments(
        test_db_session,
        USER_ID,
        week_start_date_raw=WEEK_START.isoformat(),
        operations_raw=[{"op": "adjust_volume", "delta_pct": 25}],
    )

    assert status == "ok"
    assert payload["schema_version"] == PLAN_ADJUSTMENTS_SCHEMA_VERSION
    assert payload["applied_count"] == 1
    assert payload["rejected_count"] == 0
    assert payload["baseline_total_miles"] == 25.0
    # Prior-week baseline 25.0 -> max +10% = 27.5
    assert payload["week_total_miles_after"] == 27.5
    op = payload["operations"][0]
    assert op["status"] == "applied"
    assert "volume_delta_pct_capped_10" in op["caps_applied"]

    current_rows = (
        test_db_session.query(PlanWorkout)
        .filter(
            PlanWorkout.plan_id == seeded_plan.id,
            PlanWorkout.date >= WEEK_START,
            PlanWorkout.date <= WEEK_START.replace(day=26),
        )
        .order_by(PlanWorkout.date)
        .all()
    )
    assert len(current_rows) == 5
    for workout in current_rows:
        half_units = round(float(workout.miles) * 2)
        assert abs(float(workout.miles) * 2 - half_units) < 1e-9


def test_adjust_intensity_increase_is_capped_to_plus_one(test_db_session, seeded_plan):
    status, payload = apply_plan_adjustments(
        test_db_session,
        USER_ID,
        week_start_date_raw=WEEK_START.isoformat(),
        operations_raw=[{"op": "adjust_intensity", "quality_delta": 3}],
    )

    assert status == "ok"
    assert payload["applied_count"] == 1
    op = payload["operations"][0]
    assert op["status"] == "applied"
    assert "quality_increase_capped_plus_1" in op["caps_applied"]
    assert op["normalized"]["quality_delta_applied"] == 1

    current_rows = (
        test_db_session.query(PlanWorkout)
        .filter(
            PlanWorkout.plan_id == seeded_plan.id,
            PlanWorkout.date >= WEEK_START,
            PlanWorkout.date <= WEEK_START.replace(day=26),
        )
        .order_by(PlanWorkout.date)
        .all()
    )
    quality_rows = [
        row
        for row in current_rows
        if row.intensity == "z3" and "tempo" in row.workout_type.lower()
    ]
    assert len(quality_rows) == 2


def test_quality_floor_requires_reason_code_on_decrease(test_db_session, seeded_plan):
    status, payload = apply_plan_adjustments(
        test_db_session,
        USER_ID,
        week_start_date_raw=WEEK_START.isoformat(),
        operations_raw=[{"op": "adjust_intensity", "quality_delta": -1}],
    )

    assert status == "ok"
    assert payload["applied_count"] == 0
    assert payload["rejected_count"] == 1
    op = payload["operations"][0]
    assert op["status"] == "rejected"
    assert op["normalized"]["requires_reason_code"] is True
    assert "reason_code" in op["message"]


def test_add_run_rejects_day_after_long_run(test_db_session, seeded_plan):
    status, payload = apply_plan_adjustments(
        test_db_session,
        USER_ID,
        week_start_date_raw=WEEK_START.isoformat(),
        operations_raw=[
            {"op": "add_run", "day": "Sunday", "run_type": "easy", "miles": 2}
        ],
    )

    assert status == "ok"
    op = payload["operations"][0]
    assert op["status"] == "rejected"
    assert "day after a Long Run" in op["message"]


def test_remove_run_cannot_remove_long_run(test_db_session, seeded_plan):
    status, payload = apply_plan_adjustments(
        test_db_session,
        USER_ID,
        week_start_date_raw=WEEK_START.isoformat(),
        operations_raw=[{"op": "remove_run", "day": "Saturday"}],
    )

    assert status == "ok"
    op = payload["operations"][0]
    assert op["status"] == "rejected"
    assert "Long Run anchor" in op["message"]


def test_add_run_is_capped_by_remaining_volume_headroom(test_db_session, seeded_plan):
    status, payload = apply_plan_adjustments(
        test_db_session,
        USER_ID,
        week_start_date_raw=WEEK_START.isoformat(),
        operations_raw=[
            {"op": "add_run", "day": "Sunday", "run_type": "easy", "miles": 5}
        ],
    )

    assert status == "ok"
    op = payload["operations"][0]
    assert op["status"] == "rejected"
    # Sunday is rejected by the hard recovery rule before the volume rule.
    assert op["audit_log_id"] is not None

    # Now add on Monday of the same week? That date is empty in the fixture.
    status2, payload2 = apply_plan_adjustments(
        test_db_session,
        USER_ID,
        week_start_date_raw=WEEK_START.isoformat(),
        operations_raw=[
            {"op": "add_run", "day": "Monday", "run_type": "easy", "miles": 5}
        ],
    )
    assert status2 == "ok"
    op2 = payload2["operations"][0]
    assert op2["status"] == "applied"
    assert "add_run_capped_by_weekly_volume" in op2["caps_applied"]
    assert op2["normalized"]["miles_applied"] == 2.5
    assert payload2["week_total_miles_after"] == 27.5


def test_each_requested_operation_creates_audit_log_row(test_db_session, seeded_plan):
    status, payload = apply_plan_adjustments(
        test_db_session,
        USER_ID,
        week_start_date_raw=WEEK_START.isoformat(),
        operations_raw=[
            {"op": "adjust_volume", "delta_pct": 8},
            {"op": "remove_run", "day": "Saturday"},
            {"op": "unsupported_thing"},
        ],
    )

    assert status == "ok"
    logs = (
        test_db_session.query(WeeklyDecisionLog)
        .filter(WeeklyDecisionLog.plan_id == seeded_plan.id)
        .order_by(WeeklyDecisionLog.id)
        .all()
    )
    assert len(logs) == 3
    assert all(
        log.adjustments_json["schema_version"] == PLAN_ADJUSTMENTS_SCHEMA_VERSION
        for log in logs
    )
    assert [entry["audit_log_id"] for entry in payload["operations"]] == [
        log.id for log in logs
    ]
