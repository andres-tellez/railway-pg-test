from __future__ import annotations

import src.smartcoach_mobile_coach.coach_response.entry as entry
from src.smartcoach_mobile_coach.coach_response.classifier import ClassifierResult
from src.smartcoach_mobile_coach.coach_response.config import CoachResponseConfig
from src.smartcoach_mobile_coach.dialogue_manager import INTENT_SPLIT_DETAIL


def _cfg(enabled: bool) -> CoachResponseConfig:
    return CoachResponseConfig(
        enabled=enabled,
        classifier_mode="heuristic",
        fetch_splits=True,
        include_comparisons=False,
        max_response_tokens=900,
        classifier_max_tokens=200,
        classifier_timeout_s=6.0,
        responder_timeout_s=45.0,
        responder_model_override="",
        classifier_model="gpt-4o-mini",
        evidence_pack_enabled=False,
    )


def test_gate_off_when_flag_disabled() -> None:
    use_coach_response, cls, cfg = entry.should_use_coach_response(
        user_message="How was my run?",
        conversation_history=[],
        internal_user_id="u1",
        cfg=_cfg(False),
    )
    assert use_coach_response is False
    assert cls is None
    assert cfg.enabled is False


def test_gate_uses_classifier_when_enabled(monkeypatch) -> None:
    fake = ClassifierResult(
        is_run_review=True,
        scope="single_run",
        confidence="high",
        day_hint="last_run",
        source="heuristic",
        reason_code="review_phrase",
    )
    monkeypatch.setattr(entry, "classify_user_message", lambda **kwargs: fake)
    use_coach_response, cls, cfg = entry.should_use_coach_response(
        user_message="How was my run?",
        conversation_history=[],
        internal_user_id="u1",
        cfg=_cfg(True),
    )
    assert use_coach_response is True
    assert cls is not None
    assert cls.reason_code == "review_phrase"
    assert cfg.enabled is True


def test_gate_split_intent_when_classifier_declines(monkeypatch) -> None:
    fake = ClassifierResult(
        is_run_review=False,
        scope="other",
        confidence="low",
        reason_code="short_referential_ambiguous",
    )
    monkeypatch.setattr(entry, "classify_user_message", lambda **kwargs: fake)
    use_coach_response, cls, _cfg_local = entry.should_use_coach_response(
        user_message="What about mile 3?",
        conversation_history=[{"role": "assistant", "content": "Nice run."}],
        internal_user_id="u1",
        dialogue_intent=INTENT_SPLIT_DETAIL,
        cfg=_cfg(True),
    )
    assert use_coach_response is True
    assert cls is not None
    assert cls.scope == "splits_only"
    assert cls.reason_code == "split_detail_intent"
    assert cls.source == "dialogue_intent"


def test_gate_upgrades_scope_when_split_intent(monkeypatch) -> None:
    fake = ClassifierResult(
        is_run_review=True,
        scope="single_run",
        confidence="high",
        reason_code="review_phrase",
    )
    monkeypatch.setattr(entry, "classify_user_message", lambda **kwargs: fake)
    use_coach_response, cls, _cfg_local = entry.should_use_coach_response(
        user_message="How was my run?",
        conversation_history=[],
        internal_user_id="u1",
        dialogue_intent=INTENT_SPLIT_DETAIL,
        cfg=_cfg(True),
    )
    assert use_coach_response is True
    assert cls is not None
    assert cls.scope == "splits_only"
    assert cls.reason_code.endswith("split_intent_scope")
