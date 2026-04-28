"""
Centralized **training invariants** — named policy constants for phase-scoped rules.

These values make implicit spine / validation rules **explicit**.
``PEAK_LONG_RUN_MIN_FRACTION_OF_PEAK_BLOCK_MAX`` is used by
``build_long_run_spine_weeks``; set ``SMARTCOACH_DEBUG_PEAK_LONG_RUN_FLOOR=1`` to
enable an optional ``assert`` there (see ``PEAK_LONG_RUN_FLOOR_DEBUG_ASSERT_ENABLED``).
Other symbols remain documentation / future hooks unless noted elsewhere.

**Convention**

- **Peak** long-run constraints must be expressed **relative to the Peak phase
  block** (e.g. max long run *within labeled Peak weeks*), not relative to a
  **global** pre-taper maximum that may occur in Base or Build.
- **Taper** intentionally allows large drops; Peak-style floors must not apply.
- **Build** (and **Base**) may include cutbacks and non-monotonic long-run weeks;
  those are normal progression mechanics, not errors by default.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Peak phase (calendar Peak block — last K pre-taper weeks in current spine policy)
# ---------------------------------------------------------------------------


def _env_truthy(name: str) -> bool:
    v = os.environ.get(name, "")
    return v.strip().lower() in ("1", "true", "yes", "on")


# Opt-in debug check in ``build_long_run_spine_weeks`` (off in production by default).
# Set ``SMARTCOACH_DEBUG_PEAK_LONG_RUN_FLOOR=1`` to enable.
PEAK_LONG_RUN_FLOOR_DEBUG_ASSERT_ENABLED: bool = _env_truthy(
    "SMARTCOACH_DEBUG_PEAK_LONG_RUN_FLOOR"
)

# When wired: minimum long run as a fraction of the **Peak block's own** maximum
# long run (computed only from weeks labeled Peak), never from global pre-taper max.
PEAK_LONG_RUN_MIN_FRACTION_OF_PEAK_BLOCK_MAX: float = 0.85

# Explicit policy flag for implementers: Peak floors must use block-local stats.
PEAK_LONG_RUN_FLOOR_RELATIVE_TO_PEAK_BLOCK_ONLY: bool = True

# Explicit anti-pattern guard (documentation + future asserts): do not key Peak
# floor off global pre-taper max long run.
PEAK_LONG_RUN_FORBID_GLOBAL_PRE_TAPER_MAX_FOR_FLOOR: bool = True

# ---------------------------------------------------------------------------
# Taper phase
# ---------------------------------------------------------------------------

# Taper may reduce long run sharply week-over-week; do not apply Peak endurance floors.
TAPER_LONG_RUN_ALLOWS_LARGE_DROPS: bool = True

# When wiring floors: skip any Peak-style minimum on Taper-labeled weeks.
TAPER_EXEMPT_FROM_PEAK_LONG_RUN_FLOOR: bool = True

# ---------------------------------------------------------------------------
# Build & Base phases
# ---------------------------------------------------------------------------

# Scheduled cutback weeks (long run below prior week) are allowed in Build/Base.
BUILD_AND_BASE_LONG_RUN_ALLOWS_CUTBACK_WEEKS: bool = True

# Long run in Build/Base may sit below a Peak-only endurance floor; do not clamp
# Build/Base to Peak block minima.
BUILD_AND_BASE_EXEMPT_FROM_PEAK_LONG_RUN_FLOOR: bool = True

__all__ = [
    "PEAK_LONG_RUN_FLOOR_DEBUG_ASSERT_ENABLED",
    "PEAK_LONG_RUN_MIN_FRACTION_OF_PEAK_BLOCK_MAX",
    "PEAK_LONG_RUN_FLOOR_RELATIVE_TO_PEAK_BLOCK_ONLY",
    "PEAK_LONG_RUN_FORBID_GLOBAL_PRE_TAPER_MAX_FOR_FLOOR",
    "TAPER_LONG_RUN_ALLOWS_LARGE_DROPS",
    "TAPER_EXEMPT_FROM_PEAK_LONG_RUN_FLOOR",
    "BUILD_AND_BASE_LONG_RUN_ALLOWS_CUTBACK_WEEKS",
    "BUILD_AND_BASE_EXEMPT_FROM_PEAK_LONG_RUN_FLOOR",
]
