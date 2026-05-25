"""Training phase resolver for recommendation policy."""

from __future__ import annotations

from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from src.db.models.plans import Plan
from src.smartcoach_mobile_coach.runner_profile.recommendations import (
    training_phase_resolver as tp_resolver,
)


def test_infer_week_index_buckets_match_weekly_rebuild_ratios():
    assert tp_resolver._infer_phase_from_week_index(1, 20).value == "Base"
    assert tp_resolver._infer_phase_from_week_index(8, 20).value == "Base"
    assert tp_resolver._infer_phase_from_week_index(9, 20).value == "Build"
    assert tp_resolver._infer_phase_from_week_index(14, 20).value == "Build"
    assert tp_resolver._infer_phase_from_week_index(18, 20).value == "Peak"
    assert tp_resolver._infer_phase_from_week_index(19, 20).value == "Taper"
    assert tp_resolver._infer_phase_from_week_index(20, 20).value == "Taper"


def test_resolve_no_plan():
    sess = MagicMock(spec=Session)
    r = tp_resolver.resolve_current_training_phase(sess, "u", plan=None)
    assert r.phase == "Base"
    assert r.source == "no_plan"


def test_resolve_plan_workouts_current_week(monkeypatch):
    from datetime import date

    workouts = [MagicMock(phase="Peak"), MagicMock(phase="Peak")]

    sess = MagicMock(spec=Session)
    sess.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
        workouts
    )
    monkeypatch.setattr(
        tp_resolver,
        "get_week_bounds_for_date",
        lambda _d: (date(2026, 5, 18), date(2026, 5, 24)),
    )

    plan = MagicMock(spec=Plan)
    plan.id = 1
    r = tp_resolver.resolve_current_training_phase(
        sess, "u", plan=plan, today=date(2026, 5, 20)
    )
    assert r.phase == "Peak"
    assert r.source == "plan_workouts_current_week"
    assert r.week_start == date(2026, 5, 18)
