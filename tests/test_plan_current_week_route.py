"""Tests for GET /api/plan/current-week."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone

import pytest

from src.db.models.activities import Activity
from src.db.models.plan_workouts import PlanWorkout
from src.db.models.plans import Plan
from src.db.models.user_athletes import UserAthleteLink

DEFAULT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture(autouse=True)
def stub_resolve_user_id_for_plan_tests(monkeypatch):
    """
    JWT resolution uses user_identity_dao.get_session (import-time binding),
    which does not share the test_db_session connection. Stub the resolver so
    @requires_auth sets g.user_id consistently with seeded rows.
    """
    monkeypatch.setattr(
        "src.utils.auth0_jwt.resolve_user_id_from_auth_provider",
        lambda *args, **kwargs: DEFAULT_USER_ID,
    )


@pytest.fixture
def plan_routes_db(monkeypatch, test_db_session):
    """Route module imported `get_session` by name; patch the route module binding."""

    class _SessCM:
        def __enter__(self):
            return test_db_session

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("src.routes.plan_routes.get_session", lambda: _SessCM())
    yield test_db_session


def _seed_week_plan_and_activity(session, *, workout_date: date):
    session.add(
        UserAthleteLink(
            user_id=str(DEFAULT_USER_ID),
            athlete_id=99901,
        )
    )
    plan = Plan(
        user_id=DEFAULT_USER_ID,
        plan_name="Week Test Plan",
        race_date=workout_date,
        race_distance="Half",
        is_active=True,
    )
    session.add(plan)
    session.flush()
    workout = PlanWorkout(
        plan_id=plan.id,
        date=workout_date,
        workout_type="Easy Run",
        description="Easy miles",
        miles=5.0,
        intensity="E",
        run_type_key="easy",
    )
    session.add(workout)
    session.flush()
    activity = Activity(
        activity_id=880011,
        athlete_id=99901,
        user_id=DEFAULT_USER_ID,
        name="Morning easy",
        type="Run",
        start_date=datetime(
            workout_date.year,
            workout_date.month,
            workout_date.day,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        matched_plan_workout_id=workout.id,
        planned_type="easy",
        executed_type="easy",
        run_score="green",
        zone_compliance_pct=80.0,
        planned_miles=5.0,
        actual_miles=5.0,
        completion_pct=100.0,
        conv_distance=5.0,
        moving_time=2700,
        average_heartrate=138.4,
    )
    session.add(activity)
    session.commit()
    return plan, workout


def test_current_week_returns_days_and_execution(
    client,
    auth_header,
    plan_routes_db,
    monkeypatch,
):
    workout_date = date(2026, 4, 21)
    _seed_week_plan_and_activity(plan_routes_db, workout_date=workout_date)
    monkeypatch.setattr(
        "src.routes.plan_routes.get_today_date_in_timezone",
        lambda _tz: date(2026, 4, 22),
    )

    resp = client.get(
        "/api/plan/current-week?tz=UTC",
        headers=auth_header(),
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["week_start"] == "2026-04-20"
    assert data["week_end"] == "2026-04-26"
    assert data["today"] == "2026-04-22"
    assert len(data["days"]) == 1
    day = data["days"][0]
    assert day["date"] == "2026-04-21"
    assert day["run_type_key"] == "easy"
    assert day["run_type"]["display_name"] == "Easy"
    assert day["execution"] is not None
    assert day["execution"]["activity_id"] == 880011
    assert day["execution"]["run_score"] == "green"
    assert day["execution"]["average_heartrate"] == 138
    assert day["execution"]["avg_pace_per_mile"] == "9:00/mi"

    # V1.6 0.E: /current-week must emit the canonical §6 namespaced
    # shape alongside the legacy flat fields. Mobile consumes from
    # here as of 0.E.
    assert "planned" in day["execution"]
    assert "actual" in day["execution"]
    assert day["execution"]["planned"]["type"] == day["execution"]["planned_type"]
    assert day["execution"]["planned"]["miles"] == day["execution"]["planned_miles"]
    assert day["execution"]["actual"]["type"] == day["execution"]["executed_type"]
    assert day["execution"]["actual"]["miles"] == day["execution"]["actual_miles"]
    assert (
        day["execution"]["actual"]["average_heartrate"]
        == day["execution"]["average_heartrate"]
    )
    assert (
        day["execution"]["actual"]["avg_pace_per_mile"]
        == day["execution"]["avg_pace_per_mile"]
    )


def test_current_week_uses_canonical_normalization_for_legacy_rows(
    client,
    auth_header,
    plan_routes_db,
    monkeypatch,
):
    """
    V1.6 Pre-Phase A 0.D regression test.

    The ``plan_workouts.chk_run_type_key`` constraint currently accepts
    ``easy``/``steady``/``endurance``/``long``. ``endurance`` is a
    non-canonical run type that MUST be normalized to canonical ``long``
    via ``LEGACY_TO_CANONICAL_RUN_TYPE`` at the GET path. Before 0.D,
    text-matching inference could produce its own divergent key. This
    test locks in that the canonical map is the single source of truth.

    Also verifies that the stored ``target_hr`` is returned as-is — the
    GET path MUST NOT revalidate or rewrite HR zones (the old
    "zone mismatch → expected_hr" mutation was deleted in 0.D).
    """
    workout_date = date(2026, 4, 22)
    plan_routes_db.add(UserAthleteLink(user_id=str(DEFAULT_USER_ID), athlete_id=99902))
    plan = Plan(
        user_id=DEFAULT_USER_ID,
        plan_name="Legacy",
        race_date=workout_date,
        race_distance="Half",
        is_active=True,
    )
    plan_routes_db.add(plan)
    plan_routes_db.flush()
    plan_routes_db.add(
        PlanWorkout(
            plan_id=plan.id,
            date=workout_date,
            workout_type="Long Run",
            description="Legacy endurance",
            miles=12.0,
            intensity="E",
            run_type_key="endurance",
            # Intentionally stored under a zone that wouldn't match a
            # recomputation for "long" (Z2) — proves the GET path doesn't
            # rewrite the stored value.
            target_hr="Z4 (170-180 bpm)",
        )
    )
    plan_routes_db.commit()

    monkeypatch.setattr(
        "src.routes.plan_routes.get_today_date_in_timezone",
        lambda _tz: workout_date,
    )

    resp = client.get("/api/plan/current-week?tz=UTC", headers=auth_header())
    assert resp.status_code == 200
    data = json.loads(resp.data)
    day = data["days"][0]
    assert day["run_type_key"] == "long", (
        "legacy 'endurance' must normalize to canonical 'long' via "
        "LEGACY_TO_CANONICAL_RUN_TYPE — the single source of truth"
    )
    assert day["run_type"]["display_name"] == "Long"
    assert day["target_hr"] == "Z4 (170-180 bpm)", (
        "stored target_hr must be returned verbatim; GET path must not "
        "revalidate/rewrite HR zones (0.D deletion)"
    )


def test_current_week_fallback_computes_target_hr_when_missing(
    client,
    auth_header,
    plan_routes_db,
    monkeypatch,
):
    """
    V1.6 Pre-Phase A 0.D: stored ``target_hr`` is authoritative, but when
    a row truly lacks one (legacy rows predating ``target_hr`` persistence)
    the GET path may compute it ONCE from the canonical run_type_key. No
    text-matching inference; no zone revalidation.
    """
    workout_date = date(2026, 4, 22)
    plan_routes_db.add(UserAthleteLink(user_id=str(DEFAULT_USER_ID), athlete_id=99903))
    plan = Plan(
        user_id=DEFAULT_USER_ID,
        plan_name="NoHR",
        race_date=workout_date,
        race_distance="Half",
        is_active=True,
    )
    plan_routes_db.add(plan)
    plan_routes_db.flush()
    plan_routes_db.add(
        PlanWorkout(
            plan_id=plan.id,
            date=workout_date,
            workout_type="Easy Run",
            description="Easy, no HR stored",
            miles=4.0,
            intensity="E",
            run_type_key="easy",
            target_hr=None,
        )
    )
    plan_routes_db.commit()

    monkeypatch.setattr(
        "src.routes.plan_routes.get_today_date_in_timezone",
        lambda _tz: workout_date,
    )

    resp = client.get("/api/plan/current-week?tz=UTC", headers=auth_header())
    assert resp.status_code == 200
    day = json.loads(resp.data)["days"][0]
    assert day["run_type_key"] == "easy"
    assert day["target_hr"], "fallback must compute target_hr when stored value missing"
    assert "Z" in day["target_hr"], "fallback must return a canonical Z[1-5] zone label"


def test_current_week_empty_when_no_workouts_in_range(
    client,
    auth_header,
    plan_routes_db,
    monkeypatch,
):
    plan = Plan(
        user_id=DEFAULT_USER_ID,
        plan_name="Off week",
        race_date=date(2026, 6, 1),
        race_distance="10K",
        is_active=True,
    )
    plan_routes_db.add(plan)
    plan_routes_db.flush()
    plan_routes_db.add(
        PlanWorkout(
            plan_id=plan.id,
            date=date(2026, 5, 1),
            workout_type="Easy",
            description="Far away",
            miles=3.0,
            intensity="E",
            run_type_key="easy",
        )
    )
    plan_routes_db.commit()

    monkeypatch.setattr(
        "src.routes.plan_routes.get_today_date_in_timezone",
        lambda _tz: date(2026, 4, 22),
    )

    resp = client.get("/api/plan/current-week?tz=UTC", headers=auth_header())
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["days"] == []
