"""
Regression: swallowed SQL errors on the shared Flask request session
must call session.rollback().

PostgreSQL aborts the whole transaction after a failed statement. If we
catch the exception and return without rollback, the next query on the
same connection fails with InFailedSqlTransaction.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from src.smartcoach_mobile_coach.agent_tools import _increment_tool_call_count
from src.smartcoach_mobile_coach.orchestrator import _load_coaching_preferences


def test_increment_tool_call_count_rolls_back_when_execute_fails() -> None:
    session = MagicMock()
    session.execute.side_effect = RuntimeError("simulated DB failure")
    _increment_tool_call_count(session, "get_run_summary")
    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_increment_tool_call_count_rolls_back_when_commit_fails() -> None:
    session = MagicMock()
    session.commit.side_effect = RuntimeError("simulated commit failure")
    _increment_tool_call_count(session, "get_run_summary")
    session.rollback.assert_called_once()


def test_load_coaching_preferences_rolls_back_when_query_fails() -> None:
    session = MagicMock()
    session.execute.side_effect = RuntimeError(
        "relation user_coach_preferences does not exist"
    )
    prefs = _load_coaching_preferences(session, "00000000-0000-0000-0000-000000000001")
    assert prefs["coaching_level"] == "beginner"
    session.rollback.assert_called_once()
