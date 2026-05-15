"""
Purpose:
- Structured observability for CoachContext snapshot builds.

Responsibilities:
- Build trace payload for response metadata.
- Emit concise build logs.

Non-goals:
- No analytics/event pipeline writes.
- No data fetching.

Guardrails:
- Allowed imports/calls: stdlib + project logger.
- Must not import orchestrator.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger("smartcoach_mobile_coach")


def build_trace(
    *,
    built: bool,
    enabled: bool,
    size_chars: int,
    slices_included: List[str],
    slices_omitted: List[str],
    fields_omitted_due_to_budget: List[str],
    field_sources: Dict[str, str],
    opening_turn: bool,
) -> Dict[str, Any]:
    """Compose response-safe trace metadata."""
    flags = {
        "active_plan": "plan" in slices_included,
        "hr_zones_present": "athlete.zones_compact" in field_sources,
        "trends_present": "trends" in slices_included,
        "memory_present": "memory" in slices_included,
        "opening_turn": opening_turn,
    }
    return {
        "built": built,
        "enabled": enabled,
        "schema_version": 1,
        "size_chars": size_chars,
        "slices_included": slices_included,
        "slices_omitted": slices_omitted,
        "fields_omitted_due_to_budget": fields_omitted_due_to_budget,
        "field_sources": field_sources,
        "flags": flags,
    }


def log_built(trace: Dict[str, Any]) -> None:
    """Emit a compact structured log line for CoachContext status."""
    flags = trace.get("flags") or {}
    logger.info(
        "[coach_context] built=%s enabled=%s size_chars=%s active_plan=%s "
        "hr_zones=%s trends=%s memory=%s omitted=%s",
        bool(trace.get("built")),
        bool(trace.get("enabled")),
        int(trace.get("size_chars") or 0),
        int(bool(flags.get("active_plan"))),
        int(bool(flags.get("hr_zones_present"))),
        int(bool(flags.get("trends_present"))),
        int(bool(flags.get("memory_present"))),
        ",".join(trace.get("fields_omitted_due_to_budget") or []),
    )
