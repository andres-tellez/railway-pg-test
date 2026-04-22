"""
Tests for V1.6 Phase D 3D.1 — ``user_phase_goals`` table + ORM model.

Covers:

* Table creation via ``Base.metadata.create_all`` (implicit — the fact
  that inserts succeed means the schema landed). Test-bootstrap
  registration happens in ``tests/conftest.py``.
* Required / nullable columns match the spec rationale in
  ``src/db/models/user_phase_goals.py``.
* ``status`` and ``source`` server defaults resolve to the V1.6
  writer-produced values.
* Supersede-then-insert preserves history without requiring a partial
  unique index.
* Module-level constants for status / source / phase values stay in
  sync with the ORM column contracts.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest

from src.db.models.plans import Plan
from src.db.models.user_athletes import UserAthleteLink
from src.db.models.user_phase_goals import (
    GOAL_SOURCE_AUTO_PROPOSED,
    GOAL_SOURCE_COACH_REFINED,
    GOAL_SOURCE_USER_STATED,
    GOAL_SOURCE_VALUES,
    GOAL_STATUS_ACTIVE,
    GOAL_STATUS_COMPLETED,
    GOAL_STATUS_DROPPED,
    GOAL_STATUS_SUPERSEDED,
    GOAL_STATUS_VALUES,
    UserPhaseGoal,
)


DEFAULT_USER_ID = uuid.UUID("0b5e5a42-0000-4000-8000-0000003d0001")


@pytest.fixture
def seeded_plan(test_db_session):
    """Seed one user + one active plan so the FK chain is satisfied."""
    session = test_db_session
    session.add(UserAthleteLink(user_id=str(DEFAULT_USER_ID), athlete_id=4301))
    plan = Plan(
        user_id=DEFAULT_USER_ID,
        plan_name="3D.1 Goals Fixture",
        race_date=date(2026, 6, 7),
        race_distance="Marathon",
        is_active=True,
        training_days=["Tue", "Sat"],
    )
    session.add(plan)
    session.flush()
    return plan


# ---------------------------------------------------------------------
# Module-level enum contracts
# ---------------------------------------------------------------------


def test_status_values_contract_is_stable_and_complete():
    # Writers MUST only produce the first three in V1.6 but the full
    # set is exposed so readers (e.g. the retrospective hook) can
    # match on COMPLETED without re-deriving the string literally.
    assert GOAL_STATUS_VALUES == (
        GOAL_STATUS_ACTIVE,
        GOAL_STATUS_SUPERSEDED,
        GOAL_STATUS_COMPLETED,
        GOAL_STATUS_DROPPED,
    )
    assert len(set(GOAL_STATUS_VALUES)) == len(GOAL_STATUS_VALUES)


def test_source_values_contract_is_stable_and_complete():
    assert GOAL_SOURCE_VALUES == (
        GOAL_SOURCE_AUTO_PROPOSED,
        GOAL_SOURCE_COACH_REFINED,
        GOAL_SOURCE_USER_STATED,
    )
    assert len(set(GOAL_SOURCE_VALUES)) == len(GOAL_SOURCE_VALUES)


# ---------------------------------------------------------------------
# Table contract
# ---------------------------------------------------------------------


def test_table_name_is_user_phase_goals():
    assert UserPhaseGoal.__tablename__ == "user_phase_goals"


def test_required_columns_exist_and_nullable_contract(seeded_plan, test_db_session):
    # Inserting a minimal row exercises every NOT-NULL column.
    goal = UserPhaseGoal(
        user_id=DEFAULT_USER_ID,
        plan_id=seeded_plan.id,
        phase="Base",
        goal_text="Stay mostly in Zone 2 on easy days.",
    )
    test_db_session.add(goal)
    test_db_session.flush()

    # Server defaults resolve on flush.
    assert goal.id is not None
    assert goal.status == GOAL_STATUS_ACTIVE
    assert goal.source == GOAL_SOURCE_AUTO_PROPOSED
    assert goal.confirmed_at is None
    assert goal.created_at is not None


def test_confirmed_at_roundtrips_when_set(seeded_plan, test_db_session):
    when = datetime(2026, 4, 22, 14, 5, 0, tzinfo=timezone.utc).replace(tzinfo=None)
    goal = UserPhaseGoal(
        user_id=DEFAULT_USER_ID,
        plan_id=seeded_plan.id,
        phase="Build",
        goal_text="Keep Tempo intervals mostly on target.",
        source=GOAL_SOURCE_USER_STATED,
        confirmed_at=when,
    )
    test_db_session.add(goal)
    test_db_session.flush()
    test_db_session.refresh(goal)
    assert goal.confirmed_at == when
    assert goal.source == GOAL_SOURCE_USER_STATED


# ---------------------------------------------------------------------
# Supersede-then-insert history pattern
# ---------------------------------------------------------------------


def test_supersede_then_insert_preserves_history(seeded_plan, test_db_session):
    """Demonstrates the 3D.2 writer pattern the model is designed for.

    After supersede+insert, exactly one row is ``active`` for
    (user, plan, phase) and the prior row is queryable with
    ``status='superseded'``.
    """
    first = UserPhaseGoal(
        user_id=DEFAULT_USER_ID,
        plan_id=seeded_plan.id,
        phase="Base",
        goal_text="Run easy days easy.",
    )
    test_db_session.add(first)
    test_db_session.flush()

    # Supersede in-place.
    first.status = GOAL_STATUS_SUPERSEDED
    second = UserPhaseGoal(
        user_id=DEFAULT_USER_ID,
        plan_id=seeded_plan.id,
        phase="Base",
        goal_text="Stay mostly in Zone 2 on easy days.",
        source=GOAL_SOURCE_COACH_REFINED,
    )
    test_db_session.add(second)
    test_db_session.flush()

    actives = (
        test_db_session.query(UserPhaseGoal)
        .filter_by(user_id=DEFAULT_USER_ID, plan_id=seeded_plan.id, phase="Base")
        .filter(UserPhaseGoal.status == GOAL_STATUS_ACTIVE)
        .all()
    )
    assert len(actives) == 1
    assert actives[0].goal_text == "Stay mostly in Zone 2 on easy days."
    assert actives[0].source == GOAL_SOURCE_COACH_REFINED

    superseded = (
        test_db_session.query(UserPhaseGoal)
        .filter_by(user_id=DEFAULT_USER_ID, plan_id=seeded_plan.id, phase="Base")
        .filter(UserPhaseGoal.status == GOAL_STATUS_SUPERSEDED)
        .all()
    )
    assert len(superseded) == 1
    assert superseded[0].goal_text == "Run easy days easy."


def test_history_rows_for_different_phases_do_not_collide(seeded_plan, test_db_session):
    """Separate phases have independent active goals on the same plan."""
    for phase, text in [
        ("Base", "Run easy days easy."),
        ("Build", "Nail Tempo zones."),
        ("Peak", "Execute on race-pace days."),
        ("Taper", "Maintain, do not improve."),
    ]:
        test_db_session.add(
            UserPhaseGoal(
                user_id=DEFAULT_USER_ID,
                plan_id=seeded_plan.id,
                phase=phase,
                goal_text=text,
            )
        )
    test_db_session.flush()

    actives = (
        test_db_session.query(UserPhaseGoal)
        .filter_by(user_id=DEFAULT_USER_ID, plan_id=seeded_plan.id)
        .filter(UserPhaseGoal.status == GOAL_STATUS_ACTIVE)
        .all()
    )
    assert {g.phase for g in actives} == {"Base", "Build", "Peak", "Taper"}
