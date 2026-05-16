"""Tests for the run-review V2 entry gate + end-to-end happy path."""

# pylint: disable=missing-function-docstring

from __future__ import annotations

from typing import Any, Dict, List

import pytest

import src.smartcoach_mobile_coach.run_review.entry as entry_mod
from src.smartcoach_mobile_coach.run_review import (
    handle_run_review_turn,
    should_use_run_review_v2,
)
from src.smartcoach_mobile_coach.run_review.classifier import ClassifierResult
from src.smartcoach_mobile_coach.run_review.config import RunReviewConfig
from src.smartcoach_mobile_coach.run_review.context import (
    RunReviewContext,
    WorkoutIntent,
)
from src.smartcoach_mobile_coach.run_review.errors import RunReviewFallback
from src.smartcoach_mobile_coach.run_review.responder import ResponderOutput


def _cfg(enabled: bool, classifier_mode: str = "heuristic") -> RunReviewConfig:
    return RunReviewConfig(
        enabled=enabled,
        classifier_mode=classifier_mode,
        fetch_splits=True,
        include_comparisons=False,
        max_response_tokens=800,
        classifier_max_tokens=200,
        classifier_timeout_s=6.0,
        responder_timeout_s=30.0,
        responder_model_override="",
        classifier_model="gpt-4o-mini",
    )


@pytest.fixture(autouse=True)
def _disable_coach_context_flag(monkeypatch):
    monkeypatch.delenv("SMARTCOACH_COACH_CONTEXT_V1", raising=False)


def test_gate_off_when_flag_disabled(monkeypatch) -> None:
    monkeypatch.setattr(entry_mod, "load_config", lambda: _cfg(False))
    use_v2, _, _ = should_use_run_review_v2(
        user_message="How was my run?",
        conversation_history=[],
        internal_user_id="u1",
    )
    assert use_v2 is False


def test_gate_allows_run_review_during_plan_creation_mode(monkeypatch) -> None:
    """Intake threads force plan_creation_mode=True; explicit run reviews still use V2."""
    monkeypatch.setattr(entry_mod, "load_config", lambda: _cfg(True))
    use_v2, classifier_result, _ = should_use_run_review_v2(
        user_message="How was my run?",
        conversation_history=[],
        internal_user_id="u1",
    )
    assert use_v2 is True
    assert classifier_result is not None
    assert classifier_result.is_run_review is True


def test_gate_off_for_intake_style_answer_during_plan_creation_mode(
    monkeypatch,
) -> None:
    monkeypatch.setattr(entry_mod, "load_config", lambda: _cfg(True))
    use_v2, _, _ = should_use_run_review_v2(
        user_message="4",
        conversation_history=[],
        internal_user_id="u1",
    )
    assert use_v2 is False


def test_gate_on_for_classic_recap_question(monkeypatch) -> None:
    monkeypatch.setattr(entry_mod, "load_config", lambda: _cfg(True))
    use_v2, classifier_result, cfg = should_use_run_review_v2(
        user_message="How was my run today?",
        conversation_history=[],
        internal_user_id="u1",
    )
    assert use_v2 is True
    assert cfg.enabled is True
    assert classifier_result is not None
    assert classifier_result.is_run_review is True


def test_gate_off_for_plan_question(monkeypatch) -> None:
    monkeypatch.setattr(entry_mod, "load_config", lambda: _cfg(True))
    use_v2, classifier_result, _ = should_use_run_review_v2(
        user_message="Help me build a training plan",
        conversation_history=[],
        internal_user_id="u1",
    )
    assert use_v2 is False
    assert classifier_result is not None
    assert classifier_result.is_run_review is False


def _stub_ctx() -> RunReviewContext:
    return RunReviewContext(
        activity_id=9001,
        anchor_local_date="2026-05-14",
        facts={
            "title": "Run",
            "execution_summary": {
                "plan_status": "executed",
                "planned": {"type": "tempo", "miles": 6.0},
                "actual": {"type": "tempo"},
            },
        },
        training_kpis={"hr_drift_band": "yellow"},
        workout_intent=WorkoutIntent(
            planned_type="tempo",
            planned_miles=6.0,
            plan_status="executed",
        ),
        resolved_via="find_runs_by_date",
        scope="single_run",
    )


def test_handle_run_review_turn_happy_path(monkeypatch) -> None:
    cfg = _cfg(True)
    monkeypatch.setattr(entry_mod, "load_config", lambda: cfg)
    monkeypatch.setattr(entry_mod, "build_context", lambda **_kw: _stub_ctx())

    captured: Dict[str, Any] = {}

    def _fake_generate(**kw):
        captured.update(kw)
        return ResponderOutput(
            content="This was a productive tempo. Strong middle miles.",
            usage={"prompt_tokens": 100, "completion_tokens": 30, "total_tokens": 130},
            cost=0.01,
            model="gpt-4o",
            timings_ms={"run_review_v2_llm_ms": 250.0},
            retried_on_empty=False,
        )

    monkeypatch.setattr(entry_mod, "generate_review", _fake_generate)

    payload, meta = handle_run_review_turn(
        session=None,
        internal_user_id="u1",
        user_message="How was my run today?",
        conversation_history=[],
        anchor_local_date="2026-05-14",
        base_system_content="BASE SYSTEM",
        history_window=10,
        model="gpt-4o",
        temperature=0.5,
        max_tokens=800,
        response_directive_dialogue={"intent": "run_analysis"},
        activity_id_hint=None,
        thread_activity_id=None,
        cfg=cfg,
        classifier_result=ClassifierResult(
            is_run_review=True,
            scope="single_run",
            confidence="high",
            source="heuristic",
            reason_code="review_phrase",
        ),
    )

    # Envelope shape matches the legacy run_summary contract.
    assert payload["type"] == "run_summary"
    assert payload["content"].startswith("This was a productive tempo")
    assert "facts" in payload["data"]
    # Meta carries V2 markers + classifier summary.
    assert meta["run_review_v2"] is True
    assert meta["run_review_v2_scope"] == "single_run"
    assert meta["run_review_v2_classifier"]["is_run_review"] is True
    assert meta["model"] == "gpt-4o"
    assert meta["usage"]["total_tokens"] == 130
    assert meta["rubric_version"] == "run_review_rubric_v1"
    # The responder must have received the augmented system content.
    assert captured["base_system_content"] == "BASE SYSTEM"
    assert captured["ctx"].activity_id == 9001


def test_handle_run_review_turn_bubbles_fallback(monkeypatch) -> None:
    cfg = _cfg(True)
    monkeypatch.setattr(entry_mod, "load_config", lambda: cfg)

    def _boom(**_kw):
        raise RunReviewFallback("no_runs_on_anchor_date")

    monkeypatch.setattr(entry_mod, "build_context", _boom)

    with pytest.raises(RunReviewFallback):
        handle_run_review_turn(
            session=None,
            internal_user_id="u1",
            user_message="How was my run today?",
            conversation_history=[],
            anchor_local_date="2026-05-14",
            base_system_content="BASE",
            history_window=10,
            model="gpt-4o",
            temperature=0.5,
            max_tokens=800,
            response_directive_dialogue={},
            cfg=cfg,
            classifier_result=ClassifierResult(
                is_run_review=True,
                scope="single_run",
                confidence="high",
                source="heuristic",
                reason_code="review_phrase",
            ),
        )


def test_handle_run_review_turn_disabled_raises(monkeypatch) -> None:
    cfg = _cfg(False)
    monkeypatch.setattr(entry_mod, "load_config", lambda: cfg)
    with pytest.raises(RunReviewFallback):
        handle_run_review_turn(
            session=None,
            internal_user_id="u1",
            user_message="How was my run today?",
            conversation_history=[],
            anchor_local_date="2026-05-14",
            base_system_content="BASE",
            history_window=10,
            model="gpt-4o",
            temperature=0.5,
            max_tokens=800,
            response_directive_dialogue={},
            cfg=cfg,
        )
