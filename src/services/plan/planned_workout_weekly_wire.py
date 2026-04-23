"""
Single source of truth for **scheduled workout** fields on the weekly-plan wire.

``GET /api/plan/current-week`` and ``get_weekly_plan`` (via
:func:`src.services.plan.weekly_plan.build_weekly_plan_payload`) must not
re-encode planned miles / HR / pace in multiple places. All **plan-side**
presentation for a :class:`~src.db.models.plan_workouts.PlanWorkout`` row
flows through :func:`build_planned_weekly_wire`.

* **``display.planned``** — Topic 4 strings (``miles``, ``target_hr``, optional
  ``pace``) for coach + mobile.
* **``execution.planned``** — canonical ``type`` + ``miles`` from the plan row,
  plus optional ``target_pace_display`` (same human string as ``display.planned.pace``).

``execution`` blocks are still built from activities for **actual.*** ; callers
merge this wire over the adapter output so ``planned.*`` always reflects the
calendar row, not ``Activity.planned_*`` analysis leftovers.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.db.models.plan_workouts import PlanWorkout
from src.smartcoach_mobile_coach.display_format import (
    format_distance_mi,
    format_pace_sec_per_mi,
)

_PACE_KEYS = frozenset({"E", "S", "M", "T"})


def _intensity_band_key(w: PlanWorkout) -> str:
    raw = (getattr(w, "intensity", None) or "").strip().upper()
    if raw and raw[0] in _PACE_KEYS:
        return raw[0]
    rtk = (getattr(w, "run_type_key", None) or "").strip().lower()
    if rtk == "steady":
        return "S"
    return "E"


def _pace_band_seconds(w: PlanWorkout) -> Optional[tuple[int, int]]:
    pr = getattr(w, "pace_ranges", None)
    if not isinstance(pr, dict) or not pr:
        return None
    letter = _intensity_band_key(w)
    raw = pr.get(letter)
    if raw is None and letter != "E":
        raw = pr.get("E")
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        sec = int(raw)
        return sec, sec
    if isinstance(raw, list) and len(raw) >= 2:
        lo, hi = int(raw[0]), int(raw[1])
        return lo, hi
    return None


def _pace_mmss_only(sec_per_mi: float) -> str:
    """``M:SS`` segment only, same rounding rules as :func:`format_pace_sec_per_mi`."""
    full = format_pace_sec_per_mi(sec_per_mi)
    if full == "—":
        return "—"
    if full.endswith("/mi"):
        return full.removesuffix("/mi")
    return full


def planned_pace_display_string(w: PlanWorkout) -> Optional[str]:
    """
    Human-readable planned pace or band from ``pace_ranges`` (sec/mi), or
    ``None`` when no ranges exist.

    Single target: ``9:18/mi``. A band uses one trailing unit:
    ``9:37-10:30/mi``.
    """
    band = _pace_band_seconds(w)
    if band is None:
        return None
    lo, hi = band
    a_full = format_pace_sec_per_mi(float(lo))
    b_full = format_pace_sec_per_mi(float(hi))
    if a_full == "—" and b_full == "—":
        return None
    if lo == hi or a_full == b_full:
        return a_full if a_full != "—" else b_full
    a = _pace_mmss_only(float(lo))
    b = _pace_mmss_only(float(hi))
    if a == "—":
        return b_full
    if b == "—":
        return a_full
    return f"{a}-{b}/mi"


def build_planned_weekly_wire(
    w: PlanWorkout,
    *,
    canonical_run_type_key: str,
    target_hr: Optional[Any],
) -> Dict[str, Any]:
    """
    Return ``{"display_planned": {...}, "execution_planned": {...}}`` for one
    plan workout. Always includes ``miles`` / ``target_hr`` display strings;
    includes ``pace`` only when :func:`planned_pace_display_string` is non-null.
    """
    miles_fmt = format_distance_mi(w.miles) if w.miles is not None else None
    pace = planned_pace_display_string(w)
    display_planned: Dict[str, Any] = {
        "miles": miles_fmt,
        "target_hr": target_hr,
    }
    if pace is not None:
        display_planned["pace"] = pace

    execution_planned: Dict[str, Any] = {
        "type": canonical_run_type_key,
        "miles": w.miles,
    }
    if pace is not None:
        execution_planned["target_pace_display"] = pace

    return {
        "display_planned": display_planned,
        "execution_planned": execution_planned,
    }


def merge_planned_wire_into_execution_shape(
    shape: Dict[str, Any],
    wire: Dict[str, Any],
) -> None:
    """
    Mutates a weekly ``execution`` dict so ``planned`` + legacy flats +
    ``display.planned`` match :func:`build_planned_weekly_wire` (plan row is
    authoritative for the scheduled workout).
    """
    ex_pl = dict(wire.get("execution_planned") or {})
    shape["planned"] = {**(shape.get("planned") or {}), **ex_pl}
    shape["planned_type"] = ex_pl.get("type")
    shape["planned_miles"] = ex_pl.get("miles")

    disp = shape.setdefault("display", {})
    disp["planned"] = dict(wire.get("display_planned") or {})


__all__ = [
    "build_planned_weekly_wire",
    "merge_planned_wire_into_execution_shape",
    "planned_pace_display_string",
]
