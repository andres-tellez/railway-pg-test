"""
Feature flags and tunables for Run Review V2.

All env reads live here so the rest of the package never touches ``os.environ``
directly. Defaults are intentionally conservative:

- The main flag (``SMARTCOACH_RUN_REVIEW_V2``) is **off** unless explicitly set.
- Splits prefetch is **on** when V2 is on (the whole point of V2 is to look at
  the right evidence for quality sessions).
- The LLM intent router is **on** by default; flip to ``heuristic`` to disable
  the extra ``gpt-4o-mini`` classifier call.
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
    # Strip UTF-8 BOM / odd whitespace (some dashboards paste hidden chars).
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
        v = int(raw)
    except ValueError:
        return default
    return max(low, min(v, high))


def _read_str(env_name: str, default: str) -> str:
    raw = (os.getenv(env_name) or "").strip()
    return raw or default


@dataclass(frozen=True)
class RunReviewConfig:
    """Snapshot of run-review settings; read at every turn (cheap)."""

    enabled: bool
    classifier_mode: str  # "llm" | "heuristic"
    fetch_splits: bool
    include_comparisons: bool
    max_response_tokens: int
    classifier_max_tokens: int
    classifier_timeout_s: float
    responder_timeout_s: float
    responder_model_override: str  # empty string = use orchestrator default
    classifier_model: str
    evidence_pack_enabled: bool


def load_config() -> RunReviewConfig:
    """Read env once and freeze a config snapshot for the current turn."""
    return RunReviewConfig(
        enabled=_read_bool("SMARTCOACH_RUN_REVIEW_V2", False),
        classifier_mode=_read_str("SMARTCOACH_RUN_REVIEW_V2_CLASSIFIER", "llm").lower(),
        fetch_splits=_read_bool("SMARTCOACH_RUN_REVIEW_V2_FETCH_SPLITS", True),
        include_comparisons=_read_bool(
            "SMARTCOACH_RUN_REVIEW_V2_INCLUDE_COMPARISONS", False
        ),
        max_response_tokens=_read_int(
            "SMARTCOACH_RUN_REVIEW_V2_MAX_TOKENS", 800, 128, 2000
        ),
        classifier_max_tokens=_read_int(
            "SMARTCOACH_RUN_REVIEW_V2_CLASSIFIER_MAX_TOKENS", 200, 32, 600
        ),
        classifier_timeout_s=float(
            _read_int("SMARTCOACH_RUN_REVIEW_V2_CLASSIFIER_TIMEOUT_S", 6, 2, 30)
        ),
        responder_timeout_s=float(
            _read_int("SMARTCOACH_RUN_REVIEW_V2_RESPONDER_TIMEOUT_S", 45, 5, 120)
        ),
        responder_model_override=_read_str("SMARTCOACH_RUN_REVIEW_V2_MODEL", ""),
        classifier_model=_read_str(
            "SMARTCOACH_RUN_REVIEW_V2_CLASSIFIER_MODEL", "gpt-4o-mini"
        ),
        evidence_pack_enabled=_read_bool(
            "SMARTCOACH_RUN_REVIEW_EVIDENCE_PACK_V1", False
        ),
    )
