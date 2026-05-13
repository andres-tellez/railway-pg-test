"""Shared marathon / race clock string parsing and formatting (readiness, suggestions)."""

from __future__ import annotations

import re
from typing import Any, Optional


def parse_clock_seconds(value: Any) -> Optional[int]:
    raw = str(value or "").strip()
    if not raw:
        return None
    match = re.match(r"^\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*$", raw)
    if not match:
        return None
    try:
        if match.group(3) is not None:
            return (
                int(match.group(1)) * 3600
                + int(match.group(2)) * 60
                + int(match.group(3))
            )
        return int(match.group(1)) * 60 + int(match.group(2))
    except (TypeError, ValueError):
        return None


def format_clock_seconds(secs: int) -> str:
    secs = max(0, int(secs))
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
