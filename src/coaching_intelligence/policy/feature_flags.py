"""Feature toggles for coaching-intelligence readiness (env-driven, default off)."""

from __future__ import annotations

import os


def thin_pace_stretch_downgrade_enabled() -> bool:
    """STRETCH soften for competitive marathon + thin pace data + decent activity volume."""
    raw = (os.getenv("SMARTCOACH_THIN_PACE_STRETCH_DOWNGRADE") or "").strip()
    return raw in ("1", "true", "True")
