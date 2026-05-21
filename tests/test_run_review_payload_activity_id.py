"""Run Review mobile payload wires ``data.activity_id`` for card-once / thread."""

from __future__ import annotations

from src.smartcoach_mobile_coach.run_review.context import RunReviewContext
from src.smartcoach_mobile_coach.run_review.payload import build_payload_data
from src.smartcoach_mobile_coach.thread_derived_context import (
    activity_id_from_run_summary_envelope,
)


def test_build_payload_data_injects_wire_activity_id() -> None:
    ctx = RunReviewContext(
        activity_id=88112233,
        anchor_local_date="2026-05-20",
        facts={"title": "Morning run", "local_date": "2026-05-20"},
        resolved_via="test",
        scope="single_run",
    )
    data = build_payload_data(ctx)
    assert data.get("activity_id") == 88112233
    assert isinstance(data.get("facts"), dict)


def test_activity_id_from_envelope_prefers_data_top_level() -> None:
    env = {
        "type": "run_summary",
        "content": "ok",
        "data": {"activity_id": 42, "facts": {"title": "Easy"}},
    }
    assert activity_id_from_run_summary_envelope(env) == 42


def test_activity_id_from_envelope_falls_through_comparison() -> None:
    env = {
        "type": "run_summary",
        "content": "ok",
        "data": {
            "facts": {},
            "comparison": {"this_run": {"activity_id": 9001}},
        },
    }
    assert activity_id_from_run_summary_envelope(env) == 9001
