from __future__ import annotations

from statistics import median
from typing import Dict, List, Optional, Tuple


def _sec_per_mile(distance_mi: float, moving_time_sec: float) -> Optional[float]:
    """Return pace sec/mi or None if inputs invalid."""
    if not distance_mi or distance_mi <= 0:
        return None
    if not moving_time_sec or moving_time_sec <= 0:
        return None
    return float(moving_time_sec) / float(distance_mi)


def _get_miles_from_activity(a: Dict) -> float:
    """
    Robustly derive miles from an activity dict that may store:
      - conv_distance: already miles (preferred)
      - distance: may be meters (DB) or miles (API-level)
    Heuristic:
      - If conv_distance exists and > 0 → use it (miles).
      - Else if distance > 100 → treat as meters, convert to miles.
      - Else → treat distance as miles.
    """
    conv_distance = a.get("conv_distance")
    if conv_distance is not None:
        try:
            miles = float(conv_distance)
            if miles > 0:
                return miles
        except (TypeError, ValueError):
            pass

    raw = a.get("distance")
    if raw is None:
        return 0.0
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return 0.0

    # If very large, assume meters and convert to miles
    if val > 100.0:
        return val / 1609.34
    return val


def compute_weekly_aggregates_from_activities(
    activities: List[Dict],
    easyish_min_mi: float = 3.0,
    easyish_max_mi: float = 12.0,
    lr_min_mi: float = 10.0,
) -> Dict[str, Optional[float]]:
    """
    Compute weekly aggregates from raw activity dicts.

    activities: [{
      'date': 'YYYY-MM-DD',
      'distance': float (miles),
      'moving_time': int (seconds),
      ...
    }]
    """
    runs: List[Tuple[float, Optional[float]]] = []
    for a in activities:
        miles = _get_miles_from_activity(a)
        moving_time = float(a.get("moving_time") or 0.0)
        pace = _sec_per_mile(miles, moving_time)
        runs.append((miles, pace))

    # Easy-ish subset
    easyish_paces = [
        pace
        for miles, pace in runs
        if pace is not None and easyish_min_mi <= miles <= easyish_max_mi
    ]

    # Longest run (≥ threshold)
    longest: Tuple[float, Optional[float]] = max(
        runs, key=lambda t: t[0], default=(0.0, None)
    )
    lr_pace = longest[1] if longest and longest[0] >= lr_min_mi else None

    return {
        "weekly_easyish_median_sec": median(easyish_paces) if easyish_paces else None,
        "weekly_lr_pace_sec": lr_pace,
        "runs_count": len([1 for _, p in runs if p is not None]),
        "total_miles": sum(m for m, _ in runs),
    }
