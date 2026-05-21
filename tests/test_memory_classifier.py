"""Memory module classifier tests (Phase 1)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pytest

from src.smartcoach_mobile_coach.memory.domain.observation import Observation
from src.smartcoach_mobile_coach.memory.domain.types import Provenance
from src.smartcoach_mobile_coach.memory.domain.vocab import (
    DurableType,
    MemoryKind,
    Source,
)
from src.smartcoach_mobile_coach.memory.policies.classifier import (
    LLMObservationClassifier,
)


def _observation(text: str) -> Observation:
    return Observation(
        user_id=uuid.uuid4(),
        text=text,
        provenance=Provenance(
            source=Source.USER_STATEMENT,
            captured_at=datetime.now(timezone.utc),
            conversation_id=None,
        ),
    )


def _fixture_json(name: str) -> Mapping[str, Any]:
    path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "memory_classifier"
        / f"{name}.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def test_classifier_uses_llm_payload_when_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeClient:
        def classify(self, *, text: str, user_id: str, timeout_s: float):
            assert "knee" in text.lower()
            assert user_id
            assert timeout_s == 1.5
            return _fixture_json("llm_durable_constraint")

    classifier = LLMObservationClassifier(llm_client=_FakeClient(), timeout_s=1.5)
    result = classifier.classify_with_metadata(
        _observation("Doctor said I should avoid speed work because of knee pain.")
    )
    assert result.used_fallback is False
    assert result.inferred_kind == MemoryKind.DURABLE
    assert result.observation.kind == MemoryKind.DURABLE
    assert result.observation.hints.get("durable_type") == DurableType.CONSTRAINT.value
    assert result.observation.hints.get("classifier_source") == "llm"
    assert result.classifier_cost == pytest.approx(0.00013)
    assert result.classifier_model == "gpt-4o-mini"


def test_classifier_falls_back_when_llm_throws() -> None:
    class _ThrowingClient:
        def classify(self, *, text: str, user_id: str, timeout_s: float):
            raise TimeoutError("simulated timeout")

    classifier = LLMObservationClassifier(llm_client=_ThrowingClient(), timeout_s=1.0)
    result = classifier.classify_with_metadata(
        _observation("I can only run 4 days per week for now.")
    )
    assert result.used_fallback is True
    assert result.reason == "llm_exception"
    assert result.observation.kind == MemoryKind.DURABLE
    assert (
        result.observation.hints.get("durable_type") == DurableType.TRAINING_DAYS.value
    )
    assert result.observation.hints.get("classifier_source") == "keyword_fallback"


def test_classifier_falls_back_when_payload_unusable() -> None:
    class _InvalidPayloadClient:
        def classify(self, *, text: str, user_id: str, timeout_s: float):
            return {"model": "gpt-4o-mini", "confidence": 0.4}

    classifier = LLMObservationClassifier(
        llm_client=_InvalidPayloadClient(), timeout_s=1.0
    )
    result = classifier.classify_with_metadata(_observation("I prefer morning runs."))
    assert result.used_fallback is True
    assert result.reason == "llm_unusable_payload"
    assert result.observation.hints.get("durable_type") == DurableType.PREFERENCE.value


def test_classifier_bypasses_llm_when_kind_already_set() -> None:
    class _CountingClient:
        def __init__(self) -> None:
            self.calls = 0

        def classify(self, *, text: str, user_id: str, timeout_s: float):
            self.calls += 1
            return {"memory_kind": "durable"}

    client = _CountingClient()
    classifier = LLMObservationClassifier(llm_client=client, timeout_s=1.0)
    obs = _observation("Whatever")
    obs = Observation(
        user_id=obs.user_id,
        text=obs.text,
        provenance=obs.provenance,
        kind=MemoryKind.DURABLE,
        hints=obs.hints,
    )
    result = classifier.classify_with_metadata(obs)
    assert result.reason == "kind_already_set"
    assert result.used_fallback is False
    assert client.calls == 0
