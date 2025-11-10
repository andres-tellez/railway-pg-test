from __future__ import annotations

from typing import Any, Dict, Optional

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
