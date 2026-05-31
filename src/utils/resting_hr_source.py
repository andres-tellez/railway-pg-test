"""Resting HR source resolution for profile save."""

from __future__ import annotations

from typing import Any, Optional

from src.utils.hr_zone_constants import ALLOWED_RESTING_HR_WRITE_SOURCES


def _normalize_source(value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    return normalized or None


def requested_resting_hr_source(raw_body: dict[str, Any]) -> Optional[str]:
    """Read resting HR source from request body (camelCase or snake_case)."""
    for key in ("restingHrSource", "resting_hr_source"):
        if key in raw_body:
            return _normalize_source(raw_body.get(key))
    return None


def resolve_resting_hr_source_for_save(
    *,
    raw_body: dict[str, Any],
    requested_source: Optional[str],
    new_resting_hr: Optional[int],
) -> Optional[str]:
    """
    Resolve source when this request explicitly saves resting HR.

    Returns USER, APPLE_HEALTH, or None when resting HR is not being saved.
    Invalid or unsupported values default to USER (never ESTIMATED).
    APPLE_HEALTH is only returned when explicitly requested with a resting HR value.
    """
    explicit_resting_hr = "restingHr" in raw_body or "resting_hr" in raw_body
    if not explicit_resting_hr or new_resting_hr is None:
        return None

    source = requested_source or requested_resting_hr_source(raw_body)
    if source == "APPLE_HEALTH" and source in ALLOWED_RESTING_HR_WRITE_SOURCES:
        return "APPLE_HEALTH"
    return "USER"
