"""Small DB helpers; avoids importing activity_routes (blueprint side effects)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Session

from src.db.models.user_hr_zones import UserHrZones


def get_primary_athlete_id(session: Session, internal_user_id: str) -> Optional[int]:
    stmt = text(
        """
        SELECT athlete_id
        FROM public.user_athletes
        WHERE user_id = :uid
        LIMIT 1
        """
    ).bindparams(bindparam("uid", type_=PGUUID))
    row = session.execute(stmt, {"uid": internal_user_id}).fetchone()
    if not row:
        return None
    return int(row[0])


def fetch_user_hr_profile_for_coach(
    session: Session, internal_user_id: str
) -> Optional[Dict[str, Any]]:
    """
    Load stored HR zones + max/resting HR used to compute them (user_hr_zones).
    Returned shape is JSON-serializable for get_run_summary / agent tools.
    """
    uid = str(internal_user_id).strip()
    row = session.query(UserHrZones).filter(UserHrZones.user_id == uid).first()
    if row is None:
        return None

    def _f(val: Optional[float]) -> Optional[float]:
        if val is None:
            return None
        return float(val)

    return {
        "method": row.method,
        "hrmax_used_bpm": _f(row.hrmax_used),
        "resting_hr_used_bpm": _f(row.resting_hr_used),
        "zones_bpm": {
            "z1": {"low": _f(row.z1_low), "high": _f(row.z1_high)},
            "z2": {"low": _f(row.z2_low), "high": _f(row.z2_high)},
            "z3": {"low": _f(row.z3_low), "high": _f(row.z3_high)},
            "z4": {"low": _f(row.z4_low), "high": _f(row.z4_high)},
            "z5": {"low": _f(row.z5_low), "high": _f(row.z5_high)},
        },
        "computed_at": row.computed_at.isoformat() if row.computed_at else None,
    }
