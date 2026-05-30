"""
Tests for V1.6 Phase B 3B.5 — ``tool_get_plan_overview``.

Covers:

* The tool returns the planned-only end-to-end plan overview payload
  for the athlete's active (or most recently created) plan.
* ``phase_blocks`` correctly groups consecutive same-phase plan weeks
  and attaches the canonical §8 ``phase_kpi_priority`` ordered
  emphasis list.
* ``volume_curve`` has one row per Monday-to-Sunday plan week with
  planned_runs + planned_miles_total + per-week phase + temporality
  (past / current / future) stamp.
* ``long_run_progression`` picks the weekly long run by the §-policy:
  prefer ``run_type_key == "long"``; otherwise the longest-miles
  workout of the week.
* §19.5 future-week "no actuals" rule structurally extends to every
  week in the overview: no ``Activity`` row is ever surfaced, even
  when a future-dated matched activity is seeded.
* Error envelopes:
    - non-UUID ``internal_user_id`` ⇒ ``invalid_user_id``.
    - no plan for the user ⇒ ``no_plan``.
* Dispatcher wiring via ``execute_tool("get_plan_overview", ...)``.
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

DEFAULT_USER_ID = uuid.UUID("0b5e5a42-0000-4000-8000-000000003b05")
DEFAULT_USER_ID_STR = str(DEFAULT_USER_ID)

# Pin "today" to mid-plan so the volume curve exercises past /
# current / future temporality stamps. 2026-04-22 is a Wednesday; the
# current week is 2026-04-20 (Mon) — 2026-04-26 (Sun).
FIXED_TODAY = date(2026, 4, 22)
PAST_MONDAY = date(2026, 4, 6)
CURRENT_MONDAY = date(2026, 4, 20)
FUTURE_MONDAY = date(2026, 5, 4)


@pytest.fixture(autouse=True)
def _pin_today(monkeypatch):
    """Pin ``get_today_date_in_timezone`` for deterministic temporality."""
    monkeypatch.setattr(
        "src.services.plan.plan_overview.get_today_date_in_timezone",
        lambda _tz: FIXED_TODAY,
    )


@pytest.fixture
def seeded_plan(test_db_session):
    """
    Four-week plan that spans a Base → Build phase transition and
    includes a canonical ``run_type_key == "long"`` Saturday session
    each week plus a Tuesday Easy session.

    Week 1 (past):     2026-04-06 Mon .. 2026-04-12 Sun   Base
        Tue easy 5 mi, Sat long 10 mi
    Week 2 (past):     2026-04-13 Mon .. 2026-04-19 Sun   Base
        Tue easy 5 mi, Sat long 11 mi
    Week 3 (current):  2026-04-20 Mon .. 2026-04-26 Sun   Build
        Tue easy 5 mi, Sat long 13 mi
    Week 4 (future):   2026-04-27 Mon .. 2026-05-03 Sun   Build
        Tue easy 5 mi, Sat long 14 mi

    A completed activity is matched to the current-week Tuesday so
    tests can prove the overview does NOT surface it (§19.5 extended
    to the overview). A landmine activity is seeded for the future
    long run to prove the overview skips the activity join entirely.
    """
    session = test_db_session
    session.add(UserAthleteLink(user_id=DEFAULT_USER_ID_STR, athlete_id=4242))
    plan = Plan(
        user_id=DEFAULT_USER_ID,
        plan_name="Plan Overview 3B.5 Test",
        race_date=date(2026, 6, 7),
        race_distance="Marathon",
        is_active=True,
        training_days=["Tue", "Sat"],
    )
    session.add(plan)
    session.flush()

    # (week_monday, phase, easy_miles, long_miles)
    week_specs = [
        (PAST_MONDAY, "Base", 5.0, 10.0),
        (date(2026, 4, 13), "Base", 5.0, 11.0),
        (CURRENT_MONDAY, "Build", 5.0, 13.0),
        (date(2026, 4, 27), "Build", 5.0, 14.0),
    ]

    workouts: dict[date, PlanWorkout] = {}
    for monday, phase, easy_mi, long_mi in week_specs:
        tue = monday + (date(2026, 4, 7) - date(2026, 4, 6))  # Mon + 1
        sat = monday + (date(2026, 4, 11) - date(2026, 4, 6))  # Mon + 5
        easy = PlanWorkout(
            plan_id=plan.id,
            date=tue,
            workout_type="Easy Run",
            description="Easy miles",
            miles=easy_mi,
            intensity="z2",
            run_type_key="easy",
            phase=phase,
        )
        long_run = PlanWorkout(
            plan_id=plan.id,
            date=sat,
            workout_type="Long Run",
            description="Weekend long",
            miles=long_mi,
            intensity="z2",
            run_type_key="long_run",
            phase=phase,
        )
        session.add_all([easy, long_run])
        session.flush()
        workouts[tue] = easy
        workouts[sat] = long_run

    # Real past-week completed activity matched to a plan workout.
    # The overview must NOT surface this — overview is planned-only.
    session.add(
        Activity(
            activity_id=424200,
            athlete_id=4242,
            user_id=DEFAULT_USER_ID,
            name="Past easy — real execution",
            type="Run",
            start_date=datetime(2026, 4, 7, 12, 0, tzinfo=timezone.utc),
            matched_plan_workout_id=workouts[date(2026, 4, 7)].id,
            planned_type="easy",
            executed_type="easy",
            run_score="green",
            zone_compliance_pct=85.0,
            planned_miles=5.0,
            actual_miles=5.0,
            completion_pct=100.0,
            conv_distance=5.0,
            moving_time=2700,
        )
    )
    # Landmine future-dated matched activity — should NEVER appear
    # in the overview because the service never reads Activity rows.
    session.add(
        Activity(
            activity_id=424201,
            athlete_id=4242,
            user_id=DEFAULT_USER_ID,
            name="LANDMINE future-dated overview activity",
            type="Run",
            start_date=datetime(2026, 5, 2, 12, 0, tzinfo=timezone.utc),
            matched_plan_workout_id=workouts[date(2026, 5, 2)].id,
            planned_type="long",
            executed_type="long",
            run_score="green",
            zone_compliance_pct=80.0,
            planned_miles=14.0,
            actual_miles=14.0,
            completion_pct=100.0,
            conv_distance=14.0,
            moving_time=7200,
        )
    )
    session.commit()
    return {"plan": plan, "workouts": workouts}


# ---------------------------------------------------------------------------
# Error envelopes
# ---------------------------------------------------------------------------


def test_tool_rejects_non_uuid_user_id(test_db_session):
    out = agent_tools.tool_get_plan_overview(test_db_session, "not-a-uuid")
    assert out["error"] == "invalid_user_id"


def test_tool_returns_error_envelope_when_no_plan_exists(test_db_session):
    session = test_db_session
    session.add(UserAthleteLink(user_id=DEFAULT_USER_ID_STR, athlete_id=4242))
    session.commit()
    out = agent_tools.tool_get_plan_overview(session, DEFAULT_USER_ID_STR)
    assert out["error"] == "no_plan"


# ---------------------------------------------------------------------------
# Shape — plan-level totals
# ---------------------------------------------------------------------------


def test_overview_exposes_plan_metadata(test_db_session, seeded_plan):
    out = agent_tools.tool_get_plan_overview(test_db_session, DEFAULT_USER_ID_STR)
    plan = seeded_plan["plan"]
    assert out["plan_id"] == plan.id
    assert out["plan_name"] == "Plan Overview 3B.5 Test"
    assert out["race_date"] == "2026-06-07"
    assert out["race_distance"] == "Marathon"
    assert out["plan_start"] == PAST_MONDAY.isoformat()
    assert out["plan_end"] == "2026-05-03"  # Sunday of week 4
    assert out["total_weeks"] == 4


def test_overview_exposes_plan_totals(test_db_session, seeded_plan):
    out = agent_tools.tool_get_plan_overview(test_db_session, DEFAULT_USER_ID_STR)
    # 4 weeks * 2 runs = 8 planned runs.
    assert out["total_planned_runs"] == 8
    # Easy 5*4 = 20, long 10+11+13+14 = 48 → 68.
    assert out["total_planned_miles"] == pytest.approx(68.0)


# ---------------------------------------------------------------------------
# Volume curve
# ---------------------------------------------------------------------------


def test_volume_curve_has_one_row_per_plan_week(test_db_session, seeded_plan):
    out = agent_tools.tool_get_plan_overview(test_db_session, DEFAULT_USER_ID_STR)
    vc = out["volume_curve"]
    assert [row["week_index"] for row in vc] == [1, 2, 3, 4]
    assert [row["week_start"] for row in vc] == [
        "2026-04-06",
        "2026-04-13",
        "2026-04-20",
        "2026-04-27",
    ]


def test_volume_curve_counts_planned_runs_and_miles(test_db_session, seeded_plan):
    out = agent_tools.tool_get_plan_overview(test_db_session, DEFAULT_USER_ID_STR)
    vc = out["volume_curve"]
    for row in vc:
        assert row["planned_runs"] == 2
    miles = [row["planned_miles_total"] for row in vc]
    assert miles == pytest.approx([15.0, 16.0, 18.0, 19.0])


def test_volume_curve_stamps_per_week_temporality(test_db_session, seeded_plan):
    out = agent_tools.tool_get_plan_overview(test_db_session, DEFAULT_USER_ID_STR)
    temps = [row["week_temporality"] for row in out["volume_curve"]]
    # With FIXED_TODAY = Wed 2026-04-22:
    #   wk1 2026-04-06 = past
    #   wk2 2026-04-13 = past
    #   wk3 2026-04-20 = current
    #   wk4 2026-04-27 = future
    assert temps == ["past", "past", "current", "future"]


def test_volume_curve_resolves_phase_per_week(test_db_session, seeded_plan):
    out = agent_tools.tool_get_plan_overview(test_db_session, DEFAULT_USER_ID_STR)
    phases = [row["phase"] for row in out["volume_curve"]]
    assert phases == ["Base", "Base", "Build", "Build"]


# ---------------------------------------------------------------------------
# Phase blocks
# ---------------------------------------------------------------------------


def test_phase_blocks_group_consecutive_same_phase_weeks(test_db_session, seeded_plan):
    out = agent_tools.tool_get_plan_overview(test_db_session, DEFAULT_USER_ID_STR)
    blocks = out["phase_blocks"]
    # Exactly two blocks: Base (weeks 1-2), Build (weeks 3-4).
    assert [b["phase"] for b in blocks] == ["Base", "Build"]
    assert blocks[0]["start_week"] == 1
    assert blocks[0]["end_week"] == 2
    assert blocks[0]["num_weeks"] == 2
    assert blocks[0]["num_runs"] == 4
    assert blocks[0]["total_miles"] == pytest.approx(31.0)  # 15 + 16
    assert blocks[1]["start_week"] == 3
    assert blocks[1]["end_week"] == 4
    assert blocks[1]["num_weeks"] == 2
    assert blocks[1]["num_runs"] == 4
    assert blocks[1]["total_miles"] == pytest.approx(37.0)  # 18 + 19


def test_phase_blocks_attach_canonical_kpi_priority(test_db_session, seeded_plan):
    out = agent_tools.tool_get_plan_overview(test_db_session, DEFAULT_USER_ID_STR)
    base = out["phase_blocks"][0]
    build = out["phase_blocks"][1]
    # §8 Base order: HR Drift → Aerobic Efficiency → Easy zone compliance.
    assert [e["kpi_id"] for e in base["phase_kpi_priority"]] == [
        "hr_drift",
        "aerobic_efficiency",
        "easy_zone_compliance",
    ]
    # §8 Build order: Pace Consistency (Tempo) → Quality zone compliance → HR Drift.
    assert [e["kpi_id"] for e in build["phase_kpi_priority"]] == [
        "pace_consistency_tempo",
        "quality_zone_compliance",
        "hr_drift",
    ]


# ---------------------------------------------------------------------------
# Long-run progression
# ---------------------------------------------------------------------------


def test_long_run_progression_picks_run_type_long(test_db_session, seeded_plan):
    out = agent_tools.tool_get_plan_overview(test_db_session, DEFAULT_USER_ID_STR)
    lrp = out["long_run_progression"]
    assert len(lrp) == 4
    assert [row["long_run_miles"] for row in lrp] == pytest.approx(
        [10.0, 11.0, 13.0, 14.0]
    )
    # All four weeks have a canonical "long" workout, so the type is
    # consistently "long".
    assert [row["long_run_type"] for row in lrp] == ["long", "long", "long", "long"]
    # Long-run dates are the Saturdays of each week.
    assert [row["long_run_date"] for row in lrp] == [
        "2026-04-11",
        "2026-04-18",
        "2026-04-25",
        "2026-05-02",
    ]


def test_long_run_progression_falls_back_to_longest_workout(test_db_session):
    """
    When no workout has ``run_type_key == "long"``, the selector
    degrades to the longest-miles workout of the week so the coach
    always has a progression anchor to narrate.
    """
    session = test_db_session
    session.add(UserAthleteLink(user_id=DEFAULT_USER_ID_STR, athlete_id=4242))
    plan = Plan(
        user_id=DEFAULT_USER_ID,
        plan_name="No-long-runs plan",
        race_date=None,
        is_active=True,
        training_days=["Tue", "Thu"],
    )
    session.add(plan)
    session.flush()
    session.add_all(
        [
            PlanWorkout(
                plan_id=plan.id,
                date=date(2026, 4, 7),
                workout_type="Easy",
                description="",
                miles=4.0,
                intensity="z2",
                run_type_key="easy",
                phase="Base",
            ),
            PlanWorkout(
                plan_id=plan.id,
                date=date(2026, 4, 9),
                workout_type="Steady",
                description="",
                miles=7.0,
                intensity="z3",
                run_type_key="easy",
                phase="Base",
            ),
        ]
    )
    session.commit()

    out = agent_tools.tool_get_plan_overview(session, DEFAULT_USER_ID_STR)
    lrp = out["long_run_progression"]
    assert len(lrp) == 1
    assert lrp[0]["long_run_miles"] == pytest.approx(7.0)
    assert lrp[0]["long_run_type"] == "easy"
    assert lrp[0]["long_run_date"] == "2026-04-09"


# ---------------------------------------------------------------------------
# §19.5 no-actuals — extended to the whole overview
# ---------------------------------------------------------------------------


def test_overview_never_surfaces_activity_ids(test_db_session, seeded_plan):
    """
    The overview is planned-only. A completed past-week activity was
    seeded in the fixture; the overview payload MUST NOT contain its
    ``activity_id`` anywhere.
    """
    out = agent_tools.tool_get_plan_overview(test_db_session, DEFAULT_USER_ID_STR)
    # Serialize and check structurally — we don't know a priori which
    # shape a leak would take; checking the full JSON is the strongest
    # assertion.
    serialized = json.dumps(out)
    assert "424200" not in serialized
    assert "424201" not in serialized  # landmine too


def test_overview_payload_does_not_contain_actual_namespace(
    test_db_session, seeded_plan
):
    """
    Belt-and-braces: the overview should not carry any ``actual``
    namespaced field, regardless of which week you look at. Any
    occurrence would indicate a future regression where someone
    wired ``get_plan_overview`` to a weekly-plan call chain that
    does read activities.
    """
    out = agent_tools.tool_get_plan_overview(test_db_session, DEFAULT_USER_ID_STR)
    serialized = json.dumps(out)
    assert '"actual"' not in serialized
    assert "zone_compliance_pct" not in serialized
    assert "deviation_direction" not in serialized


# ---------------------------------------------------------------------------
# Dispatcher wiring
# ---------------------------------------------------------------------------


def test_execute_tool_dispatches_get_plan_overview(test_db_session, seeded_plan):
    out = agent_tools.execute_tool(
        test_db_session,
        DEFAULT_USER_ID_STR,
        "get_plan_overview",
        "{}",
    )
    assert out["plan_name"] == "Plan Overview 3B.5 Test"
    assert out["total_weeks"] == 4


def test_execute_tool_accepts_tz_argument(test_db_session, seeded_plan):
    out = agent_tools.execute_tool(
        test_db_session,
        DEFAULT_USER_ID_STR,
        "get_plan_overview",
        json.dumps({"tz": "America/Denver"}),
    )
    assert out["timezone"] == "America/Denver"


def test_execute_tool_ignores_invalid_json_arguments(test_db_session, seeded_plan):
    out = agent_tools.execute_tool(
        test_db_session,
        DEFAULT_USER_ID_STR,
        "get_plan_overview",
        "not-json",
    )
    assert out["error"] == "invalid_arguments"
