"""Deprecation lock-in test for tool_get_weekly_training_insight.

Locks the V1.6 Pre-Phase A 0.C decision: the tool is deprecated and emits a
DeprecationWarning on every invocation. This keeps existing coach flows
working (no runtime break) while giving CI / code review a loud, grep-able
signal that the tool should not gain new consumers.

Spec ref: PHASE_3_IMPLEMENTATION_CHECKLIST 0.C. Replacement is
get_weekly_plan (V1.7, AGENTIC_COACH.md Topic 9).

Guardrail: if a future refactor drops the DeprecationWarning, this test
turns red — forcing a conversation about whether the deprecation policy
has changed.
"""

from __future__ import annotations

import warnings
from unittest.mock import MagicMock

import pytest

from src.smartcoach_mobile_coach import agent_tools
from src.smartcoach_mobile_coach.agent_tools import (
    _GWTI_DEPRECATION_MESSAGE,
    tool_get_weekly_training_insight,
)


class TestDeprecationWarningEmitted:
    def test_direct_call_emits_deprecation_warning(self, monkeypatch):
        monkeypatch.setattr(
            agent_tools,
            "get_latest_weekly_insight",
            lambda *a, **k: {"ok": True},
        )
        monkeypatch.setattr(
            agent_tools,
            "weekly_insight_tool_slim_default_from_env",
            lambda: True,
        )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            tool_get_weekly_training_insight(
                MagicMock(),
                "00000000-0000-0000-0000-000000000001",
            )

        deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert len(deprecations) == 1, (
            "Expected exactly one DeprecationWarning from "
            "tool_get_weekly_training_insight; 0.C deprecation lock broken."
        )

    def test_message_mentions_replacement_and_policy(self, monkeypatch):
        monkeypatch.setattr(
            agent_tools,
            "get_latest_weekly_insight",
            lambda *a, **k: {"ok": True},
        )
        monkeypatch.setattr(
            agent_tools,
            "weekly_insight_tool_slim_default_from_env",
            lambda: True,
        )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            tool_get_weekly_training_insight(
                MagicMock(),
                "00000000-0000-0000-0000-000000000001",
            )

        messages = [str(w.message) for w in caught]
        assert any("deprecated" in m.lower() for m in messages)
        assert any("get_weekly_plan" in m for m in messages), (
            "Deprecation message must point callers at the replacement "
            "tool so new code knows where to go."
        )
        assert any("0.C" in m for m in messages), (
            "Deprecation message must cite the checklist item (0.C) so "
            "reviewers can find the policy."
        )

    def test_warning_is_filterable_by_category(self, monkeypatch):
        """Consumers that explicitly silence DeprecationWarning (e.g. the
        live orchestrator) must be able to do so — this is a standard
        Python warnings contract check."""
        monkeypatch.setattr(
            agent_tools,
            "get_latest_weekly_insight",
            lambda *a, **k: {"ok": True},
        )
        monkeypatch.setattr(
            agent_tools,
            "weekly_insight_tool_slim_default_from_env",
            lambda: True,
        )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("ignore", DeprecationWarning)
            tool_get_weekly_training_insight(
                MagicMock(),
                "00000000-0000-0000-0000-000000000001",
            )

        assert not any(issubclass(w.category, DeprecationWarning) for w in caught)


class TestDeprecationMessageConstant:
    """Lock the published message constant — its wording is depended on by
    log aggregation / alerting rules that grep for specific phrases."""

    def test_message_mentions_v16_and_0c(self):
        assert "V1.6" in _GWTI_DEPRECATION_MESSAGE
        assert "0.C" in _GWTI_DEPRECATION_MESSAGE

    def test_message_names_replacement_tool(self):
        assert "get_weekly_plan" in _GWTI_DEPRECATION_MESSAGE

    def test_message_states_no_new_consumers_policy(self):
        lowered = _GWTI_DEPRECATION_MESSAGE.lower()
        assert "new consumer" in lowered or "do not add" in lowered


class TestBehaviorIsPreserved:
    """Deprecation must NOT change the tool's return contract; existing
    coach conversations depend on it."""

    def test_return_value_pass_through(self, monkeypatch):
        expected = {"schema_version": 99, "marker": "preserved"}
        monkeypatch.setattr(
            agent_tools,
            "get_latest_weekly_insight",
            lambda *a, **k: expected,
        )
        monkeypatch.setattr(
            agent_tools,
            "weekly_insight_tool_slim_default_from_env",
            lambda: True,
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = tool_get_weekly_training_insight(
                MagicMock(),
                "00000000-0000-0000-0000-000000000001",
            )

        assert result is expected

    @pytest.mark.parametrize(
        "include_kpi_detail, env_slim_default, expected_slim_arg",
        [
            (None, True, True),
            (None, False, False),
            (True, True, False),
            (False, False, True),
        ],
    )
    def test_include_kpi_detail_still_resolves_slim_flag(
        self,
        monkeypatch,
        include_kpi_detail,
        env_slim_default,
        expected_slim_arg,
    ):
        captured_slim: list[bool] = []

        def fake_get(session, uid, *, slim=False):
            captured_slim.append(slim)
            return {"ok": True}

        monkeypatch.setattr(agent_tools, "get_latest_weekly_insight", fake_get)
        monkeypatch.setattr(
            agent_tools,
            "weekly_insight_tool_slim_default_from_env",
            lambda: env_slim_default,
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            tool_get_weekly_training_insight(
                MagicMock(),
                "00000000-0000-0000-0000-000000000001",
                include_kpi_detail=include_kpi_detail,
            )

        assert captured_slim == [expected_slim_arg]
