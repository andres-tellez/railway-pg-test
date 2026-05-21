"""
Purpose:
- Structured observability contract for Memory module.

Responsibilities:
- Define stable event names and typed payload keys.
- Provide a single logger entry point.

Non-goals:
- No analytics pipeline ownership.
- No persistence of telemetry events.

Guardrails:
- Allowed imports/calls: stdlib logging + typing only.
- Must not import orchestrator or adapter modules.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger("smartcoach_mobile_coach")

EVENT_MEMORY_RECORD = "memory.record"
EVENT_MEMORY_VIEW_BUILT = "memory.view_built"
EVENT_MEMORY_CLASSIFIER = "memory.classifier"


def log_memory_event(event_name: str, payload: Dict[str, Any]) -> None:
    """Emit a compact structured memory event line."""
    logger.info("[memory] event=%s payload=%s", event_name, payload)
