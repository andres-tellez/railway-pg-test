"""
Purpose:
- Feature/config helpers for CoachContext.

Responsibilities:
- Parse CoachContext feature flag with conservative defaults.

Non-goals:
- No snapshot assembly or telemetry logic.

Guardrails:
- Allowed imports/calls: `os` only.
- Must not import orchestrator or run-review modules.
"""

from __future__ import annotations

import os

_TRUE_VALUES = {"1", "true", "yes", "on", "y", "t", "enable", "enabled"}


def coach_context_v1_enabled() -> bool:
    """Feature flag gate for CoachContext Phase 1 wiring."""
    raw = (os.getenv("SMARTCOACH_COACH_CONTEXT_V1") or "").lstrip("\ufeff").strip()
    return raw.lower() in _TRUE_VALUES
