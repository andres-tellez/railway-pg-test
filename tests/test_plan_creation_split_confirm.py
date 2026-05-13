"""Split intake vs plan-generation confirmation (ux flags)."""

from __future__ import annotations

import pytest

from src.smartcoach_mobile_coach.plan_intake_flow import (
    update_plan_intake_state,
    user_requests_plan_generation,
)
from tests.coaching_intelligence.ambition_gap_fixtures import (
    synthetic_ambition_attributions,
)


@pytest.fixture
def full_draft() -> dict:
    return {
        "race_distance": "Marathon",
        "race_date": "2026-10-11",
        "primary_goal": "Target Time",
        "target_time": "3:00:00",
        "training_days": ["Mon", "Wed", "Fri", "Sat"],
        "long_run_day": "Sat",
    }


def test_user_requests_plan_generation_phrases():
    assert user_requests_plan_generation("create my plan")
    assert user_requests_plan_generation("Please build my plan.")
    assert user_requests_plan_generation("generate the plan")
    assert not user_requests_plan_generation("yes")
    assert not user_requests_plan_generation("sure")


def test_material_edit_clears_confirmation_ux(monkeypatch, full_draft):
    monkeypatch.setenv("SMARTCOACH_PLAN_CREATION_SPLIT_CONFIRM_V1", "1")
    prior = {
        "draft": dict(full_draft),
        "ux": {
            "intake_confirmed": True,
            "runner_review_delivered": True,
            "plan_generation_confirmed": True,
        },
        "alignment": {},
    }
    out = update_plan_intake_state(
        prior,
        updates={"target_time": "3:15:00"},
        source_user_message="",
    )
    ux = out.get("ux") or {}
    assert ux.get("intake_confirmed") is None
    assert ux.get("runner_review_delivered") is None
    assert ux.get("plan_generation_confirmed") is None


def test_intake_confirm_then_plan_generation_chip(monkeypatch, full_draft):
    monkeypatch.setenv("SMARTCOACH_PLAN_CREATION_SPLIT_CONFIRM_V1", "1")
    base = {"draft": dict(full_draft), "ux": {}, "alignment": {}}
    s1 = update_plan_intake_state(
        base,
        updates={},
        source_user_message="yes",
    )
    assert s1.get("ready_to_generate")
    assert s1["ux"].get("intake_confirmed") is True

    s2 = update_plan_intake_state(
        {**s1, "ux": {**s1["ux"], "runner_review_delivered": True}},
        updates={"plan_generation_confirmed": True},
        source_user_message="",
    )
    assert s2["ux"].get("plan_generation_confirmed") is True


def test_plan_generation_phrase_after_review(monkeypatch, full_draft):
    monkeypatch.setenv("SMARTCOACH_PLAN_CREATION_SPLIT_CONFIRM_V1", "1")
    s = update_plan_intake_state(
        {
            "draft": dict(full_draft),
            "ux": {"intake_confirmed": True, "runner_review_delivered": True},
            "alignment": {},
        },
        updates={},
        source_user_message="create my plan",
    )
    assert s["ux"].get("plan_generation_confirmed") is True


def test_tradeoff_continue_unblocks_pending(monkeypatch):
    monkeypatch.setenv("SMARTCOACH_PLAN_CREATION_SPLIT_CONFIRM_V1", "1")
    out = update_plan_intake_state(
        {
            "draft": {
                "race_distance": "Marathon",
                "race_date": "2026-10-11",
                "primary_goal": "Target Time",
                "target_time": "3:00:00",
                "training_days": ["Mon", "Wed", "Fri"],
                "long_run_day": "Fri",
            },
            "ux": {
                "intake_confirmed": True,
                "runner_review_delivered": True,
                "runner_review_assessment_status": "needs_user_decision",
                "runner_tradeoff_pending": True,
            },
            "alignment": {},
        },
        updates={"runner_tradeoff_choice": "continue_tradeoff"},
        source_user_message="",
    )
    ux = out["ux"]
    assert ux.get("runner_tradeoff_resolved") is True
    assert ux.get("runner_tradeoff_pending") is False


def test_classify_sub_three_three_days():
    from src.coaching_intelligence.pre_generation_runner_review import (
        STATUS_NEEDS_DECISION,
        classify_assessment_status_v1,
    )

    assessment_api = {
        "activity_summary": {
            "activities_found": 5,
            "avg_miles_per_week_approx": 45.0,
            "longest_run_miles": 18.0,
        },
        "ambition_gap": {
            "stance": "COHERENT",
            "baseline_band": "ESTABLISHED",
            "goal_demand": "TIME_TARGET",
            "thin_baseline_data": False,
            "attributions": synthetic_ambition_attributions(
                baseline_band="ESTABLISHED",
                goal_demand="TIME_TARGET",
                thin_baseline_data=False,
                longest_run_miles=18.0,
            ),
        },
        "intake_alignment_state": {
            "generation_ready": True,
            "unresolved_flags": [],
        },
    }
    plan_request = {
        "race_distance": "Marathon",
        "primary_goal": "Target Time",
        "target_time": "2:55:00",
        "training_days": ["Mon", "Wed", "Fri"],
        "race_date": "2027-01-01",
    }
    assert (
        classify_assessment_status_v1(
            assessment_api=assessment_api,
            plan_request=plan_request,
        )
        == STATUS_NEEDS_DECISION
    )


def test_classify_three_hours_flat_three_days_needs_user_decision():
    """Exact 3:00:00 counts as sub-3-level for marathon + ≤3 run days (tradeoff review)."""
    from src.coaching_intelligence.pre_generation_runner_review import (
        STATUS_NEEDS_DECISION,
        classify_assessment_status_v1,
    )

    assessment_api = {
        "activity_summary": {
            "activities_found": 5,
            "avg_miles_per_week_approx": 45.0,
            "longest_run_miles": 18.0,
        },
        "ambition_gap": {
            "stance": "COHERENT",
            "baseline_band": "ESTABLISHED",
            "goal_demand": "TIME_TARGET",
            "thin_baseline_data": False,
            "attributions": synthetic_ambition_attributions(
                baseline_band="ESTABLISHED",
                goal_demand="TIME_TARGET",
                thin_baseline_data=False,
                longest_run_miles=18.0,
            ),
        },
        "intake_alignment_state": {
            "generation_ready": True,
            "unresolved_flags": [],
        },
    }
    plan_request = {
        "race_distance": "Marathon",
        "primary_goal": "Target Time",
        "target_time": "3:00:00",
        "training_days": ["Mon", "Wed", "Sat"],
        "race_date": "2027-01-01",
    }
    assert (
        classify_assessment_status_v1(
            assessment_api=assessment_api,
            plan_request=plan_request,
        )
        == STATUS_NEEDS_DECISION
    )
