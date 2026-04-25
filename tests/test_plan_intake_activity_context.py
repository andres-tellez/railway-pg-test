from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.smartcoach_mobile_coach.plan_intake_activity_context import (
    PLAN_ACTIVITY_PREAMBLE_MARKER,
    apply_plan_activity_preamble_to_assistant_markdown,
    build_plan_intake_activity_context_block,
    compute_plan_intake_activity_summary,
    format_plan_intake_activity_context_block,
    format_user_visible_activity_overview,
    thread_has_plan_activity_preamble,
)


def test_format_plan_intake_activity_context_with_runs():
    s = format_plan_intake_activity_context_block(
        {
            "lookback_weeks": 12,
            "activities_found": 8,
            "has_running_data": True,
            "total_miles_window": 40.0,
            "avg_miles_per_week_approx": 3.3,
            "longest_run_miles": 12.5,
            "longest_run_date": "2026-03-01",
            "latest_run_date": "2026-04-01",
        }
    )
    assert "**8**" in s
    assert "40" in s
    assert "Do not" in s or "not" in s.lower()
    assert "race distance" in s.lower()


def test_format_plan_intake_activity_context_zero_runs():
    s = format_plan_intake_activity_context_block(
        {
            "lookback_weeks": 12,
            "activities_found": 0,
            "has_running_data": False,
            "total_miles_window": 0.0,
            "avg_miles_per_week_approx": 0.0,
            "longest_run_miles": 0.0,
            "longest_run_date": None,
            "latest_run_date": None,
        }
    )
    assert "no" in s.lower() or "0" in s
    assert "Strava" in s or "strava" in s.lower()


@patch(
    "src.smartcoach_mobile_coach.plan_intake_activity_context.DataCollectionService.fetch_strava_activities"
)
def test_compute_plan_intake_activity_summary(mock_fetch):
    mock_fetch.return_value = [
        {"date": "2026-04-10", "distance": 6.0},
        {"date": "2026-04-03", "distance": 10.0},
    ]
    session = MagicMock()
    out = compute_plan_intake_activity_summary(session, "user-uuid", lookback_weeks=12)
    assert out["activities_found"] == 2
    assert out["has_running_data"] is True
    assert out["total_miles_window"] == 16.0
    assert out["longest_run_miles"] == 10.0
    mock_fetch.assert_called_once()


def test_format_user_visible_activity_overview_empty_without_runs():
    assert (
        format_user_visible_activity_overview(
            {"has_running_data": False, "activities_found": 0}
        )
        == ""
    )


def test_format_user_visible_activity_overview_with_runs():
    s = format_user_visible_activity_overview(
        {
            "lookback_weeks": 12,
            "activities_found": 8,
            "has_running_data": True,
            "total_miles_window": 40.0,
            "avg_miles_per_week_approx": 3.3,
            "longest_run_miles": 12.5,
            "longest_run_date": "2026-03-01",
            "latest_run_date": "2026-04-01",
        }
    )
    assert "synced runs" in s.lower()
    assert "**8**" in s
    assert "40" in s


def test_apply_plan_activity_preamble_prepends_once():
    summary = {
        "lookback_weeks": 12,
        "activities_found": 2,
        "has_running_data": True,
        "total_miles_window": 10.0,
        "avg_miles_per_week_approx": 0.8,
        "longest_run_miles": 6.0,
        "longest_run_date": "2026-01-01",
        "latest_run_date": "2026-01-02",
    }
    out = apply_plan_activity_preamble_to_assistant_markdown(
        "What is your **race date**?",
        plan_creation_mode=True,
        activity_summary=summary,
        conversation_history=[],
    )
    assert "race date" in out
    assert PLAN_ACTIVITY_PREAMBLE_MARKER in out
    assert thread_has_plan_activity_preamble([{"role": "assistant", "content": out}])


def test_apply_plan_activity_preamble_skips_if_already_shown():
    summary = {
        "lookback_weeks": 12,
        "activities_found": 2,
        "has_running_data": True,
        "total_miles_window": 10.0,
        "avg_miles_per_week_approx": 0.8,
        "longest_run_miles": 6.0,
        "longest_run_date": "2026-01-01",
        "latest_run_date": "2026-01-02",
    }
    prior = f"Old reply\n\n{PLAN_ACTIVITY_PREAMBLE_MARKER}"
    out = apply_plan_activity_preamble_to_assistant_markdown(
        "Next question?",
        plan_creation_mode=True,
        activity_summary=summary,
        conversation_history=[{"role": "assistant", "content": prior}],
    )
    assert out == "Next question?"


def test_build_plan_intake_activity_context_block_integration():
    with patch(
        "src.smartcoach_mobile_coach.plan_intake_activity_context.DataCollectionService.fetch_strava_activities",
        return_value=[{"date": "2026-01-01", "distance": 5.0}],
    ):
        text = build_plan_intake_activity_context_block(MagicMock(), "any-uuid")
    assert "## Athlete activity snapshot" in text
    assert "**1**" in text
