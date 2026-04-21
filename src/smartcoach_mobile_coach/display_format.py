"""Human-readable display strings for runner-facing tool payloads (Topic 4)."""

from datetime import date, datetime
from typing import Optional, Union

_DateLike = Union[date, datetime, str, None]


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


def format_hr_range_bpm(low: Optional[float], high: Optional[float]) -> Optional[str]:
    """
    Format an HR range as "138–150 bpm". Collapses to a single value
    ("142 bpm") when both ends are equal. Returns ``None`` when either
    end is missing — callers should fall back to the numeric fields.
    """
    if low is None or high is None:
        return None
    try:
        lo = int(round(float(low)))
        hi = int(round(float(high)))
    except (TypeError, ValueError):
        return None
    if lo == hi:
        return f"{lo} bpm"
    return f"{lo}\u2013{hi} bpm"


def format_percent(value: Optional[float], *, decimals: int = 0) -> Optional[str]:
    """
    Format a fractional value (``0.725``) as a percentage string
    (``"72 %"``  / ``"72.5 %"``). Accepts a value already in %-space
    (``72.5``) by leaving values above 1.5 untouched — the ambiguous
    range ``[0, 1.5]`` is interpreted as fractional. Returns ``None``
    on bad input so callers can degrade to the raw numeric field.
    """
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if -1.5 <= v <= 1.5:
        v = v * 100.0
    return f"{v:.{decimals}f} %"


def format_time_utc(dt) -> str:
    if dt is None:
        return "—"
    try:
        return dt.strftime("%I:%M %p").lstrip("0") + " UTC"
    except Exception:
        return "—"


def _coerce_to_date(value: _DateLike) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and len(value) >= 10:
        try:
            return datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def format_month_day(local_d: _DateLike) -> str:
    """Table-friendly month-day, e.g. 03-24 (no year)."""
    d = _coerce_to_date(local_d)
    if d is None:
        return "—"
    return f"{d.month:02d}-{d.day:02d}"


def table_row_date_label(local_d: _DateLike, anchor_yyyy_mm_dd: Optional[str]) -> str:
    """
    Label for comparison tables: 'Today' if local calendar day matches anchor (YYYY-MM-DD),
    else MM-DD. Central place for coach table date copy.
    """
    d = _coerce_to_date(local_d)
    if d is None:
        return "—"
    a = (anchor_yyyy_mm_dd or "").strip()[:10]
    if len(a) == 10 and d.isoformat() == a:
        return "Today"
    return format_month_day(d)
