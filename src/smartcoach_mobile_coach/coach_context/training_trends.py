"""
Purpose:
- Build compact always-on training trend signals.

Responsibilities:
- Read one canonical KPI producer and project only small trend scalars.
- Omit trend slice when baseline is insufficient or data is absent.

Non-goals:
- No full KPI payloads or long arrays in Layer A.
- No verdict generation.

Guardrails:
- Allowed imports/calls: `get_training_progress` service only.
- Must not import orchestrator or tool wrappers.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from src.smartcoach_mobile_coach.coach_context.schemas import TrendsSlice
from src.smartcoach_mobile_coach.training_kpi_service import get_training_progress


def _to_int_miles(raw: Any) -> Optional[int]:
    try:
        if raw is None:
            return None
        return int(round(float(raw)))
    except (TypeError, ValueError):
        return None


def build_trends_slice(
    *,
    session: Session,
    internal_user_id: str,
    baseline_status: Optional[str],
) -> Optional[TrendsSlice]:
    """Build compact mileage trend slice."""
    if (baseline_status or "").strip().lower() == "insufficient":
        return None
    payload: Dict[str, Any] = get_training_progress(
        session, str(internal_user_id), weeks=4
    )
    if not isinstance(payload, dict) or payload.get("error"):
        return None
    rows = payload.get("weekly_summaries")
    if not isinstance(rows, list) or not rows:
        return None

    vals = []
    for row in rows[:4]:
        if not isinstance(row, dict):
            continue
        v = _to_int_miles(row.get("total_miles"))
        if v is not None:
            vals.append(v)
    if not vals:
        return None
    vals = list(reversed(vals))
    while len(vals) < 4:
        vals.insert(0, 0)
    vals = vals[-4:]
    recent = vals[-1]
    prior = vals[:-1]
    denom = len(prior) if prior else 1
    avg_prior = sum(prior) / float(denom)
    delta = int(round(recent - avg_prior))
    return TrendsSlice(
        mileage_4w=vals,
        mileage_delta_last_vs_avg=delta,
    )
