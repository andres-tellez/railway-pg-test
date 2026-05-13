"""Readiness verdict shapes — lossless wrap of evaluate_plan_generation_readiness output."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

READINESS_VERDICT_SCHEMA = "readiness_verdict.v1"


@dataclass(frozen=True)
class ReadinessVerdictPayload:
    """Holds the full readiness API dict; enables roundtrip + future narrowing."""

    _payload: Dict[str, Any]

    @classmethod
    def from_api_dict(cls, d: Dict[str, Any]) -> "ReadinessVerdictPayload":
        return cls(_payload=dict(d))

    def to_api_dict(self) -> Dict[str, Any]:
        return dict(self._payload)
