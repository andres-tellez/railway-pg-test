"""
Tests for V1.6 Phase D 3D.2 — ``tool_save_phase_goal`` wrapper and
``execute_tool`` dispatch integration.

Focus areas:

* User-id guard (non-UUID string → ``invalid_user_id``).
* Successful happy path returns ``saved=True`` with serialized goal.
* Validation errors from the service propagate through the wrapper
  without ``saved`` being added accidentally.
* Commit semantics: on success, the row is committed (visible to a
  fresh query in the same session); on service-level error nothing
  is written.
* The tool is registered in ``execute_tool`` under
  ``"save_phase_goal"`` and routes to the wrapper.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from src.db.models.plans import Plan
from src.db.models.user_athletes import UserAthleteLink
from src.db.models.user_phase_goals import (
    GOAL_SOURCE_COACH_REFINED,
    GOAL_STATUS_ACTIVE,
    UserPhaseGoal,
)
from src.smartcoach_mobile_coach.agent_tools import (
    execute_tool,
    tool_save_phase_goal,
)


USER_ID = uuid.UUID("0b5e5a42-0000-4000-8000-0000003d2001")


@pytest.fixture
def seeded_plan(test_db_session):
    session = test_db_session
    session.add(UserAthleteLink(user_id=str(USER_ID), athlete_id=4401))
    plan = Plan(
        user_id=USER_ID,
        plan_name="3D.2 Tool Fixture",
        race_date=date(2026, 6, 7),
        race_distance="Marathon",
        is_active=True,
        training_days=["Tue", "Sat"],
    )
    session.add(plan)
    session.flush()
    return plan


def test_tool_rejects_non_uuid_user_id(test_db_session, seeded_plan):
    result = tool_save_phase_goal(
        test_db_session,
        internal_user_id="not-a-uuid",
        args={
            "phase": "Base",
            "goal_text": "Stay in Zone 2 on long runs.",
        },
    )
    assert result == {
        "error": "invalid_user_id",
        "message": "internal_user_id must be a UUID string.",
    }


def test_tool_returns_saved_envelope_on_success(test_db_session, seeded_plan):
    result = tool_save_phase_goal(
        test_db_session,
        internal_user_id=str(USER_ID),
        args={
            "phase": "base",
            "goal_text": "Stay mostly in Zone 2 on long runs.",
        },
    )

    assert result["saved"] is True
    assert result["superseded_goal_id"] is None
    assert result["message"] == "Saved your Base focus."
    goal = result["goal"]
    assert goal["phase"] == "Base"
    assert goal["status"] == GOAL_STATUS_ACTIVE
    assert goal["goal_text"] == "Stay mostly in Zone 2 on long runs."
    assert goal["confirmed_at"] is None

    # Row is committed — a fresh query sees it.
    persisted = (
        test_db_session.query(UserPhaseGoal)
        .filter(UserPhaseGoal.id == goal["id"])
        .one()
    )
    assert persisted.goal_text == "Stay mostly in Zone 2 on long runs."


def test_tool_passes_through_validation_errors_without_saved_flag(
    test_db_session, seeded_plan
):
    result = tool_save_phase_goal(
        test_db_session,
        internal_user_id=str(USER_ID),
        args={
            "phase": "Sharpen",  # invalid phase
            "goal_text": "Anything.",
        },
    )
    assert "saved" not in result
    assert result["error"] == "invalid_phase"


def test_tool_passes_through_no_active_plan_error(test_db_session):
    uid = uuid.UUID("0b5e5a42-0000-4000-8000-0000003d2002")
    test_db_session.add(UserAthleteLink(user_id=str(uid), athlete_id=4402))
    test_db_session.flush()

    result = tool_save_phase_goal(
        test_db_session,
        internal_user_id=str(uid),
        args={
            "phase": "Base",
            "goal_text": "Stay mostly in Zone 2 on long runs.",
        },
    )
    assert result == {
        "error": "no_active_plan",
        "message": (
            "No active plan on file for this user. Generate a plan "
            "before setting a phase focus."
        ),
    }


def test_tool_coerces_confirmed_true_string(test_db_session, seeded_plan):
    result = tool_save_phase_goal(
        test_db_session,
        internal_user_id=str(USER_ID),
        args={
            "phase": "Build",
            "goal_text": "Keep Tempo intervals feeling like controlled effort.",
            "source": GOAL_SOURCE_COACH_REFINED,
            "confirmed": "true",
        },
    )
    assert result["saved"] is True
    assert result["goal"]["confirmed_at"] is not None
    assert result["goal"]["source"] == GOAL_SOURCE_COACH_REFINED


def test_execute_tool_routes_save_phase_goal(test_db_session, seeded_plan, monkeypatch):
    """``execute_tool("save_phase_goal", ...)`` routes to the wrapper.

    We patch the ``_increment_tool_call_count`` commit-counter (it eagerly
    commits the outer SQLAlchemy transaction, which interacts poorly with
    the rollback-scoped ``test_db_session`` fixture on SQLite). This test
    only exercises dispatch — the wrapper contract is covered in full by
    the direct-call tests above.
    """
    import json

    from src.smartcoach_mobile_coach import agent_tools as _agent_tools

    monkeypatch.setattr(
        _agent_tools, "_increment_tool_call_count", lambda session, name: None
    )

    result = execute_tool(
        test_db_session,
        str(USER_ID),
        "save_phase_goal",
        json.dumps(
            {
                "phase": "Base",
                "goal_text": "Stay mostly in Zone 2 on long runs.",
            }
        ),
    )
    assert result.get("saved") is True, f"unexpected result: {result}"
    assert result["goal"]["phase"] == "Base"
