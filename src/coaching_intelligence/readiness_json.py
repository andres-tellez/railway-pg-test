"""JSON-safe helpers for readiness payloads."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def _json_safe_scalar(value: Any) -> Any:
    """Coerce date/datetime to ISO strings for API JSON payloads (readiness only)."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _json_safe_facts(value: Any) -> Any:
    """Recursively JSON-safe structures for category ``facts_used``."""
    if isinstance(value, dict):
        return {str(k): _json_safe_facts(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe_facts(v) for v in value]
    return _json_safe_scalar(value)
