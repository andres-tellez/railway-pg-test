"""
Purpose:
- Feature/config helpers for Memory module.

Responsibilities:
- Parse feature flags with conservative defaults.
- Expose a typed immutable configuration snapshot.

Non-goals:
- No service wiring.
- No orchestration or persistence logic.

Guardrails:
- Allowed imports/calls: `os`, dataclasses, typing.
- Must not import orchestrator or adapter modules.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

_TRUE_VALUES = {"1", "true", "yes", "on", "y", "t", "enable", "enabled"}


def _read_bool(env_name: str, default: bool) -> bool:
    raw = (os.getenv(env_name) or "").lstrip("\ufeff").strip()
    if not raw:
        return default
    return raw.lower() in _TRUE_VALUES


@dataclass(frozen=True)
class MemoryConfig:
    """Configuration snapshot for Memory module behavior."""

    classifier_enabled: bool
    classifier_timeout_s: float
    summary_writer_enabled: bool


def load_memory_config() -> MemoryConfig:
    """
    Return a conservative config snapshot.
    """
    timeout_raw = (os.getenv("SMARTCOACH_MEMORY_CLASSIFIER_TIMEOUT_S") or "").strip()
    try:
        timeout_s = float(timeout_raw) if timeout_raw else 1.5
    except ValueError:
        timeout_s = 1.5

    return MemoryConfig(
        classifier_enabled=_read_bool("SMARTCOACH_MEMORY_V2_LLM_CLASSIFIER", True),
        classifier_timeout_s=max(0.1, timeout_s),
        summary_writer_enabled=_read_bool(
            "SMARTCOACH_SESSION_SUMMARY_WRITER_ENABLED", False
        ),
    )
