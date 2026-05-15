"""Unit tests for the canonical active-plan service facade."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.services.plan.active_plan import has_active_plan


def test_has_active_plan_returns_true_when_row_exists() -> None:
    session = MagicMock()
    row = MagicMock()
    session.execute.return_value.first.return_value = row
    assert has_active_plan(session, "user-1") is True


def test_has_active_plan_returns_false_when_no_row() -> None:
    session = MagicMock()
    session.execute.return_value.first.return_value = None
    assert has_active_plan(session, "user-1") is False


def test_has_active_plan_returns_false_for_empty_user_id() -> None:
    session = MagicMock()
    assert has_active_plan(session, "") is False
    session.execute.assert_not_called()


def test_has_active_plan_returns_false_and_rolls_back_on_db_error() -> None:
    session = MagicMock()
    session.execute.side_effect = RuntimeError("relation plans does not exist")
    assert has_active_plan(session, "user-1") is False
    session.rollback.assert_called_once()
