"""
Tests for V1.6 Phase B 3B.2–3B.4 — ``tool_get_weekly_plan``.

Covers:

* **3B.2** — The tool returns the V1.6 §6 weekly-plan payload for any
  past / current / future Monday-to-Sunday window. When
  ``week_start_iso`` is omitted, it resolves to the athlete's current
  week. Malformed values degrade to current-week rather than raising.
* **3B.3** — Future-week payload contract is enforced structurally:
  every day's ``execution`` is ``None``, every day's ``plan_status`` is
  ``"planned_only"``, the weekly ``adherence`` block is ``None``, and
  no activity is ever surfaced in the payload (even if an activity
  happens to be seeded for a future-week planned workout, the builder
  skips the join and the ``actual.*`` namespace cannot leak).
* **3B.4** — For PAST / CURRENT weeks, the payload contains the
  canonical weekly ``adherence`` block (produced by
  ``compute_weekly_adherence``) and the week-level ``phase_kpi_priority``
  block (produced by ``compute_phase_kpi_priority_for_week``) so the
  coach can calibrate tone and emphasis without recomputing either.
* **§X.5 single-source-of-truth** — The tool payload for the current
  week matches the ``GET /api/plan/current-week`` payload byte-exact
  (both delegate to ``build_weekly_plan_payload``).
* **Dispatcher** — ``execute_tool("get_weekly_plan", ...)`` routes to
  ``tool_get_weekly_plan`` and parses the ``week_start_iso`` arg.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone

import pytest

from src.db.models.activities import Activity
from src.db.models.plan_workouts import PlanWorkout
from src.db.models.plans import Plan
from src.db.models.user_athletes import UserAthleteLink
from src.smartcoach_mobile_coach import agent_tools

DEFAULT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_USER_ID_STR = str(DEFAULT_USER_ID)

# A fixed "today" across all tests — 2026-04-22 is a Wednesday, so the
# current week is 2026-04-20 (Mon) — 2026-04-26 (Sun). Choose past and
# future weeks relative to this anchor:
#   past_monday    = 2026-04-06
#   current_monday = 2026-04-20
#   future_monday  = 2026-05-04
FIXED_TODAY = date(2026, 4, 22)
CURRENT_MONDAY = date(2026, 4, 20)
PAST_MONDAY = date(2026, 4, 6)
FUTURE_MONDAY = date(2026, 5, 4)


@pytest.fixture(autouse=True)
def _pin_today(monkeypatch):
    """
    Pin ``weekly_plan.get_today_date_in_timezone`` so every test has a
    deterministic notion of "today". The weekly-plan service is the
    single consumer of this helper inside the tool path, so patching
    it here is sufficient (the HTTP route delegates to the same call
    chain).
    """
    monkeypatch.setattr(
        "src.services.plan.weekly_plan.get_today_date_in_timezone",
        lambda _tz: FIXED_TODAY,
    )


@pytest.fixture
def seeded_plan(test_db_session):
    """
    Seed a three-week plan window with one Easy workout per Tuesday and
    a completed activity matched to the CURRENT-week workout.

    Tuesdays were chosen to exercise weekday resolution — the fixed
    today (Wed 2026-04-22) is one day after the current-week Tuesday,
    so the ``plan_status`` for past weeks' Tuesdays is ``missed``
    (no activity), for the current week is ``executed`` (has an
    activity), and for the future week is ``planned_only``.
    """
    session = test_db_session
    session.add(UserAthleteLink(user_id=DEFAULT_USER_ID_STR, athlete_id=99901))
    plan = Plan(
        user_id=DEFAULT_USER_ID,
        plan_name="Weekly Plan 3B.2 Test",
        race_date=FUTURE_MONDAY,
        race_distance="Half",
        is_active=True,
        training_days=["Tue"],
    )
    session.add(plan)
    session.flush()

    tuesdays = [
        date(2026, 4, 7),  # past week
        date(2026, 4, 21),  # current week
        date(2026, 5, 5),  # future week
    ]
    workouts: dict[date, PlanWorkout] = {}
    for i, d in enumerate(tuesdays):
        w = PlanWorkout(
            plan_id=plan.id,
            date=d,
            workout_type="Easy Run",
            description=f"Easy miles week {i}",
            miles=5.0,
            intensity="E",
            run_type_key="easy",
            phase="Base",
        )
        session.add(w)
        session.flush()
        workouts[d] = w

    # Matched activity only for the CURRENT-week workout. Use a Z2
    # HR distribution so deviation_direction = on_target for the
    # Easy plan (V1.6 §5).
    session.add(
        Activity(
            activity_id=881100,
            athlete_id=99901,
            user_id=DEFAULT_USER_ID,
            name="Current-week easy",
            type="Run",
            start_date=datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc),
            matched_plan_workout_id=workouts[date(2026, 4, 21)].id,
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
            hr_zone_1=0,
            hr_zone_2=2700,
            hr_zone_3=0,
            hr_zone_4=0,
            hr_zone_5=0,
        )
    )

    # Extra "landmine" activity on a FUTURE-week Tuesday. The
    # future-week contract says the activity join must be skipped
    # entirely — this row exists to prove the tool can't leak it.
    # In real data you would never have a future-dated matched
    # activity, but a mis-timed backfill / test seed could produce
    # one; the contract must hold regardless.
    session.add(
        Activity(
            activity_id=881101,
            athlete_id=99901,
            user_id=DEFAULT_USER_ID,
            name="LANDMINE future-dated activity",
            type="Run",
            start_date=datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc),
            matched_plan_workout_id=workouts[date(2026, 5, 5)].id,
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
            hr_zone_1=0,
            hr_zone_2=2700,
            hr_zone_3=0,
            hr_zone_4=0,
            hr_zone_5=0,
        )
    )
    session.commit()
    return {"plan": plan, "workouts": workouts}


# ---------------------------------------------------------------------------
# 3B.2 — week-start resolution
# ---------------------------------------------------------------------------


def test_tool_defaults_to_current_week_when_week_start_omitted(
    test_db_session, seeded_plan
):
    out = agent_tools.tool_get_weekly_plan(test_db_session, DEFAULT_USER_ID_STR)
    assert out["week_start"] == CURRENT_MONDAY.isoformat()
    assert out["week_end"] == "2026-04-26"
    assert out["week_temporality"] == "current"


def test_tool_accepts_any_date_within_target_week(test_db_session, seeded_plan):
    # Pass a Friday — the service should still normalize to Monday.
    out = agent_tools.tool_get_weekly_plan(
        test_db_session,
        DEFAULT_USER_ID_STR,
        week_start_iso="2026-04-10",  # Friday of past week
    )
    assert out["week_start"] == PAST_MONDAY.isoformat()
    assert out["week_temporality"] == "past"


def test_tool_parses_datetime_string_form(test_db_session, seeded_plan):
    out = agent_tools.tool_get_weekly_plan(
        test_db_session,
        DEFAULT_USER_ID_STR,
        week_start_iso="2026-05-04T00:00:00",
    )
    assert out["week_start"] == FUTURE_MONDAY.isoformat()
    assert out["week_temporality"] == "future"


def test_tool_malformed_week_start_iso_degrades_to_current_week(
    test_db_session, seeded_plan
):
    """
    The parser returns ``None`` on malformed input and the builder
    treats ``None`` as "current week" — the LLM never gets an error
    envelope for a typo, it gets a useful payload.
    """
    out = agent_tools.tool_get_weekly_plan(
        test_db_session,
        DEFAULT_USER_ID_STR,
        week_start_iso="not-a-date",
    )
    assert out["week_start"] == CURRENT_MONDAY.isoformat()
    assert out["week_temporality"] == "current"


def test_tool_rejects_non_uuid_user_id(test_db_session):
    out = agent_tools.tool_get_weekly_plan(test_db_session, "not-a-uuid")
    assert out["error"] == "invalid_user_id"


def test_tool_returns_error_envelope_when_no_plan_exists(test_db_session):
    session = test_db_session
    session.add(UserAthleteLink(user_id=DEFAULT_USER_ID_STR, athlete_id=99901))
    session.commit()
    out = agent_tools.tool_get_weekly_plan(session, DEFAULT_USER_ID_STR)
    assert out["error"] == "no_plan"


# ---------------------------------------------------------------------------
# 3B.3 — future-week payload contract enforced structurally
# ---------------------------------------------------------------------------


def test_future_week_has_no_execution_on_any_day(test_db_session, seeded_plan):
    out = agent_tools.tool_get_weekly_plan(
        test_db_session,
        DEFAULT_USER_ID_STR,
        week_start_iso=FUTURE_MONDAY.isoformat(),
    )
    assert out["week_temporality"] == "future"
    assert len(out["days"]) == 1
    for day in out["days"]:
        # §19.5: future weeks have no actuals. The ``execution``
        # block is None, full stop.
        assert day["execution"] is None


def test_future_week_plan_status_is_planned_only(test_db_session, seeded_plan):
    out = agent_tools.tool_get_weekly_plan(
        test_db_session,
        DEFAULT_USER_ID_STR,
        week_start_iso=FUTURE_MONDAY.isoformat(),
    )
    for day in out["days"]:
        assert day["plan_status"] == "planned_only"
        assert day["violated_rest_day"] is False


def test_future_week_adherence_is_null(test_db_session, seeded_plan):
    out = agent_tools.tool_get_weekly_plan(
        test_db_session,
        DEFAULT_USER_ID_STR,
        week_start_iso=FUTURE_MONDAY.isoformat(),
    )
    # Nothing to aggregate → adherence block is None. This is
    # stronger than "empty" — the LLM never sees a 0% adherence
    # signal for a future week, which would be meaningless and
    # could lead to adversarial coaching.
    assert out["adherence"] is None


def test_future_week_phase_priority_still_emitted(test_db_session, seeded_plan):
    """
    §8 / §19.4: phase emphasis describes planned phase, not
    execution — future-week emphasis is valid because the coach
    can explain what to focus on, even without any runs yet.
    """
    out = agent_tools.tool_get_weekly_plan(
        test_db_session,
        DEFAULT_USER_ID_STR,
        week_start_iso=FUTURE_MONDAY.isoformat(),
    )
    assert out["phase_kpi_priority"] is not None
    assert out["phase_kpi_priority"]["phase"] == "Base"
    assert [e["kpi_id"] for e in out["phase_kpi_priority"]["priority"]] == [
        "hr_drift",
        "aerobic_efficiency",
        "easy_zone_compliance",
    ]


def test_future_week_does_not_surface_seeded_landmine_activity(
    test_db_session, seeded_plan
):
    """
    The ``seeded_plan`` fixture seeds a future-dated matched
    activity (``activity_id=881101``). The 3B.3 contract says the
    activity join is skipped entirely for future weeks — so even
    this adversarial seed cannot leak into the payload.
    """
    out = agent_tools.tool_get_weekly_plan(
        test_db_session,
        DEFAULT_USER_ID_STR,
        week_start_iso=FUTURE_MONDAY.isoformat(),
    )
    serialized = json.dumps(out)
    assert "881101" not in serialized
    assert "LANDMINE" not in serialized


# ---------------------------------------------------------------------------
# 3B.4 — past / current weeks include adherence + phase_kpi_priority
# ---------------------------------------------------------------------------


def test_current_week_has_adherence_block_with_expected_fields(
    test_db_session, seeded_plan
):
    out = agent_tools.tool_get_weekly_plan(test_db_session, DEFAULT_USER_ID_STR)
    assert out["week_temporality"] == "current"
    adh = out["adherence"]
    assert adh is not None
    # 1 planned workout, 1 completed → 100 %.
    assert adh["planned_runs"] == 1
    assert adh["completed_runs"] == 1
    assert adh["adherence_runs_pct"] == 100.0
    assert adh["band"] == "high"
    # Supporting weekly mileage aggregate.
    assert adh["planned_miles_total"] == 5.0
    assert adh["actual_miles_matched_total"] == 5.0


def test_current_week_has_phase_kpi_priority_block(test_db_session, seeded_plan):
    out = agent_tools.tool_get_weekly_plan(test_db_session, DEFAULT_USER_ID_STR)
    pk = out["phase_kpi_priority"]
    assert pk is not None
    assert pk["phase"] == "Base"
    # V1.6 §8 Base ordered list verbatim.
    assert [e["kpi_id"] for e in pk["priority"]] == [
        "hr_drift",
        "aerobic_efficiency",
        "easy_zone_compliance",
    ]


def test_past_week_missed_workout_is_reflected_in_adherence(
    test_db_session, seeded_plan
):
    """
    Past week's Tuesday workout has no activity → ``plan_status``
    is ``missed``, adherence_runs_pct = 0 %, band = low. This is
    the 3B.4 "calibrate tone by adherence band" signal.
    """
    out = agent_tools.tool_get_weekly_plan(
        test_db_session,
        DEFAULT_USER_ID_STR,
        week_start_iso=PAST_MONDAY.isoformat(),
    )
    assert out["week_temporality"] == "past"
    assert len(out["days"]) == 1
    assert out["days"][0]["plan_status"] == "missed"
    assert out["days"][0]["execution"] is None
    assert out["adherence"]["completed_runs"] == 0
    assert out["adherence"]["adherence_runs_pct"] == 0.0
    assert out["adherence"]["band"] == "low"


# ---------------------------------------------------------------------------
# §X.5 — single-source-of-truth parity with /api/plan/current-week
# ---------------------------------------------------------------------------


def test_tool_payload_matches_http_route_payload_byte_exact(
    client, auth_header, test_db_session, monkeypatch, seeded_plan
):
    """
    The LLM tool and the mobile HTTP route delegate to the same
    service — they must produce identical payloads for the same
    week. Any future drift between the two is a §X.5 violation.
    """

    # Route-side plumbing: patch its get_session to use test_db_session.
    class _SessCM:
        def __enter__(self):
            return test_db_session

        def __exit__(self, *a):
            return False

    monkeypatch.setattr("src.routes.plan_routes.get_session", lambda: _SessCM())
    monkeypatch.setattr(
        "src.utils.auth0_jwt.resolve_user_id_from_auth_provider",
        lambda *a, **kw: DEFAULT_USER_ID,
    )

    resp = client.get(
        "/api/plan/current-week?tz=UTC",
        headers=auth_header(),
    )
    assert resp.status_code == 200
    route_payload = json.loads(resp.data)

    tool_payload = agent_tools.tool_get_weekly_plan(
        test_db_session, DEFAULT_USER_ID_STR, tz="UTC"
    )

    assert tool_payload == route_payload


# ---------------------------------------------------------------------------
# Dispatcher wiring
# ---------------------------------------------------------------------------


def test_execute_tool_routes_get_weekly_plan(test_db_session, seeded_plan):
    out = agent_tools.execute_tool(
        test_db_session,
        DEFAULT_USER_ID_STR,
        "get_weekly_plan",
        json.dumps({"week_start_iso": PAST_MONDAY.isoformat()}),
    )
    assert out["week_temporality"] == "past"
    assert out["week_start"] == PAST_MONDAY.isoformat()


def test_execute_tool_get_weekly_plan_empty_args_returns_current_week(
    test_db_session, seeded_plan
):
    out = agent_tools.execute_tool(
        test_db_session, DEFAULT_USER_ID_STR, "get_weekly_plan", "{}"
    )
    assert out["week_temporality"] == "current"
