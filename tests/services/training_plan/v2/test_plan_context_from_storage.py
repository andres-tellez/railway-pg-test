"""Tests for :mod:`src.services.training_plan.v2.plan_context_from_storage`."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from src.db.dao import plans_dao
from src.db.models.plan_workouts import PlanWorkout
from src.db.models.user_identity import UserIdentity
from src.smartcoach_mobile_coach import agent_tools
from src.services.training_plan.v2.plan_context_from_storage import (
    build_plan_context_from_active_plan,
)


def test_build_plan_context_returns_none_when_no_plan(test_db_session: Session) -> None:
    uid = uuid4()
    assert build_plan_context_from_active_plan(test_db_session, uid) is None


def test_build_plan_context_sets_weeks_and_metadata(test_db_session: Session) -> None:
    uid = uuid4()
    test_db_session.add(UserIdentity(user_id=uid, email=f"{uid.hex}@t.example"))
    plan = plans_dao.create_plan(
        test_db_session,
        {
            "user_id": uid,
            "plan_name": "Test Plan",
            "race_date": date(2026, 10, 11),
            "race_distance": "Marathon",
            "is_active": True,
        },
    )
    test_db_session.flush()
    test_db_session.add(
        PlanWorkout(
            plan_id=plan.id,
            date=date(2026, 4, 20),
            workout_type="easy",
            description="easy",
            miles=5.0,
            intensity="easy",
            phase="Base",
            run_type_key="easy",
        )
    )
    test_db_session.add(
        PlanWorkout(
            plan_id=plan.id,
            date=date(2026, 4, 22),
            workout_type="long",
            description="long",
            miles=12.0,
            intensity="easy",
            phase="Base",
            run_type_key="long_run",
        )
    )
    test_db_session.commit()

    ctx = build_plan_context_from_active_plan(test_db_session, uid)
    assert ctx is not None
    assert ctx.metadata and ctx.metadata.get("plan_id") == plan.id
    weeks = (ctx.detailed_plan or {}).get("weeks") or []
    assert len(weeks) == 1
    assert weeks[0]["week_number"] == 1
    assert weeks[0]["weekly_mileage"] == pytest.approx(17.0)
    assert weeks[0]["long_run_miles"] == pytest.approx(12.0)
    assert ctx.validation == {"valid": True, "issues": []}
    assert ctx.spine_quality_issues == []


@patch(
    "src.smartcoach_mobile_coach.agent_tools.generate_plan_explanation",
    return_value="**Grounded** explanation.",
)
def test_tool_explain_current_plan_happy_path(
    _mock_gen: MagicMock,
    test_db_session: Session,
) -> None:
    uid = uuid4()
    test_db_session.add(UserIdentity(user_id=uid, email=f"{uid.hex}@t.example"))
    plan = plans_dao.create_plan(
        test_db_session,
        {
            "user_id": uid,
            "plan_name": "T",
            "race_date": date(2026, 10, 11),
            "race_distance": "Marathon",
            "is_active": True,
        },
    )
    test_db_session.flush()
    test_db_session.add(
        PlanWorkout(
            plan_id=plan.id,
            date=date(2026, 4, 20),
            workout_type="easy",
            description="e",
            miles=3.0,
            intensity="easy",
            phase="Base",
            run_type_key="easy",
        )
    )
    test_db_session.commit()

    out = agent_tools.execute_tool(
        test_db_session,
        str(uid),
        "explain_current_plan",
        "{}",
    )
    assert out.get("explanation") == "**Grounded** explanation."
    assert out.get("plan_id") == plan.id
    assert _mock_gen.called
