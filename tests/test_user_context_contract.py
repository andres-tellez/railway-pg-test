"""
V1.6 Phase B 3B.11 — ``get_user_context`` payload contract tests.

This file complements ``tests/test_get_user_context_tool.py`` with the
**stable-key** + **size budget** contract for the ``user_context``
payload. The per-field semantic tests live in the tool test file; this
file locks the **shape** so downstream consumers (coach prompt,
validator, any future mobile surface) can rely on a fixed set of keys
and a predictable byte budget.

Spec references
---------------
* 3B.11 "light payload (≤ 2 KB); structured JSON with stable keys; no
  PII beyond what is already in ``user_profile``".
* §X.5 single-source-of-truth — this file asserts the shape produced
  by :func:`src.services.user.user_context.build_user_context_payload`
  (the canonical producer); ``tool_get_user_context`` must mirror it
  byte-for-byte.
* §19 PII posture — adversarial string checks keep ``email`` /
  ``picture`` / auth metadata out of the payload blob even when the
  seed data contains them.

Budget rationale
----------------
The 2 KB budget comes from AGENTIC_COACH.md Topic 4 (system prompt +
per-turn context tokens are scarce; ``user_context`` is read on every
opening turn). Current fully-populated shape lands at ~900 bytes;
we assert < 2048 with headroom so future additive fields (e.g. 3F.3
session-summary excerpt) can land without bust.
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
from src.services.user.user_context import (
    USER_CONTEXT_SCHEMA_VERSION,
    build_user_context_payload,
)

DEFAULT_USER_ID = uuid.UUID("0b5e5a42-0000-4000-8000-00000000b011")
DEFAULT_USER_ID_STR = str(DEFAULT_USER_ID)

# Wednesday of the plan's third week (Build phase).
FIXED_TODAY = date(2026, 4, 22)

# ---------------------------------------------------------------------------
# Canonical stable-key contract (locked by 3B.11).
# ---------------------------------------------------------------------------

EXPECTED_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    {
        "schema_version",
        "user_id",
        "display_name",
        "baseline_status",
        "race_goal",
        "plan",
        "coaching",
        "preferences",
        "plan_memories",
        "session_summary",
        "generated_at",
        "today",
    }
)

EXPECTED_RACE_GOAL_KEYS: frozenset[str] = frozenset(
    {
        "race_name",
        "race_distance",
        "race_date",
        "goal_time",
        "primary_goal",
        "weeks_until_race",
    }
)

EXPECTED_PLAN_KEYS: frozenset[str] = frozenset(
    {
        "plan_id",
        "plan_name",
        "plan_start",
        "plan_end",
        "total_weeks",
        "current_week_number",
        "is_active",
        "current_phase",
        "phase_kpi_priority",
    }
)

EXPECTED_COACHING_KEYS: frozenset[str] = frozenset(
    {
        "coaching_level",
        "verbosity",
        "run_summary_priority",
        "training_summary_priority",
        "has_saved_preferences",
    }
)

EXPECTED_PREFERENCES_KEYS: frozenset[str] = frozenset(
    {
        "training_days",
        "long_run_day",
        "unit_system",
        "timezone",
    }
)


@pytest.fixture(autouse=True)
def _pin_today(monkeypatch):
    monkeypatch.setattr(
        "src.services.user.user_context.get_today_date_in_timezone",
        lambda _tz: FIXED_TODAY,
    )


def _seed_identity(session, *, name: str = "Jane Runner") -> UserIdentity:
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
    """Seed a fully-populated user + plan — mirrors the 3B.10 fixture."""
    session = test_db_session
    _seed_identity(session, name="Jane Runner")
    _seed_profile(session, unit_system="imperial")
    session.add(UserAthleteLink(user_id=DEFAULT_USER_ID_STR, athlete_id=4411))
    session.add(
        UserCoachPreferences(
            user_id=DEFAULT_USER_ID,
            coaching_level="intermediate",
            verbosity="detailed",
            run_summary_priority=["hr_drift_pct", "aerobic_efficiency"],
            training_summary_priority=["zone_compliance", "completion_miles_pct"],
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
                    intensity="z2",
                    run_type_key="easy",
                    phase=phase,
                ),
                PlanWorkout(
                    plan_id=plan.id,
                    date=sat,
                    workout_type="Long Run",
                    description="Weekend long",
                    miles=10.0,
                    intensity="z2",
                    run_type_key="long",
                    phase=phase,
                ),
            ]
        )

    # 3 activities spread across 3 distinct 7-day buckets → "thin".
    for offset_days, aid in ((1, 911001), (8, 911002), (15, 911003)):
        session.add(
            Activity(
                activity_id=aid,
                athlete_id=4411,
                user_id=DEFAULT_USER_ID,
                name=f"Run {aid}",
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
# Stable-key contract — top level
# ---------------------------------------------------------------------------


def test_top_level_keys_exactly_match_contract(test_db_session, seeded_full_user):
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    assert set(out.keys()) == EXPECTED_TOP_LEVEL_KEYS, (
        "Top-level key set drift detected. "
        f"Expected={sorted(EXPECTED_TOP_LEVEL_KEYS)} "
        f"Actual={sorted(out.keys())}"
    )


def test_top_level_keys_match_even_when_plan_absent(test_db_session):
    """Null branches must keep the contract — just null values, not missing keys."""
    _seed_identity(test_db_session)
    test_db_session.commit()
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    assert set(out.keys()) == EXPECTED_TOP_LEVEL_KEYS


def test_schema_version_is_an_integer_and_matches_constant(
    test_db_session, seeded_full_user
):
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    assert isinstance(out["schema_version"], int)
    assert out["schema_version"] == USER_CONTEXT_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Stable-key contract — nested blocks
# ---------------------------------------------------------------------------


def test_race_goal_block_key_set_is_stable(test_db_session, seeded_full_user):
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    assert out["race_goal"] is not None
    assert set(out["race_goal"].keys()) == EXPECTED_RACE_GOAL_KEYS


def test_plan_block_key_set_is_stable(test_db_session, seeded_full_user):
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    assert out["plan"] is not None
    assert set(out["plan"].keys()) == EXPECTED_PLAN_KEYS


def test_coaching_block_key_set_is_stable(test_db_session, seeded_full_user):
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    assert set(out["coaching"].keys()) == EXPECTED_COACHING_KEYS


def test_coaching_block_key_set_matches_on_default_path(test_db_session):
    """Defaults path (no ``user_coach_preferences`` row) must keep the same keys."""
    _seed_identity(test_db_session)
    test_db_session.commit()
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    assert set(out["coaching"].keys()) == EXPECTED_COACHING_KEYS


def test_preferences_block_key_set_is_stable(test_db_session, seeded_full_user):
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    assert set(out["preferences"].keys()) == EXPECTED_PREFERENCES_KEYS


def test_preferences_block_key_set_matches_without_plan(test_db_session):
    """Preferences must still ship its full key set even with no plan row."""
    _seed_identity(test_db_session)
    _seed_profile(test_db_session, unit_system="metric")
    test_db_session.commit()
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    assert set(out["preferences"].keys()) == EXPECTED_PREFERENCES_KEYS


# ---------------------------------------------------------------------------
# Payload size budget (3B.11 contract: < 2 KB)
# ---------------------------------------------------------------------------

PAYLOAD_SIZE_BUDGET_BYTES = 2048


def _payload_bytes(payload: dict) -> int:
    return len(json.dumps(payload).encode("utf-8"))


def test_payload_size_under_2kb_for_fully_populated_user(
    test_db_session, seeded_full_user
):
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    size = _payload_bytes(out)
    assert size < PAYLOAD_SIZE_BUDGET_BYTES, (
        f"user_context payload is {size} bytes; 3B.11 budget is "
        f"<{PAYLOAD_SIZE_BUDGET_BYTES}."
    )


def test_payload_size_under_2kb_for_minimal_user(test_db_session):
    """Empty-state payload (identity only, no plan) must also fit the budget."""
    _seed_identity(test_db_session)
    test_db_session.commit()
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    assert _payload_bytes(out) < PAYLOAD_SIZE_BUDGET_BYTES


def test_payload_size_under_2kb_through_service_builder(
    test_db_session, seeded_full_user
):
    """Service builder output and tool wrapper must agree on size budget."""
    out = build_user_context_payload(
        test_db_session, DEFAULT_USER_ID, tz="UTC", today=FIXED_TODAY
    )
    assert _payload_bytes(out) < PAYLOAD_SIZE_BUDGET_BYTES


# ---------------------------------------------------------------------------
# PII posture (3B.11 — "no PII beyond what is already in user_profile")
# ---------------------------------------------------------------------------


def test_payload_blob_does_not_leak_email_or_auth_metadata(
    test_db_session, seeded_full_user
):
    out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    blob = json.dumps(out)
    # Adversarial — even if a future refactor accidentally widens the
    # read, these must stay out of the payload.
    assert "jane@example.com" not in blob
    assert "@" not in blob  # no embedded email of any kind
    assert "picture" not in out
    assert "email" not in out


def test_display_name_is_only_first_whitespace_token(test_db_session):
    session = test_db_session
    _seed_identity(session, name="Jane Middle Runner")
    session.commit()
    out = agent_tools.tool_get_user_context(session, DEFAULT_USER_ID_STR)
    assert out["display_name"] == "Jane"
    blob = json.dumps(out)
    assert "Middle" not in blob
    assert "Runner" not in blob


# ---------------------------------------------------------------------------
# Tool / service shape parity
# ---------------------------------------------------------------------------


def test_tool_wrapper_and_service_produce_the_same_shape(
    test_db_session, seeded_full_user
):
    """
    ``tool_get_user_context`` is a thin wrapper over
    ``build_user_context_payload``. Their **key sets** must match so
    dispatcher-side consumers see the same contract.
    """
    tool_out = agent_tools.tool_get_user_context(test_db_session, DEFAULT_USER_ID_STR)
    svc_out = build_user_context_payload(
        test_db_session, DEFAULT_USER_ID, tz="UTC", today=FIXED_TODAY
    )
    assert set(tool_out.keys()) == set(svc_out.keys())
    for key in ("race_goal", "plan", "coaching", "preferences"):
        tv = tool_out.get(key)
        sv = svc_out.get(key)
        if isinstance(tv, dict) and isinstance(sv, dict):
            assert set(tv.keys()) == set(sv.keys())
