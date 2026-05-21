"""
Purpose:
- Implement LLM-assisted observation classification with keyword fallback.

Responsibilities:
- Classify free-text observations into memory kinds and durable subtypes.
- Apply timeout-safe fallback behavior when LLM classification is unavailable.
- Emit per-call classifier telemetry including fallback outcome and cost hints.

Non-goals:
- No persistence writes.
- No direct OpenAI imports (network client injected through protocol).

Guardrails:
- Allowed imports/calls: typing/dataclasses/stdlib + memory domain + telemetry.
- Must keep network dependencies injected behind protocols.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Any, Mapping, Protocol

from src.smartcoach_mobile_coach.memory.domain.observation import Observation
from src.smartcoach_mobile_coach.memory.domain.vocab import DurableType, MemoryKind
from src.smartcoach_mobile_coach.memory.telemetry import (
    EVENT_MEMORY_CLASSIFIER,
    log_memory_event,
)


class ClassifierClient(Protocol):
    def classify(
        self, *, text: str, user_id: str, timeout_s: float
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class ClassifierResult:
    observation: Observation
    used_fallback: bool
    reason: str | None = None
    inferred_kind: MemoryKind | None = None
    classifier_cost: float | None = None
    classifier_model: str | None = None


class LLMObservationClassifier:
    """
    LLM-assisted classifier with keyword fallback.

    Phase 1 skeleton only; behavior implementation lands in subsequent commits.
    """

    def __init__(
        self,
        *,
        llm_client: ClassifierClient,
        timeout_s: float,
        llm_enabled: bool = True,
    ) -> None:
        self._llm_client = llm_client
        self._timeout_s = timeout_s
        self._llm_enabled = llm_enabled

    def classify(self, obs: Observation) -> Observation:
        """Return an observation potentially enriched with inferred kind hints."""
        return self.classify_with_metadata(obs).observation

    def classify_with_metadata(self, obs: Observation) -> ClassifierResult:
        """Return classified observation and fallback metadata."""
        if obs.kind is not None:
            result = ClassifierResult(
                observation=obs,
                used_fallback=False,
                reason="kind_already_set",
                inferred_kind=obs.kind,
            )
            self._log(result)
            return result

        text = (obs.text or "").strip()
        if not text:
            result = ClassifierResult(
                observation=obs,
                used_fallback=True,
                reason="empty_text",
                inferred_kind=None,
            )
            self._log(result)
            return result

        if not self._llm_enabled:
            result = self._fallback(obs, reason="llm_disabled")
            self._log(result)
            return result

        try:
            payload = self._llm_client.classify(
                text=text, user_id=str(obs.user_id), timeout_s=self._timeout_s
            )
        except Exception:
            result = self._fallback(obs, reason="llm_exception")
            self._log(result)
            return result

        llm_applied = self._from_llm_payload(obs, payload)
        if llm_applied is None:
            result = self._fallback(
                obs,
                reason="llm_unusable_payload",
                payload=payload,
            )
            self._log(result)
            return result

        result = ClassifierResult(
            observation=llm_applied,
            used_fallback=False,
            reason=None,
            inferred_kind=llm_applied.kind,
            classifier_cost=_coerce_float(payload.get("cost")),
            classifier_model=_coerce_str(payload.get("model")),
        )
        self._log(result)
        return result

    def _log(self, result: ClassifierResult) -> None:
        hints = result.observation.hints
        payload = {
            "used_fallback": result.used_fallback,
            "reason": result.reason,
            "inferred_kind": (
                str(result.inferred_kind) if result.inferred_kind else None
            ),
            "durable_type": hints.get("durable_type"),
            "classifier_source": hints.get("classifier_source"),
            "classifier_confidence": hints.get("classifier_confidence"),
            "cost": result.classifier_cost,
            "model": result.classifier_model,
        }
        log_memory_event(EVENT_MEMORY_CLASSIFIER, payload)

    def _fallback(
        self,
        obs: Observation,
        *,
        reason: str,
        payload: Mapping[str, Any] | None = None,
    ) -> ClassifierResult:
        durable_type = infer_durable_type_keyword(obs.text)
        updated = _apply_classification(
            obs=obs,
            kind=MemoryKind.DURABLE,
            durable_type=durable_type,
            source="keyword_fallback",
            confidence=0.6,
        )
        return ClassifierResult(
            observation=updated,
            used_fallback=True,
            reason=reason,
            inferred_kind=updated.kind,
            classifier_cost=(
                _coerce_float(payload.get("cost"))
                if isinstance(payload, Mapping)
                else None
            ),
            classifier_model=(
                _coerce_str(payload.get("model"))
                if isinstance(payload, Mapping)
                else None
            ),
        )

    def _from_llm_payload(
        self, obs: Observation, payload: Mapping[str, Any]
    ) -> Observation | None:
        raw_kind = _coerce_str(payload.get("memory_kind")) or _coerce_str(
            payload.get("kind")
        )
        if raw_kind is None:
            return None
        kind = _parse_memory_kind(raw_kind)
        if kind is None:
            return None
        durable_type = _parse_durable_type(_coerce_str(payload.get("durable_type")))
        confidence = _coerce_float(payload.get("confidence"))
        source = "llm"
        if kind == MemoryKind.DURABLE and durable_type is None:
            durable_type = infer_durable_type_keyword(obs.text)
            source = "llm_plus_keyword_default"
        return _apply_classification(
            obs=obs,
            kind=kind,
            durable_type=durable_type,
            source=source,
            confidence=confidence if confidence is not None else 0.7,
        )


def _apply_classification(
    *,
    obs: Observation,
    kind: MemoryKind,
    durable_type: DurableType | None,
    source: str,
    confidence: float,
) -> Observation:
    hints = dict(obs.hints)
    hints["classifier_source"] = source
    hints["classifier_confidence"] = round(max(0.0, min(1.0, confidence)), 3)
    if durable_type is not None:
        hints["durable_type"] = durable_type.value
    hints["inferred_kind"] = kind.value
    return replace(obs, kind=kind, hints=hints)


def _parse_memory_kind(raw: str) -> MemoryKind | None:
    value = raw.strip().lower()
    if value in ("durable", "state", "open_thread", "interaction", "summary"):
        return MemoryKind(value)
    return None


def _parse_durable_type(raw: str | None) -> DurableType | None:
    if raw is None:
        return None
    value = raw.strip().lower()
    if value in (
        "goal",
        "constraint",
        "preference",
        "training_days",
        "long_run_day",
        "other",
    ):
        return DurableType(value)
    return None


def _coerce_str(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    value = raw.strip()
    return value or None


def _coerce_float(raw: Any) -> float | None:
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        try:
            return float(raw.strip())
        except ValueError:
            return None
    return None


_WEEKDAY_WORDS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "mon",
    "tue",
    "wed",
    "thu",
    "fri",
    "sat",
    "sun",
)


def infer_durable_type_keyword(text: str) -> DurableType:
    """Keyword-only durable subtype fallback. Deterministic and cheap."""
    l = (text or "").lower()
    if re.search(
        r"\b(injur|doctor|physio|must avoid|cannot run|can't run|never run|"
        r"no doubles|no back-to-back|limited to|only able to|do not run|"
        r"avoid running|not allowed to run)\b",
        l,
    ):
        return DurableType.CONSTRAINT
    if "can't" in l or "cannot " in l or "must not" in l:
        return DurableType.CONSTRAINT
    if re.search(
        r"\b(\d+)\s*(day|days|time|times)\s*(per week|each week|a week)\b", l
    ) or re.search(r"\bonly run\s+\d\b", l):
        return DurableType.TRAINING_DAYS
    if "days per week" in l or "train only" in l or "run only" in l:
        return DurableType.TRAINING_DAYS
    if ("long run" in l or "long-run" in l or "longrun" in l) and any(
        w in l for w in _WEEKDAY_WORDS
    ):
        return DurableType.LONG_RUN_DAY
    if re.search(
        r"\b(goal|target|aim|sub-\d|boston|qualify|marathon|half marathon)\b", l
    ):
        return DurableType.GOAL
    if re.search(
        r"\b(prefer|rather|like to|i'd like|morning|evening|schedule|work|travel)\b",
        l,
    ):
        return DurableType.PREFERENCE
    return DurableType.OTHER
