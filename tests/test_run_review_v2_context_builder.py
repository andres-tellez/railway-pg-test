"""Unit tests for the Run Review V2 context builder with mocked tools."""

# pylint: disable=missing-function-docstring,redefined-outer-name

from __future__ import annotations

from typing import Any, Dict

import pytest

import src.smartcoach_mobile_coach.run_review.context_builder as cb_mod
from src.smartcoach_mobile_coach.run_review.classifier import ClassifierResult
from src.smartcoach_mobile_coach.run_review.config import RunReviewConfig
from src.smartcoach_mobile_coach.run_review.context_builder import build_context
from src.smartcoach_mobile_coach.run_review.errors import RunReviewFallback


def _cfg(fetch_splits: bool = True) -> RunReviewConfig:
    return RunReviewConfig(
        enabled=True,
        classifier_mode="heuristic",
        fetch_splits=fetch_splits,
        include_comparisons=False,
        max_response_tokens=800,
        classifier_max_tokens=200,
        classifier_timeout_s=6.0,
        responder_timeout_s=30.0,
        responder_model_override="",
        classifier_model="gpt-4o-mini",
        evidence_pack_enabled=False,
    )


def _classifier(scope: str = "single_run", day_hint: str = None) -> ClassifierResult:
    return ClassifierResult(
        is_run_review=True,
        scope=scope,
        confidence="high",
        day_hint=day_hint,
        source="heuristic",
        reason_code="test",
    )


def _patch_tools(monkeypatch, *, summary, splits=None, find_by_date=None, search=None):
    """Replace agent tools with deterministic stubs for unit tests.

    The context builder imports the real ``src.smartcoach_mobile_coach.agent_tools``
    inside the helper functions, so we patch attributes on that module.
    """
    import src.smartcoach_mobile_coach.agent_tools as agent_tools_mod

    if find_by_date is None:
        find_by_date = lambda _s, _u, _ld: {  # noqa: E731
            "disambiguation_needed": False,
            "activity_id": 9001,
            "local_date": "2026-05-14",
        }
    if search is None:
        search = lambda _s, _u, **_kw: {  # noqa: E731
            "matches": [
                {
                    "activity_id": 9001,
                    "start_local_date": "2026-05-14",
                    "title": "Run",
                    "distance_display": "6.1 mi",
                    "start_local_time_display": "Wed 6:30 PM",
                }
            ],
            "count": 1,
            "filters": {},
            "message": "ok",
        }

    monkeypatch.setattr(agent_tools_mod, "tool_find_runs_by_date", find_by_date)
    monkeypatch.setattr(agent_tools_mod, "tool_search_runs", search)
    monkeypatch.setattr(
        agent_tools_mod,
        "tool_get_run_summary",
        lambda *_a, **_kw: summary,
    )
    if splits is not None:
        monkeypatch.setattr(
            agent_tools_mod,
            "tool_get_run_splits",
            lambda *_a, **_kw: splits,
        )
    else:
        monkeypatch.setattr(
            agent_tools_mod,
            "tool_get_run_splits",
            lambda *_a, **_kw: {"error": "not_found"},
        )


def test_build_context_uses_thread_activity_id_hint(monkeypatch) -> None:
    summary = {
        "facts": {
            "title": "Run",
            "execution_summary": {
                "plan_status": "executed",
                "planned": {"type": "tempo", "miles": 6.0},
                "actual": {"type": "tempo"},
            },
        },
        "training_kpis": {"hr_drift_band": "yellow"},
    }
    _patch_tools(monkeypatch, summary=summary)
    ctx = build_context(
        session=None,
        internal_user_id="u1",
        anchor_local_date="2026-05-14",
        classifier=_classifier(),
        cfg=_cfg(fetch_splits=False),
        activity_id_hint=None,
        thread_activity_id=42,
    )
    assert ctx.activity_id == 42
    assert ctx.resolved_via == "thread_context"
    assert ctx.workout_intent.planned_type == "tempo"


def test_build_context_resolves_most_recent_run_when_day_hint_last_run(
    monkeypatch,
) -> None:
    summary = {
        "facts": {
            "execution_summary": {
                "plan_status": "executed",
                "planned": {"type": "easy", "miles": 4.0},
                "actual": {"type": "easy"},
            }
        }
    }
    _patch_tools(monkeypatch, summary=summary)
    ctx = build_context(
        session=None,
        internal_user_id="u1",
        anchor_local_date="",  # no anchor
        classifier=_classifier(day_hint="last_run"),
        cfg=_cfg(fetch_splits=False),
    )
    assert ctx.activity_id == 9001
    assert ctx.resolved_via == "most_recent_run"
    assert ctx.anchor_local_date == "2026-05-14"


def test_build_context_fallback_when_summary_errors(monkeypatch) -> None:
    summary = {"error": "not_found", "message": "missing"}
    _patch_tools(monkeypatch, summary=summary)
    with pytest.raises(RunReviewFallback):
        build_context(
            session=None,
            internal_user_id="u1",
            anchor_local_date="2026-05-14",
            classifier=_classifier(),
            cfg=_cfg(fetch_splits=False),
        )


def test_build_context_fallback_when_disambiguation_needed(monkeypatch) -> None:
    summary = {"facts": {}}

    def _find(_s, _u, _ld):
        return {"disambiguation_needed": True, "candidates": []}

    _patch_tools(monkeypatch, summary=summary, find_by_date=_find)
    with pytest.raises(RunReviewFallback):
        build_context(
            session=None,
            internal_user_id="u1",
            anchor_local_date="2026-05-14",
            classifier=_classifier(),
            cfg=_cfg(fetch_splits=False),
        )


def test_build_context_attaches_splits_when_present(monkeypatch) -> None:
    summary = {
        "facts": {
            "execution_summary": {
                "plan_status": "executed",
                "planned": {"type": "tempo", "miles": 6.0},
                "actual": {"type": "tempo"},
            }
        }
    }
    splits_payload: Dict[str, Any] = {
        "splits_count": 2,
        "splits": [
            {"lap_index": 1, "avg_pace_display": "8:30/mi"},
            {"lap_index": 2, "avg_pace_display": "8:45/mi"},
        ],
        "splits_truncated": False,
    }
    _patch_tools(monkeypatch, summary=summary, splits=splits_payload)
    ctx = build_context(
        session=None,
        internal_user_id="u1",
        anchor_local_date="2026-05-14",
        classifier=_classifier(),
        cfg=_cfg(fetch_splits=True),
    )
    assert ctx.splits is not None
    assert ctx.splits_count == 2
    assert ctx.splits["splits"][0]["avg_pace_display"] == "8:30/mi"


def test_build_context_degrades_when_splits_tool_errors(monkeypatch) -> None:
    summary = {
        "facts": {
            "execution_summary": {
                "plan_status": "executed",
                "planned": {"type": "tempo", "miles": 6.0},
                "actual": {"type": "tempo"},
            }
        }
    }
    _patch_tools(monkeypatch, summary=summary, splits={"error": "unsupported"})
    ctx = build_context(
        session=None,
        internal_user_id="u1",
        anchor_local_date="2026-05-14",
        classifier=_classifier(),
        cfg=_cfg(fetch_splits=True),
    )
    assert ctx.splits is None
    # We must still produce a valid context so the responder can run.
    assert ctx.workout_intent.planned_type == "tempo"


def test_workout_intent_unplanned(monkeypatch) -> None:
    summary = {
        "facts": {
            "execution_summary": {
                "plan_status": "unplanned",
                "violated_rest_day": True,
                "planned": {"type": None, "miles": None},
                "actual": {"type": "easy"},
            }
        }
    }
    _patch_tools(monkeypatch, summary=summary)
    ctx = build_context(
        session=None,
        internal_user_id="u1",
        anchor_local_date="2026-05-14",
        classifier=_classifier(),
        cfg=_cfg(fetch_splits=False),
    )
    assert ctx.workout_intent.planned_type is None
    assert ctx.workout_intent.plan_status == "unplanned"
    assert ctx.workout_intent.violated_rest_day is True
    assert ctx.workout_intent.is_quality_session is False
    assert ctx.workout_intent.is_easy_or_long is False


def test_build_context_attaches_evidence_pack_when_enabled(monkeypatch) -> None:
    summary = {
        "facts": {
            "distance_display": "5.00 mi",
            "avg_pace_display": "9:30/mi",
            "avg_heart_rate_display": "132 bpm",
            "max_heart_rate_display": "143 bpm",
            "execution_summary": {
                "plan_status": "executed",
                "planned": {"type": "easy", "miles": 5.0},
                "actual": {"type": "easy"},
            },
        },
        "is_easy_run": True,
    }
    _patch_tools(monkeypatch, summary=summary)
    monkeypatch.setattr(
        cb_mod,
        "build_evidence_pack",
        lambda **_kw: (
            {
                "version": "run_review_evidence_pack_v1_easy",
                "similar_runs": {"rows": []},
            },
            {"present": True, "size_chars": 123},
        ),
    )
    cfg = _cfg(fetch_splits=False)
    cfg = RunReviewConfig(**{**cfg.__dict__, "evidence_pack_enabled": True})
    ctx = build_context(
        session=None,
        internal_user_id="u1",
        anchor_local_date="2026-05-14",
        classifier=_classifier(),
        cfg=cfg,
    )
    assert ctx.evidence_pack is not None
    assert ctx.evidence_pack_trace is not None
    assert ctx.evidence_pack_trace["present"] is True
