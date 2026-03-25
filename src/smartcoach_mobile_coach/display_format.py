"""Human-readable display strings for runner-facing tool payloads (Topic 4)."""

from typing import Optional


def format_duration_seconds(sec: int) -> str:
    if sec is None or sec < 0:
        return "—"
    s = int(sec)
    h, rem = divmod(s, 3600)
    m, s2 = divmod(rem, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s2:02d}"
    return f"{m}:{s2:02d}"


def format_pace_sec_per_mi(sec_per_mi: float) -> str:
    """e.g. 558 -> 9:18/mi"""
    if sec_per_mi is None or sec_per_mi <= 0 or sec_per_mi > 3600:
        return "—"
    total = int(round(sec_per_mi))
    m, s = divmod(total, 60)
    return f"{m}:{s:02d}/mi"


def format_distance_mi(miles: float) -> str:
    if miles is None or miles < 0:
        return "—"
    return f"{miles:.2f} mi"


def format_hr_bpm(hr: Optional[float]) -> Optional[str]:
    if hr is None:
        return None
    try:
        v = int(round(float(hr)))
    except (TypeError, ValueError):
        return None
    return f"{v} bpm"


def format_time_utc(dt) -> str:
    if dt is None:
        return "—"
    try:
        return dt.strftime("%I:%M %p").lstrip("0") + " UTC"
    except Exception:
        return "—"
