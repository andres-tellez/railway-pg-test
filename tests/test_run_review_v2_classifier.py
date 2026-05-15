"""Unit tests for the Run Review V2 classifier.

These exercise the **deterministic** path only — no LLM is called.
The LLM-router branch is covered separately by the entry test that
patches the OpenAI service.
"""

# pylint: disable=missing-function-docstring,missing-class-docstring

from __future__ import annotations

from src.smartcoach_mobile_coach.run_review.classifier import (
    ClassifierResult,
    _heuristic_classify,
    classify_user_message,
)
from src.smartcoach_mobile_coach.run_review.config import RunReviewConfig


def _cfg(classifier_mode: str = "heuristic") -> RunReviewConfig:
    return RunReviewConfig(
        enabled=True,
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


def test_heuristic_obvious_run_review_phrases() -> None:
    msg = "How was my run today?"
    r = _heuristic_classify(msg)
    assert r.is_run_review is True
    assert r.scope == "single_run"
    assert r.confidence == "high"
    assert r.day_hint == "today"
    assert r.reason_code == "review_phrase"


def test_heuristic_run_review_phrase_beats_this_week_hint() -> None:
    """Broad weekly hints must not suppress explicit run-review wording."""
    r = _heuristic_classify("How was my run this week?")
    assert r.is_run_review is True
    assert r.reason_code == "review_phrase"


def test_heuristic_split_only_phrase() -> None:
    r = _heuristic_classify("Can you look at my splits from yesterday?")
    assert r.is_run_review is True
    assert r.scope == "splits_only"
    assert r.confidence == "high"
    assert r.day_hint == "yesterday"


def test_heuristic_paraphrase_was_that_too_hard() -> None:
    r = _heuristic_classify("Was that too hard for a tempo?")
    assert r.is_run_review is True


def test_heuristic_plan_request_is_not_review() -> None:
    r = _heuristic_classify("Help me build a plan for a marathon.")
    assert r.is_run_review is False
    assert r.scope == "other"
    assert r.confidence == "high"
    assert r.reason_code == "non_review_hint"


def test_heuristic_metric_explainer_is_not_review() -> None:
    r = _heuristic_classify("What is Z2?")
    assert r.is_run_review is False
    assert r.confidence == "high"
    assert r.reason_code == "non_review_hint"


def test_heuristic_empty_returns_not_review() -> None:
    r = _heuristic_classify("")
    assert r.is_run_review is False
    assert r.reason_code == "empty_message"


def test_classify_user_message_skips_llm_on_high_confidence_yes(monkeypatch) -> None:
    calls = []

    def _fake_llm(*args, **kwargs):
        calls.append(1)
        raise AssertionError("should not be called on high-confidence heuristic yes")

    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.run_review.classifier._llm_classify", _fake_llm
    )
    r = classify_user_message(
        user_message="How was my run today?",
        conversation_history=[],
        internal_user_id="u1",
        cfg=_cfg("llm"),
    )
    assert r.is_run_review is True
    assert r.source == "heuristic"
    assert calls == []


def test_classify_user_message_skips_llm_on_high_confidence_no(monkeypatch) -> None:
    def _fake_llm(*args, **kwargs):
        raise AssertionError("should not be called on high-confidence heuristic no")

    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.run_review.classifier._llm_classify", _fake_llm
    )
    r = classify_user_message(
        user_message="Help me build a plan",
        conversation_history=[],
        internal_user_id="u1",
        cfg=_cfg("llm"),
    )
    assert r.is_run_review is False


def test_classify_user_message_falls_back_when_llm_returns_none(monkeypatch) -> None:
    def _fake_llm(**kwargs):
        return None

    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.run_review.classifier._llm_classify", _fake_llm
    )
    r = classify_user_message(
        user_message="was that ok?",  # short referential, low confidence
        conversation_history=[],
        internal_user_id="u1",
        cfg=_cfg("llm"),
    )
    assert r.source == "llm_fallback"
    # Don't assert is_run_review here — the heuristic decides, we only
    # care that fallback path is used and we return cleanly.


def test_classify_user_message_respects_llm_decision(monkeypatch) -> None:
    fake = ClassifierResult(
        is_run_review=True,
        scope="single_run",
        confidence="medium",
        day_hint="last_run",
        source="llm",
        reason_code="llm_classified",
    )
    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.run_review.classifier._llm_classify",
        lambda **kwargs: fake,
    )
    r = classify_user_message(
        user_message="any thoughts on my latest one",  # ambiguous
        conversation_history=[],
        internal_user_id="u1",
        cfg=_cfg("llm"),
    )
    assert r.is_run_review is True
    assert r.source == "llm"
    assert r.day_hint == "last_run"


def test_classify_user_message_heuristic_mode_never_calls_llm(monkeypatch) -> None:
    def _fake_llm(**kwargs):
        raise AssertionError("LLM router should not run in heuristic mode")

    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.run_review.classifier._llm_classify", _fake_llm
    )
    r = classify_user_message(
        user_message="hmm not sure about that one",
        conversation_history=[],
        internal_user_id="u1",
        cfg=_cfg("heuristic"),
    )
    assert r.source == "heuristic"
