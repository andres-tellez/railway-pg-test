"""
Tests for V1.6 Phase D 3D.2 — ``src.services.plan.phase_goal``.

Covers the canonical writer + reader contract:

* Validation envelopes for ``phase`` / ``goal_text`` / ``source``.
* ``no_active_plan`` error when the user has no ``is_active`` plan row.
* Happy-path insert (confirmed and unconfirmed).
* Supersede-then-insert pattern: prior active goal is flipped to
  ``superseded`` and the new ``active`` row wins
  :func:`get_active_phase_goal`.
* Per-phase isolation: saving a Build goal does NOT touch the Base
  active goal.
* ``get_all_goals_for_plan`` returns newest-first.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from src.db.models.plans import Plan
from src.db.models.user_athletes import UserAthleteLink
from src.db.models.user_phase_goals import (
    GOAL_SOURCE_AUTO_PROPOSED,
    GOAL_SOURCE_USER_STATED,
    GOAL_STATUS_ACTIVE,
    GOAL_STATUS_SUPERSEDED,
)
from src.services.phase.phase_priority import Phase
from src.services.plan.phase_goal import (
    MAX_GOAL_TEXT_LENGTH,
    get_active_phase_goal,
    get_all_goals_for_plan,
    save_phase_goal,
)


DEFAULT_USER_ID = uuid.UUID("0b5e5a42-0000-4000-8000-0000003d0002")


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def seeded_plan(test_db_session):
    """One user + one active plan — satisfies FK chain for goal inserts."""
    session = test_db_session
    session.add(UserAthleteLink(user_id=str(DEFAULT_USER_ID), athlete_id=4302))
    plan = Plan(
        user_id=DEFAULT_USER_ID,
        plan_name="3D.2 Service Fixture",
        race_date=date(2026, 6, 7),
        race_distance="Marathon",
        is_active=True,
        training_days=["Tue", "Sat"],
    )
    session.add(plan)
    session.flush()
    return plan


@pytest.fixture
def seeded_user_no_plan(test_db_session):
    """User without an active plan — drives the ``no_active_plan`` path."""
    uid = uuid.UUID("0b5e5a42-0000-4000-8000-0000003d0003")
    test_db_session.add(UserAthleteLink(user_id=str(uid), athlete_id=4303))
    test_db_session.flush()
    return uid


# --------------------------------------------------------------------- #
# Validation envelopes
# --------------------------------------------------------------------- #


def test_save_rejects_invalid_phase(test_db_session, seeded_plan):
    status, payload = save_phase_goal(
        test_db_session,
        DEFAULT_USER_ID,
        phase_raw="Sharpen",  # not a canonical phase
        goal_text_raw="Focus on easy-day discipline.",
    )
    assert status == "invalid_phase"
    assert payload["error"] == "invalid_phase"
    assert "Base" in payload["message"]


@pytest.mark.parametrize("bad", [None, 123, "", "   "])
def test_save_rejects_non_string_or_empty_phase(test_db_session, seeded_plan, bad):
    status, _ = save_phase_goal(
        test_db_session,
        DEFAULT_USER_ID,
        phase_raw=bad,
        goal_text_raw="Some focus.",
    )
    assert status == "invalid_phase"


@pytest.mark.parametrize("bad", [None, 123, "", "   "])
def test_save_rejects_empty_goal_text(test_db_session, seeded_plan, bad):
    status, _ = save_phase_goal(
        test_db_session,
        DEFAULT_USER_ID,
        phase_raw="Base",
        goal_text_raw=bad,
    )
    assert status == "invalid_goal_text"


def test_save_rejects_goal_text_over_max_length(test_db_session, seeded_plan):
    too_long = "x" * (MAX_GOAL_TEXT_LENGTH + 1)
    status, payload = save_phase_goal(
        test_db_session,
        DEFAULT_USER_ID,
        phase_raw="Base",
        goal_text_raw=too_long,
    )
    assert status == "invalid_goal_text"
    assert str(MAX_GOAL_TEXT_LENGTH) in payload["message"]


def test_save_accepts_goal_text_at_max_length(test_db_session, seeded_plan):
    at_max = "a" * MAX_GOAL_TEXT_LENGTH
    status, payload = save_phase_goal(
        test_db_session,
        DEFAULT_USER_ID,
        phase_raw="Base",
        goal_text_raw=at_max,
    )
    assert status == "ok"
    assert payload["goal"]["goal_text"] == at_max


def test_save_trims_whitespace_from_goal_text(test_db_session, seeded_plan):
    status, payload = save_phase_goal(
        test_db_session,
        DEFAULT_USER_ID,
        phase_raw="Base",
        goal_text_raw="   Stay mostly in Zone 2 on long runs.   ",
    )
    assert status == "ok"
    assert payload["goal"]["goal_text"] == "Stay mostly in Zone 2 on long runs."


def test_save_rejects_explicit_bad_source(test_db_session, seeded_plan):
    status, payload = save_phase_goal(
        test_db_session,
        DEFAULT_USER_ID,
        phase_raw="Base",
        goal_text_raw="Stay mostly in Zone 2 on long runs.",
        source_raw="made_up_source",
    )
    assert status == "invalid_source"
    assert "auto_proposed" in payload["message"]


def test_save_accepts_omitted_source_and_defaults_to_auto_proposed(
    test_db_session, seeded_plan
):
    status, payload = save_phase_goal(
        test_db_session,
        DEFAULT_USER_ID,
        phase_raw="Base",
        goal_text_raw="Stay in control of easy days.",
    )
    assert status == "ok"
    assert payload["goal"]["source"] == GOAL_SOURCE_AUTO_PROPOSED


# --------------------------------------------------------------------- #
# Plan lookup
# --------------------------------------------------------------------- #


def test_save_errors_when_user_has_no_active_plan(test_db_session, seeded_user_no_plan):
    status, payload = save_phase_goal(
        test_db_session,
        seeded_user_no_plan,
        phase_raw="Base",
        goal_text_raw="Stay mostly in Zone 2 on long runs.",
    )
    assert status == "no_active_plan"
    assert payload["error"] == "no_active_plan"


# --------------------------------------------------------------------- #
# Happy path — single insert
# --------------------------------------------------------------------- #


def test_save_inserts_unconfirmed_goal_by_default(test_db_session, seeded_plan):
    status, payload = save_phase_goal(
        test_db_session,
        DEFAULT_USER_ID,
        phase_raw="base",  # case-insensitive
        goal_text_raw="Stay mostly in Zone 2 on long runs.",
    )
    assert status == "ok"
    goal = payload["goal"]
    assert goal["plan_id"] == seeded_plan.id
    assert goal["phase"] == Phase.BASE.value
    assert goal["status"] == GOAL_STATUS_ACTIVE
    assert goal["source"] == GOAL_SOURCE_AUTO_PROPOSED
    assert goal["confirmed_at"] is None
    assert goal["created_at"] is not None
    assert payload["superseded_goal_id"] is None


def test_save_stamps_confirmed_at_when_confirmed_true(test_db_session, seeded_plan):
    status, payload = save_phase_goal(
        test_db_session,
        DEFAULT_USER_ID,
        phase_raw="Base",
        goal_text_raw="Stay mostly in Zone 2 on long runs.",
        source_raw=GOAL_SOURCE_USER_STATED,
        confirmed=True,
    )
    assert status == "ok"
    assert payload["goal"]["confirmed_at"] is not None
    assert payload["goal"]["source"] == GOAL_SOURCE_USER_STATED


# --------------------------------------------------------------------- #
# Supersede-then-insert
# --------------------------------------------------------------------- #


def test_second_save_supersedes_prior_active_goal(test_db_session, seeded_plan):
    status1, payload1 = save_phase_goal(
        test_db_session,
        DEFAULT_USER_ID,
        phase_raw="Base",
        goal_text_raw="Initial Base focus.",
    )
    assert status1 == "ok"
    first_id = payload1["goal"]["id"]

    status2, payload2 = save_phase_goal(
        test_db_session,
        DEFAULT_USER_ID,
        phase_raw="Base",
        goal_text_raw="Refined Base focus after mid-week check-in.",
        source_raw="coach_refined",
    )
    assert status2 == "ok"
    assert payload2["superseded_goal_id"] == first_id
    assert payload2["goal"]["id"] != first_id
    assert payload2["goal"]["status"] == GOAL_STATUS_ACTIVE

    active = get_active_phase_goal(
        test_db_session, DEFAULT_USER_ID, seeded_plan.id, Phase.BASE
    )
    assert active is not None
    assert active.id == payload2["goal"]["id"]
    assert active.goal_text == "Refined Base focus after mid-week check-in."

    all_goals = get_all_goals_for_plan(test_db_session, DEFAULT_USER_ID, seeded_plan.id)
    assert len(all_goals) == 2
    assert all_goals[0].id == payload2["goal"]["id"]  # newest first
    assert all_goals[1].id == first_id
    assert all_goals[1].status == GOAL_STATUS_SUPERSEDED


def test_save_does_not_touch_other_phases(test_db_session, seeded_plan):
    status_base, payload_base = save_phase_goal(
        test_db_session,
        DEFAULT_USER_ID,
        phase_raw="Base",
        goal_text_raw="Base focus.",
    )
    status_build, payload_build = save_phase_goal(
        test_db_session,
        DEFAULT_USER_ID,
        phase_raw="Build",
        goal_text_raw="Build focus.",
    )
    assert status_base == "ok"
    assert status_build == "ok"
    assert payload_build["superseded_goal_id"] is None

    base_active = get_active_phase_goal(
        test_db_session, DEFAULT_USER_ID, seeded_plan.id, Phase.BASE
    )
    build_active = get_active_phase_goal(
        test_db_session, DEFAULT_USER_ID, seeded_plan.id, Phase.BUILD
    )
    assert base_active is not None and base_active.id == payload_base["goal"]["id"]
    assert build_active is not None and build_active.id == payload_build["goal"]["id"]
    assert base_active.status == GOAL_STATUS_ACTIVE
    assert build_active.status == GOAL_STATUS_ACTIVE


def test_get_active_phase_goal_returns_none_when_no_rows(test_db_session, seeded_plan):
    assert (
        get_active_phase_goal(
            test_db_session, DEFAULT_USER_ID, seeded_plan.id, Phase.PEAK
        )
        is None
    )


def test_get_all_goals_for_plan_is_empty_initially(test_db_session, seeded_plan):
    assert (
        get_all_goals_for_plan(test_db_session, DEFAULT_USER_ID, seeded_plan.id) == []
    )
