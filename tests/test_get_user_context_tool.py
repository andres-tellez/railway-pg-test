"""
Tests for V1.6 Phase B 3B.10 — ``tool_get_user_context``.

Covers:

* Error envelopes (invalid user UUID, missing user identity row).
* Plan-level metadata passthrough (plan_id / plan_name / plan_start /
  plan_end / total_weeks / current_week_number / is_active).
* Current phase + canonical §8 ``phase_kpi_priority`` emphasis list
  for the week containing "today".
* ``baseline_status`` wired to
  :func:`src.services.baseline.baseline_status.compute_baseline_status_for_athlete`.
* Race-goal block (race_name / race_distance / race_date / goal_time /
  primary_goal / weeks_until_race).
* Coaching block — both the "no row saved yet" default path and the
  "user has saved preferences" path.
* Preferences block — training_days, derived long_run_day, unit_system,
  timezone.
* PII posture — only the first name of ``user_identity.name`` is
  emitted.
* Payload size budget — ``< 2 KB`` for a fully populated user (3B.11
  pre-check; the contract test lands in 3B.11 but we smoke-check here).
* Session summary placeholder is explicit ``None``.
* Dispatcher wiring via ``execute_tool("get_user_context", ...)``.
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
from src.db.models.user_coach_preferences import UserCoachPreferences
from src.db.models.user_identity import UserIdentity
from src.db.models.user_profile import UserProfile
from src.smartcoach_mobile_coach import agent_tools

DEFAULT_USER_ID = uuid.UUID("0b5e5a42-0000-4000-8000-000000003b10")
DEFAULT_USER_ID_STR = str(DEFAULT_USER_ID)

# Pin "today" to Wed 2026-04-22 so the current week is
# 2026-04-20 .. 2026-04-26 (Build phase in the seeded plan).
FIXED_TODAY = date(2026, 4, 22)


@pytest.fixture(autouse=True)
def _pin_today(monkeypatch):
    """Pin the timezone "today" helper so per-test assertions are deterministic."""
    monkeypatch.setattr(
        "src.services.user.user_context.get_today_date_in_timezone",
        lambda _tz: FIXED_TODAY,
    )


def _seed_identity(session, *, name: str = "Jane Doe") -> UserIdentity:
    ident = UserIdentity(user_id=DEFAULT_USER_ID, name=name, email="jane@example.com")
    session.add(ident)
    session.flush()
    return ident


def _seed_profile(session, *, unit_system: str = "imperial") -> UserProfile:
    prof = UserProfile(
        user_id=DEFAULT_USER_ID_STR,
        age_group="30-39",
        height_feet=5,
        height_inches=8,
        unit_system=unit_system,
    )
    session.add(prof)
    session.flush()
    return prof


@pytest.fixture
def seeded_full_user(test_db_session):
    """
    Seed a user with:

    * ``user_identity`` row (name "Jane Doe" → display_name "Jane").
    * ``user_profile`` row (unit_system "imperial").
    * ``user_athletes`` link (athlete_id 4343).
    * ``user_coach_preferences`` row (coaching_level "intermediate",
      verbosity "detailed").
    * Active plan with race Chicago Marathon on 2026-10-11,
      target_time "3:45:00", primary_goal "finish_strong",
      training_days ["Mon", "Wed", "Fri", "Sat"].
    * 4-week plan Base (w1-w2) → Build (w3-w4) with Tue easy + Sat long
      each week.
    * 3 historical matched activities in the last 28 days so
      ``compute_baseline_status_for_athlete`` returns ``thin`` (3 runs
      spread across 3 distinct 7-day buckets — not enough to hit
      ``strong`` which needs >=4 weeks + >=6 runs, but above the
      ``insufficient`` floor of <2 weeks or <3 runs).
    """
    session = test_db_session
    _seed_identity(session, name="Jane Doe")
    _seed_profile(session, unit_system="imperial")
    session.add(UserAthleteLink(user_id=DEFAULT_USER_ID_STR, athlete_id=4343))
    session.add(
        UserCoachPreferences(
            user_id=DEFAULT_USER_ID,
            coaching_level="intermediate",
            verbosity="detailed",
        )
    )

    plan = Plan(
        user_id=DEFAULT_USER_ID,
        plan_name="Chicago Marathon Plan",
        race_name="Chicago Marathon",
        race_date=date(2026, 10, 11),
        race_distance="Marathon",
        target_time="3:45:00",
        primary_goal="finish_strong",
        training_days=["Mon", "Wed", "Fri", "Sat"],
        is_active=True,
    )
    session.add(plan)
    session.flush()

    # 4-week plan: Base (w1-w2) → Build (w3-w4), 2 workouts/week.
    week_specs = [
        (date(2026, 4, 6), "Base"),
        (date(2026, 4, 13), "Base"),
        (date(2026, 4, 20), "Build"),
        (date(2026, 4, 27), "Build"),
    ]
    for monday, phase in week_specs:
        tue = monday + timedelta(days=1)
        sat = monday + timedelta(days=5)
        session.add_all(
            [
                PlanWorkout(
                    plan_id=plan.id,
                    date=tue,
                    workout_type="Easy Run",
                    description="Easy miles",
                    miles=5.0,
                    intensity="E",
                    run_type_key="easy",
                    phase=phase,
                ),
                PlanWorkout(
                    plan_id=plan.id,
                    date=sat,
                    workout_type="Long Run",
                    description="Weekend long",
                    miles=10.0,
                    intensity="E",
                    run_type_key="long",
                    phase=phase,
                ),
            ]
        )

    # Seed 3 historical activities for baseline_status: one today, one 8
    # days ago, one 15 days ago. Three distinct 7-day buckets but only
    # 3 runs total → classifies as ``thin`` (needs >=6 runs for strong,
    # >=3 runs for above insufficient).
    for offset_days, aid in ((1, 900001), (8, 900002), (15, 900003)):
        session.add(
            Activity(
                activity_id=aid,
                athlete_id=4343,
                user_id=DEFAULT_USER_ID,
                name=f"Baseline run {aid}",
                type="Run",
                start_date=datetime.combine(
                    FIXED_TODAY - timedelta(days=offset_days),
                    datetime.min.time(),
                    tzinfo=timezone.utc,
                ),
                conv_distance=5.0,
                moving_time=2700,
            )
        )

    session.commit()
    return {"plan": plan}


# ---------------------------------------------------------------------------
# Error envelopes
# ---------------------------------------------------------------------------


def test_tool_rejects_non_uuid_user_id(test_db_session):
    out = agent_tools.tool_get_user_context(test_db_session, "not-a-uuid")
    assert out["error"] == "invalid_user_id"


def test_tool_returns_no_user_when_identity_missing(test_db_session):
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    assert out["error"] == "no_user"


# ---------------------------------------------------------------------------
# Identity + display name (PII posture)
# ---------------------------------------------------------------------------


def test_display_name_is_first_name_only(test_db_session):
    session = test_db_session
    _seed_identity(session, name="Jane Middle Doe")
    session.commit()
    out = agent_tools.tool_get_user_context(session, DEFAULT_USER_ID_STR)
    assert out["display_name"] == "Jane"


def test_display_name_is_none_when_name_empty(test_db_session):
    session = test_db_session
    _seed_identity(session, name="   ")
    session.commit()
    out = agent_tools.tool_get_user_context(session, DEFAULT_USER_ID_STR)
    assert out["display_name"] is None


def test_payload_carries_no_email_or_picture(test_db_session):
    session = test_db_session
    _seed_identity(session, name="Jane Doe")
    session.commit()
    out = agent_tools.tool_get_user_context(session, DEFAULT_USER_ID_STR)
    blob = json.dumps(out)
    assert "jane@example.com" not in blob
    assert "email" not in out
    assert "picture" not in out


# ---------------------------------------------------------------------------
# Race goal
# ---------------------------------------------------------------------------


def test_race_goal_is_populated_when_plan_has_race(test_db_session, seeded_full_user):
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    rg = out["race_goal"]
    assert rg["race_name"] == "Chicago Marathon"
    assert rg["race_distance"] == "Marathon"
    assert rg["race_date"] == "2026-10-11"
    assert rg["goal_time"] == "3:45:00"
    assert rg["primary_goal"] == "finish_strong"
    expected_weeks = (date(2026, 10, 11) - FIXED_TODAY).days // 7
    assert rg["weeks_until_race"] == expected_weeks


def test_weeks_until_race_is_zero_on_race_day(test_db_session):
    session = test_db_session
    _seed_identity(session)
    plan = Plan(
        user_id=DEFAULT_USER_ID,
        plan_name="Race Day Plan",
        race_date=FIXED_TODAY,
        race_distance="Marathon",
        is_active=True,
    )
    session.add(plan)
    session.commit()

    out = agent_tools.tool_get_user_context(session, DEFAULT_USER_ID_STR)
    assert out["race_goal"]["weeks_until_race"] == 0


def test_weeks_until_race_is_none_for_past_race(test_db_session):
    session = test_db_session
    _seed_identity(session)
    plan = Plan(
        user_id=DEFAULT_USER_ID,
        plan_name="Past Plan",
        race_date=FIXED_TODAY - timedelta(days=14),
        race_distance="Marathon",
        is_active=True,
    )
    session.add(plan)
    session.commit()

    out = agent_tools.tool_get_user_context(session, DEFAULT_USER_ID_STR)
    assert out["race_goal"]["weeks_until_race"] is None


def test_race_goal_is_none_when_no_plan(test_db_session):
    session = test_db_session
    _seed_identity(session)
    session.commit()
    out = agent_tools.tool_get_user_context(session, DEFAULT_USER_ID_STR)
    assert out["race_goal"] is None
    assert out["plan"] is None


# ---------------------------------------------------------------------------
# Plan block
# ---------------------------------------------------------------------------


def test_plan_block_surfaces_core_metadata(test_db_session, seeded_full_user):
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    plan_block = out["plan"]
    assert plan_block["plan_name"] == "Chicago Marathon Plan"
    assert plan_block["is_active"] is True
    assert plan_block["plan_start"] == "2026-04-07"  # first workout date (Tue)
    assert plan_block["plan_end"] == "2026-05-02"  # last workout date (Sat W4)
    assert plan_block["total_weeks"] == 4


def test_plan_block_current_week_number_is_three_for_week3(
    test_db_session, seeded_full_user
):
    """``FIXED_TODAY`` (2026-04-22) is in the plan's third week."""
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    assert out["plan"]["current_week_number"] == 3


def test_plan_block_current_phase_is_build(test_db_session, seeded_full_user):
    """Week 3 (2026-04-20..26) is seeded as Build."""
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    assert out["plan"]["current_phase"] == "Build"


def test_phase_kpi_priority_matches_canonical_table_for_build(
    test_db_session, seeded_full_user
):
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    pkp = out["plan"]["phase_kpi_priority"]
    assert pkp == [
        {"kpi_id": "pace_consistency_tempo", "label": "Pace Consistency (Tempo)"},
        {"kpi_id": "quality_zone_compliance", "label": "Quality zone compliance"},
        {"kpi_id": "hr_drift", "label": "HR Drift"},
    ]


def test_plan_block_current_week_number_none_before_plan_start(test_db_session):
    """Before a plan starts, current_week_number is None."""
    session = test_db_session
    _seed_identity(session)
    plan = Plan(
        user_id=DEFAULT_USER_ID,
        plan_name="Future Plan",
        race_date=date(2026, 12, 31),
        is_active=True,
    )
    session.add(plan)
    session.flush()
    session.add(
        PlanWorkout(
            plan_id=plan.id,
            date=FIXED_TODAY + timedelta(days=30),
            workout_type="Easy Run",
            description="Easy",
            miles=5.0,
            intensity="E",
            run_type_key="easy",
            phase="Base",
        )
    )
    session.commit()

    out = agent_tools.tool_get_user_context(session, DEFAULT_USER_ID_STR)
    assert out["plan"]["current_week_number"] is None
    assert out["plan"]["current_phase"] is None
    assert out["plan"]["phase_kpi_priority"] is None


# ---------------------------------------------------------------------------
# Baseline status
# ---------------------------------------------------------------------------


def test_baseline_status_is_wired_to_canonical_producer(
    test_db_session, seeded_full_user
):
    """Seeded: 3 runs across 3 buckets in last 28 days → ``thin``."""
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    assert out["baseline_status"] == "thin"


def test_baseline_status_null_when_no_athlete_link(test_db_session):
    """User has identity but no ``user_athletes`` row → ``None``."""
    session = test_db_session
    _seed_identity(session)
    session.commit()
    out = agent_tools.tool_get_user_context(session, DEFAULT_USER_ID_STR)
    assert out["baseline_status"] is None


# ---------------------------------------------------------------------------
# Coaching block
# ---------------------------------------------------------------------------


def test_coaching_block_uses_beginner_defaults_when_no_preferences(test_db_session):
    session = test_db_session
    _seed_identity(session)
    session.commit()
    out = agent_tools.tool_get_user_context(session, DEFAULT_USER_ID_STR)
    coaching = out["coaching"]
    assert coaching["coaching_level"] == "beginner"
    assert coaching["verbosity"] == "normal"
    assert coaching["run_summary_priority"] is None
    assert coaching["training_summary_priority"] is None
    assert coaching["has_saved_preferences"] is False


def test_coaching_block_reflects_saved_preferences(test_db_session, seeded_full_user):
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    coaching = out["coaching"]
    assert coaching["coaching_level"] == "intermediate"
    assert coaching["verbosity"] == "detailed"
    assert coaching["has_saved_preferences"] is True


# ---------------------------------------------------------------------------
# Preferences block
# ---------------------------------------------------------------------------


def test_preferences_block_carries_plan_training_days(
    test_db_session, seeded_full_user
):
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    prefs = out["preferences"]
    assert prefs["training_days"] == ["Mon", "Wed", "Fri", "Sat"]


def test_preferences_long_run_day_derived_from_plan_workouts(
    test_db_session, seeded_full_user
):
    """All long runs in the seeded plan are on Saturdays."""
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    assert out["preferences"]["long_run_day"] == "Sat"


def test_preferences_unit_system_comes_from_user_profile(
    test_db_session, seeded_full_user
):
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    assert out["preferences"]["unit_system"] == "imperial"


def test_preferences_timezone_defaults_to_utc(test_db_session, seeded_full_user):
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    assert out["preferences"]["timezone"] == "UTC"


def test_preferences_timezone_emitted_when_provided(test_db_session, seeded_full_user):
    out = agent_tools.tool_get_user_context(
        test_db_session, DEFAULT_USER_ID_STR, tz="America/New_York"
    )
    assert out["preferences"]["timezone"] == "America/New_York"


# ---------------------------------------------------------------------------
# Session summary + plan memories (Phase F) + top-level shape invariants
# ---------------------------------------------------------------------------


def test_session_summary_is_null_when_no_layer_b_row(test_db_session, seeded_full_user):
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    assert "session_summary" in out
    assert out["session_summary"] is None


def test_plan_memories_defaults_to_empty_list(test_db_session, seeded_full_user):
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    assert out["plan_memories"] == []


def test_schema_version_is_emitted(test_db_session, seeded_full_user):
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    assert out["schema_version"] == 2


def test_today_and_generated_at_are_present(test_db_session, seeded_full_user):
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    assert out["today"] == FIXED_TODAY.isoformat()
    # ``generated_at`` is an ISO-8601 datetime; just verify it round-trips.
    assert "T" in out["generated_at"]
    datetime.fromisoformat(out["generated_at"].rstrip("Z"))


# ---------------------------------------------------------------------------
# Payload size budget (3B.11 pre-check)
# ---------------------------------------------------------------------------


def test_payload_size_is_under_2kb_when_fully_populated(
    test_db_session, seeded_full_user
):
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    blob = json.dumps(out)
    # 2 KB = 2048 bytes. Give headroom for future additive fields.
    assert (
        len(blob.encode("utf-8")) < 2048
    ), f"Payload is {len(blob.encode('utf-8'))} bytes; budget is <2048."


# ---------------------------------------------------------------------------
# Dispatcher wiring
# ---------------------------------------------------------------------------


def test_execute_tool_routes_get_user_context(test_db_session, seeded_full_user):
    out = agent_tools.execute_tool(
        test_db_session,
        DEFAULT_USER_ID_STR,
        "get_user_context",
        json.dumps({}),
    )
    assert "error" not in out
    assert out["schema_version"] == 2
    assert out["plan"]["plan_name"] == "Chicago Marathon Plan"


def test_execute_tool_accepts_tz_argument(test_db_session, seeded_full_user):
    out = agent_tools.execute_tool(
        test_db_session,
        DEFAULT_USER_ID_STR,
        "get_user_context",
        json.dumps({"tz": "America/Los_Angeles"}),
    )
    assert out["preferences"]["timezone"] == "America/Los_Angeles"


def test_execute_tool_handles_malformed_json(test_db_session, seeded_full_user):
    out = agent_tools.execute_tool(
        test_db_session,
        DEFAULT_USER_ID_STR,
        "get_user_context",
        "{not valid json",
    )
    assert out["error"] == "invalid_arguments"
