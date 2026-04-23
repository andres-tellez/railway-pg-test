"""Phase F — remember_plan_preference tool."""

from __future__ import annotations

import json
import uuid

import pytest

from src.db.models.user_identity import UserIdentity
from src.smartcoach_mobile_coach import agent_tools


@pytest.fixture
def uid_str(test_db_session) -> str:
    u = uuid.uuid4()
    test_db_session.add(UserIdentity(user_id=u, name="Mem Tester"))
    test_db_session.commit()
    return str(u)


def test_remember_invalid_user_id(test_db_session):
    out = agent_tools.tool_remember_plan_preference(
        test_db_session, "not-a-uuid", {"preference_text": "Saturday long runs"}
    )
    assert out["error"] == "invalid_user_id"


def test_remember_missing_text(test_db_session, uid_str):
    out = agent_tools.tool_remember_plan_preference(test_db_session, uid_str, {})
    assert out["error"] == "invalid_preference_text"


def test_remember_happy_path(test_db_session, uid_str):
    out = agent_tools.tool_remember_plan_preference(
        test_db_session,
        uid_str,
        {"preference_text": "Keep long runs on Saturday"},
    )
    assert out.get("saved") is True
    assert out["memory"]["text"] == "Keep long runs on Saturday"
    assert out["memory"]["source"] == "coach_tool"
    assert out["memory"]["memory_type"] == "long_run_day"


def test_remember_deduplicates_near_duplicate(test_db_session, uid_str):
    out1 = agent_tools.tool_remember_plan_preference(
        test_db_session,
        uid_str,
        {
            "preference_text": (
                "Prefer Saturday for long runs in marathon training plan schedule"
            ),
        },
    )
    assert out1.get("saved") is True
    assert not out1.get("deduplicated")
    out2 = agent_tools.tool_remember_plan_preference(
        test_db_session,
        uid_str,
        {
            "preference_text": (
                "I prefer Saturday for long runs in marathon training plan schedule"
            ),
        },
    )
    assert out2.get("deduplicated") is True


def test_execute_tool_dispatches_remember(test_db_session, uid_str):
    out = agent_tools.execute_tool(
        test_db_session,
        uid_str,
        "remember_plan_preference",
        json.dumps({"preference_text": "No doubles after work"}),
    )
    assert out.get("saved") is True
