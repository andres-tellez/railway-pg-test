from __future__ import annotations

from datetime import datetime, date
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = "UTC"


def resolve_timezone(plan_request: Optional[Dict[str, Any]]) -> str:
    """
    Resolve the timezone to use for plan generation.

    Args:
        plan_request: Plan request payload containing optional timezone info.

    Returns:
        IANA timezone string, defaulting to UTC when not provided.
    """

    if not plan_request:
        return DEFAULT_TIMEZONE

    tz = plan_request.get("user_timezone")
    if isinstance(tz, str) and tz.strip():
        return tz.strip()

    return DEFAULT_TIMEZONE


def get_today_date_in_timezone(iana_tz: Optional[str]) -> date:
    """
    Calendar "today" in the given IANA timezone.

    Used for week-boundary calculations (e.g. Monday of the athlete's current week)
    independent of the server's local date.

    Args:
        iana_tz: IANA timezone name (e.g. "America/New_York"). Empty/None -> UTC.

    Returns:
        The current date in that timezone (falls back to UTC on unknown names).
    """
    tz_name = (iana_tz or "").strip() or DEFAULT_TIMEZONE
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo(DEFAULT_TIMEZONE)
    return datetime.now(tz).date()
