"""Feature flags and tunables for isolated coach response."""

from __future__ import annotations

import os
from dataclasses import dataclass

_TRUE_VALUES = (
    "1",
    "true",
    "yes",
    "on",
    "y",
    "enable",
    "enabled",
)
_FALSE_VALUES = ("0", "false", "no", "off", "n", "f", "disable", "disabled")


def _read_bool(env_name: str, default: bool) -> bool:
    raw = (os.getenv(env_name) or "").strip("\ufeff \t\r\n").lower()
    if raw in _TRUE_VALUES:
        return True
    if raw in _FALSE_VALUES:
        return False
    return default


def _read_int(env_name: str, default: int, low: int, high: int) -> int:
    raw = (os.getenv(env_name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(low, min(value, high))


def _read_str(env_name: str, default: str) -> str:
    raw = (os.getenv(env_name) or "").strip()
    return raw or default


@dataclass(frozen=True)
class CoachResponseConfig:
    enabled: bool
    classifier_mode: str
    fetch_splits: bool
    include_comparisons: bool
    max_response_tokens: int
    classifier_max_tokens: int
    classifier_timeout_s: float
    responder_timeout_s: float
    responder_model_override: str
    classifier_model: str
    evidence_pack_enabled: bool


def load_coach_response_config() -> CoachResponseConfig:
    return CoachResponseConfig(
        enabled=_read_bool("SMARTCOACH_COACH_RESPONSE_V1", True),
        classifier_mode=_read_str(
            "SMARTCOACH_COACH_RESPONSE_CLASSIFIER_MODE", "llm"
        ).lower(),
        fetch_splits=_read_bool("SMARTCOACH_COACH_RESPONSE_FETCH_SPLITS", True),
        include_comparisons=_read_bool(
            "SMARTCOACH_COACH_RESPONSE_INCLUDE_COMPARISONS", False
        ),
        max_response_tokens=_read_int(
            "SMARTCOACH_COACH_RESPONSE_MAX_TOKENS", 900, 128, 2200
        ),
        classifier_max_tokens=_read_int(
            "SMARTCOACH_COACH_RESPONSE_CLASSIFIER_MAX_TOKENS", 200, 32, 600
        ),
        classifier_timeout_s=float(
            _read_int("SMARTCOACH_COACH_RESPONSE_CLASSIFIER_TIMEOUT_S", 6, 2, 30)
        ),
        responder_timeout_s=float(
            _read_int("SMARTCOACH_COACH_RESPONSE_RESPONDER_TIMEOUT_S", 45, 5, 120)
        ),
        responder_model_override=_read_str("SMARTCOACH_COACH_RESPONSE_MODEL", ""),
        classifier_model=_read_str(
            "SMARTCOACH_COACH_RESPONSE_CLASSIFIER_MODEL", "gpt-4o-mini"
        ),
        evidence_pack_enabled=_read_bool(
            "SMARTCOACH_COACH_RESPONSE_EVIDENCE_PACK_V1", False
        ),
    )
