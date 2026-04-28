"""
Centralized **training invariants** — named policy constants for phase-scoped rules.

These values make implicit spine / validation rules **explicit**.
``build_long_run_spine_weeks`` uses ``PEAK_LONG_RUN_MIN_FRACTION_OF_GLOBAL_PRE_TAPER_MAX``
for calendar Peak weeks (band vs **G** = global pre-taper max long run).
``PEAK_LONG_RUN_MIN_FRACTION_OF_PEAK_BLOCK_MAX`` is a deprecated alias of that
constant (backward compatibility only). Set ``SMARTCOACH_DEBUG_PEAK_LONG_RUN_FLOOR=1`` to enable
an optional ``assert`` in the spine (see ``PEAK_LONG_RUN_FLOOR_DEBUG_ASSERT_ENABLED``).

**Convention**

- **Peak** (calendar last **K** weeks before taper): long runs are held in
  ``[PEAK_LONG_RUN_MIN_FRACTION_OF_GLOBAL_PRE_TAPER_MAX * G, G]`` where **G** is the
  max long run over all pre-taper weeks.
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

# Minimum long run in calendar Peak weeks as a fraction of **G** (max long run
# over all pre-taper weeks). Used by ``build_long_run_spine_weeks``.
PEAK_LONG_RUN_MIN_FRACTION_OF_GLOBAL_PRE_TAPER_MAX: float = 0.85

# DEPRECATED: Use PEAK_LONG_RUN_MIN_FRACTION_OF_GLOBAL_PRE_TAPER_MAX instead.
# This alias exists for backward compatibility and will be removed in a future release.
PEAK_LONG_RUN_MIN_FRACTION_OF_PEAK_BLOCK_MAX: float = (
    PEAK_LONG_RUN_MIN_FRACTION_OF_GLOBAL_PRE_TAPER_MAX
)

# Explicit policy flag (historical): Peak band in production uses global G.
PEAK_LONG_RUN_FLOOR_RELATIVE_TO_PEAK_BLOCK_ONLY: bool = False

# Peak long-run floor may reference global pre-taper max (G) for calendar Peak weeks.
PEAK_LONG_RUN_FORBID_GLOBAL_PRE_TAPER_MAX_FOR_FLOOR: bool = False

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
    "PEAK_LONG_RUN_MIN_FRACTION_OF_GLOBAL_PRE_TAPER_MAX",
    "PEAK_LONG_RUN_MIN_FRACTION_OF_PEAK_BLOCK_MAX",
    "PEAK_LONG_RUN_FLOOR_RELATIVE_TO_PEAK_BLOCK_ONLY",
    "PEAK_LONG_RUN_FORBID_GLOBAL_PRE_TAPER_MAX_FOR_FLOOR",
    "TAPER_LONG_RUN_ALLOWS_LARGE_DROPS",
    "TAPER_EXEMPT_FROM_PEAK_LONG_RUN_FLOOR",
    "BUILD_AND_BASE_LONG_RUN_ALLOWS_CUTBACK_WEEKS",
    "BUILD_AND_BASE_EXEMPT_FROM_PEAK_LONG_RUN_FLOOR",
]
