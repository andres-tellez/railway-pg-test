from __future__ import annotations

import src.smartcoach_mobile_coach.run_review_lab.entry as lab_entry
from src.smartcoach_mobile_coach.run_review.classifier import ClassifierResult
from src.smartcoach_mobile_coach.run_review_lab.config import RunReviewLabConfig


def _lab_cfg(enabled: bool) -> RunReviewLabConfig:
    return RunReviewLabConfig(
        enabled=enabled,
        max_response_tokens=900,
        responder_timeout_s=45.0,
        responder_model_override="",
        isolated_system_enabled=False,
    )


def test_lab_gate_off_when_flag_disabled() -> None:
    use_lab, cls, cfg = lab_entry.should_use_run_review_lab(
        user_message="How was my run?",
        conversation_history=[],
        internal_user_id="u1",
        cfg=_lab_cfg(False),
    )
    assert use_lab is False
    assert cls is None
    assert cfg.enabled is False


def test_lab_gate_uses_classifier_when_enabled(monkeypatch) -> None:
    fake = ClassifierResult(
        is_run_review=True,
        scope="single_run",
        confidence="high",
        day_hint="last_run",
        source="heuristic",
        reason_code="review_phrase",
    )
    monkeypatch.setattr(lab_entry, "classify_user_message", lambda **kwargs: fake)
    use_lab, cls, cfg = lab_entry.should_use_run_review_lab(
        user_message="How was my run?",
        conversation_history=[],
        internal_user_id="u1",
        cfg=_lab_cfg(True),
    )
    assert use_lab is True
    assert cls is not None
    assert cls.reason_code == "review_phrase"
    assert cfg.enabled is True
