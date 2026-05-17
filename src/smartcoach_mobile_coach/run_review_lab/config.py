"""
Feature flags and tunables for the minimal Run Review Lab path.

This path intentionally keeps prompt scaffolding very small so we can compare
LLM behavior against the production Run Review V2 contract.
"""

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
        val = int(raw)
    except ValueError:
        return default
    return max(low, min(val, high))


def _read_str(env_name: str, default: str) -> str:
    raw = (os.getenv(env_name) or "").strip()
    return raw or default


@dataclass(frozen=True)
class RunReviewLabConfig:
    """Snapshot of lab-mode settings."""

    enabled: bool
    max_response_tokens: int
    responder_timeout_s: float
    responder_model_override: str
    isolated_system_enabled: bool


def load_config() -> RunReviewLabConfig:
    return RunReviewLabConfig(
        enabled=_read_bool("SMARTCOACH_RUN_REVIEW_LAB", False),
        max_response_tokens=_read_int(
            "SMARTCOACH_RUN_REVIEW_LAB_MAX_TOKENS", 900, 128, 2200
        ),
        responder_timeout_s=float(
            _read_int("SMARTCOACH_RUN_REVIEW_LAB_RESPONDER_TIMEOUT_S", 45, 5, 120)
        ),
        responder_model_override=_read_str("SMARTCOACH_RUN_REVIEW_LAB_MODEL", ""),
        isolated_system_enabled=_read_bool(
            "SMARTCOACH_RUN_REVIEW_LAB_ISOLATED_SYSTEM", False
        ),
    )
