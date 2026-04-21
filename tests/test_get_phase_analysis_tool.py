"""
Tests for V1.6 Phase B 3B.6 — ``tool_get_phase_analysis``.

Covers:

* Error envelopes (invalid user UUID, missing / invalid ``phase_id``,
  no plan on file).
* Plan-level metadata passthrough (``plan_id``, ``plan_name``,
  ``race_date``, ``race_distance``).
* ``phase_kpi_priority`` equals the canonical §8 emphasis list for the
  requested phase.
* ``phase_weeks`` accounting (total / completed / in_progress / future
  / completion_pct / phase_temporality) against a fixture plan that
  straddles Base → Build with a pinned "today".
* ``phase_window`` boundaries (first Monday, last Sunday,
  evaluated_through).
* ``by_run_type`` per-run-type aggregation:
    - ``run_count_planned`` spans the full phase (past + current +
      future), ``run_count_matched`` only counts past + current.
    - Planned / actual miles totals.
    - Zone-compliance avg + chronological weekly trend series.
    - ``completion_miles_pct_avg``.
    - ``deviation_direction_distribution``.
    - ``run_score_distribution``.
* §19.5 future-week extension: future phase-weeks with a seeded
  landmine matched activity contribute NO execution data — the
  ``activity_id`` never appears in the payload.
* §X.5 single source of truth: each actual-side field reads off the
  canonical ``build_run_execution_block`` output (verified via the
  rollup maths).
* Phase-empty edge case: requesting a phase that has no weeks in the
  plan returns ``phase_weeks.total == 0`` + empty ``by_run_type`` but
  still attaches the canonical §8 emphasis list.
* Phase-entirely-future edge case: when every phase-week starts after
  today, ``by_run_type`` is empty (no matched activities to fold in).
* Dispatcher wiring via ``execute_tool("get_phase_analysis", ...)``.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from src.db.models.activities import Activity
from src.db.models.plan_workouts import PlanWorkout
from src.db.models.plans import Plan
from src.db.models.user_athletes import UserAthleteLink
from src.smartcoach_mobile_coach import agent_tools

DEFAULT_USER_ID = uuid.UUID("0b5e5a42-0000-4000-8000-000000003b06")
DEFAULT_USER_ID_STR = str(DEFAULT_USER_ID)

# Pin "today" to Wed 2026-04-22. Current week is 2026-04-20..2026-04-26.
FIXED_TODAY = date(2026, 4, 22)


@pytest.fixture(autouse=True)
def _pin_today(monkeypatch):
    """Pin ``get_today_date_in_timezone`` so phase-to-date is deterministic."""
    monkeypatch.setattr(
        "src.services.plan.phase_analysis.get_today_date_in_timezone",
        lambda _tz: FIXED_TODAY,
    )


@pytest.fixture
def seeded_plan(test_db_session):
    """
    Four-week plan that spans Base → Build with two run types per
    week (Easy on Tue, Long on Sat). Past weeks have real matched
    activities; the current week's Tuesday has one in-progress match;
    the future week has a LANDMINE matched activity to prove the
    tool structurally cannot surface it.

    Week 1 (past):     2026-04-06 Mon .. 2026-04-12 Sun   Base
        Tue easy 5 mi (matched, 85% zone, green)
        Sat long 10 mi (matched, 70% zone, yellow, too_hard)
    Week 2 (past):     2026-04-13 Mon .. 2026-04-19 Sun   Base
        Tue easy 5 mi (matched, 90% zone, green)
        Sat long 11 mi (matched, 65% zone, yellow, too_hard)
    Week 3 (current):  2026-04-20 Mon .. 2026-04-26 Sun   Build
        Tue easy 5 mi (matched, 80% zone, green)
        Sat long 13 mi (not yet executed)
    Week 4 (future):   2026-04-27 Mon .. 2026-05-03 Sun   Build
        Tue easy 5 mi (LANDMINE matched activity — must NOT leak)
        Sat long 14 mi (not matched)
    """
    session = test_db_session
    session.add(UserAthleteLink(user_id=DEFAULT_USER_ID_STR, athlete_id=4343))
    plan = Plan(
        user_id=DEFAULT_USER_ID,
        plan_name="Phase Analysis 3B.6 Test",
        race_date=date(2026, 6, 7),
        race_distance="Marathon",
        is_active=True,
        training_days=["Tue", "Sat"],
    )
    session.add(plan)
    session.flush()

    week_specs = [
        (date(2026, 4, 6), "Base", 5.0, 10.0),
        (date(2026, 4, 13), "Base", 5.0, 11.0),
        (date(2026, 4, 20), "Build", 5.0, 13.0),
        (date(2026, 4, 27), "Build", 5.0, 14.0),
    ]

    workouts: dict[date, PlanWorkout] = {}
    for monday, phase, easy_mi, long_mi in week_specs:
        tue = monday + timedelta(days=1)
        sat = monday + timedelta(days=5)
        easy = PlanWorkout(
            plan_id=plan.id,
            date=tue,
            workout_type="Easy Run",
            description="Easy miles",
            miles=easy_mi,
            intensity="E",
            run_type_key="easy",
            phase=phase,
        )
        long_run = PlanWorkout(
            plan_id=plan.id,
            date=sat,
            workout_type="Long Run",
            description="Weekend long",
            miles=long_mi,
            intensity="E",
            run_type_key="long",
            phase=phase,
        )
        session.add_all([easy, long_run])
        session.flush()
        workouts[tue] = easy
        workouts[sat] = long_run

    # Helper to seed a matched activity for a given workout. Mirrors
    # how build_run_execution_block will read the Activity — we set
    # the canonical fields directly.
    def _add_activity(
        *,
        aid: int,
        pw_date: date,
        start_dt: datetime,
        run_score: str,
        zc_pct: float,
        planned_type: str,
        executed_type: str,
        planned_mi: float,
        actual_mi: float,
        completion_pct: float,
    ) -> None:
        session.add(
            Activity(
                activity_id=aid,
                athlete_id=4343,
                user_id=DEFAULT_USER_ID,
                name=f"Activity {aid}",
                type="Run",
                start_date=start_dt,
                matched_plan_workout_id=workouts[pw_date].id,
                planned_type=planned_type,
                executed_type=executed_type,
                run_score=run_score,
                zone_compliance_pct=zc_pct,
                planned_miles=planned_mi,
                actual_miles=actual_mi,
                completion_pct=completion_pct,
                conv_distance=actual_mi,
                moving_time=int(actual_mi * 540),  # ~9:00/mi
            )
        )

    # Week 1 Tue easy: on_target (via deviation producer), 85% zone, green
    _add_activity(
        aid=434301,
        pw_date=date(2026, 4, 7),
        start_dt=datetime(2026, 4, 7, 12, 0, tzinfo=timezone.utc),
        run_score="green",
        zc_pct=85.0,
        planned_type="easy",
        executed_type="easy",
        planned_mi=5.0,
        actual_mi=5.0,
        completion_pct=100.0,
    )
    # Week 1 Sat long: 70% zone, yellow
    _add_activity(
        aid=434302,
        pw_date=date(2026, 4, 11),
        start_dt=datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc),
        run_score="yellow",
        zc_pct=70.0,
        planned_type="long",
        executed_type="long",
        planned_mi=10.0,
        actual_mi=10.0,
        completion_pct=100.0,
    )
    # Week 2 Tue easy: 90% zone, green
    _add_activity(
        aid=434303,
        pw_date=date(2026, 4, 14),
        start_dt=datetime(2026, 4, 14, 12, 0, tzinfo=timezone.utc),
        run_score="green",
        zc_pct=90.0,
        planned_type="easy",
        executed_type="easy",
        planned_mi=5.0,
        actual_mi=5.0,
        completion_pct=100.0,
    )
    # Week 2 Sat long: 65% zone, yellow
    _add_activity(
        aid=434304,
        pw_date=date(2026, 4, 18),
        start_dt=datetime(2026, 4, 18, 12, 0, tzinfo=timezone.utc),
        run_score="yellow",
        zc_pct=65.0,
        planned_type="long",
        executed_type="long",
        planned_mi=11.0,
        actual_mi=11.0,
        completion_pct=100.0,
    )
    # Week 3 Tue easy (current week, already done): 80% zone, green
    _add_activity(
        aid=434305,
        pw_date=date(2026, 4, 21),
        start_dt=datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc),
        run_score="green",
        zc_pct=80.0,
        planned_type="easy",
        executed_type="easy",
        planned_mi=5.0,
        actual_mi=5.0,
        completion_pct=100.0,
    )
    # LANDMINE: future week 4 Tue easy has a matched activity. The
    # phase-analysis payload for Build MUST NOT include this activity
    # because the week's Monday is after today.
    _add_activity(
        aid=434306,
        pw_date=date(2026, 4, 28),
        start_dt=datetime(2026, 4, 28, 12, 0, tzinfo=timezone.utc),
        run_score="green",
        zc_pct=99.0,
        planned_type="easy",
        executed_type="easy",
        planned_mi=5.0,
        actual_mi=5.0,
        completion_pct=100.0,
    )

    session.commit()
    return {"plan": plan, "workouts": workouts}


# ---------------------------------------------------------------------------
# Error envelopes
# ---------------------------------------------------------------------------


def test_tool_rejects_non_uuid_user_id(test_db_session):
    out = agent_tools.tool_get_phase_analysis(
        test_db_session, "not-a-uuid", phase_id="Base"
    )
    assert out["error"] == "invalid_user_id"


def test_tool_rejects_missing_phase_id(test_db_session):
    out = agent_tools.tool_get_phase_analysis(test_db_session, DEFAULT_USER_ID_STR)
    assert out["error"] == "missing_phase_id"


def test_tool_rejects_blank_phase_id(test_db_session):
    out = agent_tools.tool_get_phase_analysis(
        test_db_session, DEFAULT_USER_ID_STR, phase_id="   "
    )
    assert out["error"] == "missing_phase_id"


def test_service_rejects_invalid_phase_name(test_db_session, seeded_plan):
    out = agent_tools.tool_get_phase_analysis(
        test_db_session, DEFAULT_USER_ID_STR, phase_id="Warmup"
    )
    assert out["error"] == "invalid_phase"
    assert set(out["allowed"]) == {"Base", "Build", "Peak", "Taper"}


def test_phase_id_is_case_insensitive(test_db_session, seeded_plan):
    lower = agent_tools.tool_get_phase_analysis(
        test_db_session, DEFAULT_USER_ID_STR, phase_id="base"
    )
    upper = agent_tools.tool_get_phase_analysis(
        test_db_session, DEFAULT_USER_ID_STR, phase_id="BASE"
    )
    mixed = agent_tools.tool_get_phase_analysis(
        test_db_session, DEFAULT_USER_ID_STR, phase_id="Base"
    )
    assert lower["phase"] == upper["phase"] == mixed["phase"] == "Base"


def test_no_plan_returns_error_envelope(test_db_session):
    session = test_db_session
    session.add(UserAthleteLink(user_id=DEFAULT_USER_ID_STR, athlete_id=4343))
    session.commit()
    out = agent_tools.tool_get_phase_analysis(
        session, DEFAULT_USER_ID_STR, phase_id="Base"
    )
    assert out["error"] == "no_plan"


# ---------------------------------------------------------------------------
# Canonical phase_kpi_priority
# ---------------------------------------------------------------------------


def test_phase_kpi_priority_matches_canonical_table_for_base(
    test_db_session, seeded_plan
):
    out = agent_tools.tool_get_phase_analysis(
        test_db_session, DEFAULT_USER_ID_STR, phase_id="Base"
    )
    pkp = out["phase_kpi_priority"]
    assert pkp["phase"] == "Base"
    assert [e["kpi_id"] for e in pkp["priority"]] == [
        "hr_drift",
        "aerobic_efficiency",
        "easy_zone_compliance",
    ]


def test_phase_kpi_priority_matches_canonical_table_for_build(
    test_db_session, seeded_plan
):
    out = agent_tools.tool_get_phase_analysis(
        test_db_session, DEFAULT_USER_ID_STR, phase_id="Build"
    )
    pkp = out["phase_kpi_priority"]
    assert pkp["phase"] == "Build"
    assert [e["kpi_id"] for e in pkp["priority"]] == [
        "pace_consistency_tempo",
        "quality_zone_compliance",
        "hr_drift",
    ]


# ---------------------------------------------------------------------------
# phase_weeks accounting
# ---------------------------------------------------------------------------


def test_phase_weeks_for_base_counts_past_only(test_db_session, seeded_plan):
    out = agent_tools.tool_get_phase_analysis(
        test_db_session, DEFAULT_USER_ID_STR, phase_id="Base"
    )
    pw = out["phase_weeks"]
    # Base = weeks 1-2, both fully past.
    assert pw["total"] == 2
    assert pw["completed"] == 2
    assert pw["in_progress"] == 0
    assert pw["future"] == 0
    assert pw["completion_pct"] == pytest.approx(1.0)
    assert pw["phase_temporality"] == "past"


def test_phase_weeks_for_build_counts_current_and_future(test_db_session, seeded_plan):
    out = agent_tools.tool_get_phase_analysis(
        test_db_session, DEFAULT_USER_ID_STR, phase_id="Build"
    )
    pw = out["phase_weeks"]
    # Build = weeks 3-4: current + future.
    assert pw["total"] == 2
    assert pw["completed"] == 0
    assert pw["in_progress"] == 1
    assert pw["future"] == 1
    assert pw["completion_pct"] == pytest.approx(0.5)
    assert pw["phase_temporality"] == "current"


def test_phase_weeks_for_absent_phase_is_empty(test_db_session, seeded_plan):
    """
    The fixture plan has no Peak or Taper weeks. Requesting them
    should still succeed (error-free) and still emit the canonical
    ``phase_kpi_priority`` — the coach can narrate intent even before
    the phase begins.
    """
    out = agent_tools.tool_get_phase_analysis(
        test_db_session, DEFAULT_USER_ID_STR, phase_id="Peak"
    )
    pw = out["phase_weeks"]
    assert pw["total"] == 0
    assert pw["completed"] == 0
    assert pw["in_progress"] == 0
    assert pw["future"] == 0
    assert pw["phase_temporality"] == "empty"
    assert out["by_run_type"] == {}
    # Canonical emphasis list is still attached.
    assert [e["kpi_id"] for e in out["phase_kpi_priority"]["priority"]] == [
        "execution_zone_compliance",
        "fatigue_consistency",
        "pace_consistency",
    ]


# ---------------------------------------------------------------------------
# phase_window
# ---------------------------------------------------------------------------


def test_phase_window_for_base(test_db_session, seeded_plan):
    out = agent_tools.tool_get_phase_analysis(
        test_db_session, DEFAULT_USER_ID_STR, phase_id="Base"
    )
    pwindow = out["phase_window"]
    assert pwindow["start"] == "2026-04-06"
    assert pwindow["end"] == "2026-04-19"  # Sunday of week 2
    # evaluated_through should be the last week-2 Sunday (not today,
    # since today is AFTER the phase's end).
    assert pwindow["evaluated_through"] == "2026-04-19"


def test_phase_window_for_build_caps_evaluated_through_to_today(
    test_db_session, seeded_plan
):
    out = agent_tools.tool_get_phase_analysis(
        test_db_session, DEFAULT_USER_ID_STR, phase_id="Build"
    )
    pwindow = out["phase_window"]
    assert pwindow["start"] == "2026-04-20"
    assert pwindow["end"] == "2026-05-03"  # Sunday of week 4
    # evaluated_through = min(today, last_evaluable_sunday).
    # Last evaluable week = current (wk3); its Sunday = 2026-04-26.
    # today (2026-04-22) < that Sunday → evaluated_through = today.
    assert pwindow["evaluated_through"] == "2026-04-22"


# ---------------------------------------------------------------------------
# by_run_type — Base (past-only phase)
# ---------------------------------------------------------------------------


def test_by_run_type_base_planned_counts(test_db_session, seeded_plan):
    out = agent_tools.tool_get_phase_analysis(
        test_db_session, DEFAULT_USER_ID_STR, phase_id="Base"
    )
    base = out["by_run_type"]
    assert set(base.keys()) == {"easy", "long"}
    # 2 weeks in Base, 1 easy + 1 long per week.
    assert base["easy"]["run_count_planned"] == 2
    assert base["long"]["run_count_planned"] == 2
    assert base["easy"]["run_count_matched"] == 2
    assert base["long"]["run_count_matched"] == 2


def test_by_run_type_base_mileage_totals(test_db_session, seeded_plan):
    out = agent_tools.tool_get_phase_analysis(
        test_db_session, DEFAULT_USER_ID_STR, phase_id="Base"
    )
    base = out["by_run_type"]
    # Easy: 5 + 5 planned = 10; matched 5 + 5 = 10.
    assert base["easy"]["miles_planned_total"] == pytest.approx(10.0)
    assert base["easy"]["miles_actual_total"] == pytest.approx(10.0)
    # Long: 10 + 11 planned = 21; matched 10 + 11 = 21.
    assert base["long"]["miles_planned_total"] == pytest.approx(21.0)
    assert base["long"]["miles_actual_total"] == pytest.approx(21.0)


def test_by_run_type_base_zone_compliance_avg_and_trend(test_db_session, seeded_plan):
    out = agent_tools.tool_get_phase_analysis(
        test_db_session, DEFAULT_USER_ID_STR, phase_id="Base"
    )
    easy = out["by_run_type"]["easy"]
    long_bucket = out["by_run_type"]["long"]

    # Easy zone compliance: [85, 90] → avg 87.5.
    assert easy["zone_compliance_pct"]["avg"] == pytest.approx(87.5)
    easy_trend = easy["zone_compliance_pct"]["trend"]
    assert [t["week_start"] for t in easy_trend] == [
        "2026-04-06",
        "2026-04-13",
    ]
    assert [t["avg_zone_compliance_pct"] for t in easy_trend] == pytest.approx(
        [85.0, 90.0]
    )
    assert [t["n"] for t in easy_trend] == [1, 1]

    # Long zone compliance: [70, 65] → avg 67.5.
    assert long_bucket["zone_compliance_pct"]["avg"] == pytest.approx(67.5)


def test_by_run_type_base_run_score_distribution(test_db_session, seeded_plan):
    out = agent_tools.tool_get_phase_analysis(
        test_db_session, DEFAULT_USER_ID_STR, phase_id="Base"
    )
    # "green" is a string label stored on activities.run_score. The
    # service's _classify_run_score treats non-integer strings as
    # "null" — V1.6 canonical scoring uses an integer band. Verify
    # that behavior so callers can rely on the distribution shape.
    easy = out["by_run_type"]["easy"]
    total_easy = sum(easy["run_score_distribution"].values())
    assert total_easy == easy["run_count_matched"] == 2


def test_by_run_type_base_completion_miles_pct_avg(test_db_session, seeded_plan):
    out = agent_tools.tool_get_phase_analysis(
        test_db_session, DEFAULT_USER_ID_STR, phase_id="Base"
    )
    easy = out["by_run_type"]["easy"]
    long_bucket = out["by_run_type"]["long"]
    # All Base runs completed at 100%.
    assert easy["completion_miles_pct_avg"] == pytest.approx(100.0)
    assert long_bucket["completion_miles_pct_avg"] == pytest.approx(100.0)


def test_by_run_type_base_attaches_canonical_run_type_metadata(
    test_db_session, seeded_plan
):
    out = agent_tools.tool_get_phase_analysis(
        test_db_session, DEFAULT_USER_ID_STR, phase_id="Base"
    )
    easy = out["by_run_type"]["easy"]
    assert easy["run_type"]["key"] == "easy"
    assert isinstance(easy["run_type"]["display_name"], str)
    assert isinstance(easy["run_type"]["target_zone_ids"], list)


# ---------------------------------------------------------------------------
# by_run_type — Build (current-only execution, future is a landmine)
# ---------------------------------------------------------------------------


def test_by_run_type_build_counts_current_only(test_db_session, seeded_plan):
    out = agent_tools.tool_get_phase_analysis(
        test_db_session, DEFAULT_USER_ID_STR, phase_id="Build"
    )
    build = out["by_run_type"]
    # Planned denominator spans entire phase (wk3 + wk4).
    assert build["easy"]["run_count_planned"] == 2
    assert build["long"]["run_count_planned"] == 2
    # Matched numerator only from current week's Tuesday easy.
    assert build["easy"]["run_count_matched"] == 1
    # The current-week Sat long hasn't been executed; wk4 is future
    # so its LANDMINE activity must NOT count.
    assert build["long"]["run_count_matched"] == 0


def test_by_run_type_build_zone_compliance_only_from_current_week(
    test_db_session, seeded_plan
):
    out = agent_tools.tool_get_phase_analysis(
        test_db_session, DEFAULT_USER_ID_STR, phase_id="Build"
    )
    easy = out["by_run_type"]["easy"]
    # Only the current-week Tue easy contributed: 80%.
    assert easy["zone_compliance_pct"]["avg"] == pytest.approx(80.0)
    trend = easy["zone_compliance_pct"]["trend"]
    assert len(trend) == 1
    assert trend[0]["week_start"] == "2026-04-20"
    assert trend[0]["avg_zone_compliance_pct"] == pytest.approx(80.0)


def test_build_phase_does_not_surface_landmine_future_activity(
    test_db_session, seeded_plan
):
    """
    §19.5 extension — the future-week matched activity was seeded
    with activity_id=434306 and zone_compliance_pct=99.0. Neither
    value can appear anywhere in the serialized Build payload.
    """
    out = agent_tools.tool_get_phase_analysis(
        test_db_session, DEFAULT_USER_ID_STR, phase_id="Build"
    )
    serialized = json.dumps(out)
    assert "434306" not in serialized
    assert "99.0" not in serialized
    # Long-run actual miles totals must not include future week's 5mi
    # (it's easy anyway) or 14mi (long, not matched).
    long_bucket = out["by_run_type"]["long"]
    assert long_bucket["miles_actual_total"] == 0.0


# ---------------------------------------------------------------------------
# Deviation direction distribution shape
# ---------------------------------------------------------------------------


def test_deviation_distribution_has_four_buckets(test_db_session, seeded_plan):
    out = agent_tools.tool_get_phase_analysis(
        test_db_session, DEFAULT_USER_ID_STR, phase_id="Base"
    )
    easy = out["by_run_type"]["easy"]
    dist = easy["deviation_direction_distribution"]
    assert set(dist.keys()) == {"too_hard", "too_easy", "on_target", "null"}
    # Counts sum to number of matched runs.
    assert sum(dist.values()) == easy["run_count_matched"]


# ---------------------------------------------------------------------------
# Dispatcher wiring
# ---------------------------------------------------------------------------


def test_execute_tool_dispatches_get_phase_analysis(test_db_session, seeded_plan):
    out = agent_tools.execute_tool(
        test_db_session,
        DEFAULT_USER_ID_STR,
        "get_phase_analysis",
        json.dumps({"phase_id": "Base"}),
    )
    assert out["phase"] == "Base"
    assert "by_run_type" in out


def test_execute_tool_surfaces_missing_phase_id_envelope(test_db_session, seeded_plan):
    out = agent_tools.execute_tool(
        test_db_session,
        DEFAULT_USER_ID_STR,
        "get_phase_analysis",
        "{}",
    )
    assert out["error"] == "missing_phase_id"


def test_execute_tool_surfaces_invalid_phase_envelope(test_db_session, seeded_plan):
    out = agent_tools.execute_tool(
        test_db_session,
        DEFAULT_USER_ID_STR,
        "get_phase_analysis",
        json.dumps({"phase_id": "Warmup"}),
    )
    assert out["error"] == "invalid_phase"


def test_execute_tool_accepts_tz_argument(test_db_session, seeded_plan):
    out = agent_tools.execute_tool(
        test_db_session,
        DEFAULT_USER_ID_STR,
        "get_phase_analysis",
        json.dumps({"phase_id": "Base", "tz": "America/Denver"}),
    )
    assert out["timezone"] == "America/Denver"


def test_execute_tool_rejects_malformed_json(test_db_session, seeded_plan):
    out = agent_tools.execute_tool(
        test_db_session,
        DEFAULT_USER_ID_STR,
        "get_phase_analysis",
        "not-json",
    )
    assert out["error"] == "invalid_arguments"
