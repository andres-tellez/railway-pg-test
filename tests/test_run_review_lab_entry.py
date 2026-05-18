from __future__ import annotations

import src.smartcoach_mobile_coach.run_review_lab.entry as lab_entry
from src.smartcoach_mobile_coach.dialogue_manager import INTENT_SPLIT_DETAIL
from src.smartcoach_mobile_coach.run_review.classifier import ClassifierResult
from src.smartcoach_mobile_coach.run_review_lab.config import RunReviewLabConfig


def _lab_cfg(enabled: bool, *, splits_enabled: bool = True) -> RunReviewLabConfig:
    return RunReviewLabConfig(
        enabled=enabled,
        force_off=False,
        splits_enabled=splits_enabled,
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


def test_lab_gate_split_intent_when_classifier_declines(monkeypatch) -> None:
    fake = ClassifierResult(
        is_run_review=False,
        scope="other",
        confidence="low",
        reason_code="short_referential_ambiguous",
    )
    monkeypatch.setattr(lab_entry, "classify_user_message", lambda **kwargs: fake)
    use_lab, cls, _cfg = lab_entry.should_use_run_review_lab(
        user_message="What about mile 3?",
        conversation_history=[{"role": "assistant", "content": "Nice run."}],
        internal_user_id="u1",
        dialogue_intent=INTENT_SPLIT_DETAIL,
        cfg=_lab_cfg(True, splits_enabled=True),
    )
    assert use_lab is True
    assert cls is not None
    assert cls.scope == "splits_only"
    assert cls.reason_code == "split_detail_intent"
    assert cls.source == "dialogue_intent"


def test_lab_gate_split_intent_respects_splits_flag_off(monkeypatch) -> None:
    fake = ClassifierResult(
        is_run_review=False,
        scope="other",
        confidence="low",
        reason_code="short_referential_ambiguous",
    )
    monkeypatch.setattr(lab_entry, "classify_user_message", lambda **kwargs: fake)
    use_lab, cls, _cfg = lab_entry.should_use_run_review_lab(
        user_message="What about mile 3?",
        conversation_history=[],
        internal_user_id="u1",
        dialogue_intent=INTENT_SPLIT_DETAIL,
        cfg=_lab_cfg(True, splits_enabled=False),
    )
    assert use_lab is False
    assert cls is not None
    assert cls.is_run_review is False


def test_lab_gate_upgrades_scope_when_split_intent_and_classifier_single_run(
    monkeypatch,
) -> None:
    fake = ClassifierResult(
        is_run_review=True,
        scope="single_run",
        confidence="high",
        reason_code="review_phrase",
    )
    monkeypatch.setattr(lab_entry, "classify_user_message", lambda **kwargs: fake)
    use_lab, cls, _cfg = lab_entry.should_use_run_review_lab(
        user_message="How was my run?",
        conversation_history=[],
        internal_user_id="u1",
        dialogue_intent=INTENT_SPLIT_DETAIL,
        cfg=_lab_cfg(True),
    )
    assert use_lab is True
    assert cls is not None
    assert cls.scope == "splits_only"
    assert cls.reason_code.endswith("split_intent_scope")
