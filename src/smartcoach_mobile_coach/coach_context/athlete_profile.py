"""
Purpose:
- Build the compact athlete/profile slice for CoachSnapshot.

Responsibilities:
- Map profile identity primitives from user_context.
- Derive HR calibration status using HRMaxResolutionService.
- Attach compact zone anchors (Z2-Z4 bpm) when calibrated.

Non-goals:
- No deterministic coaching verdicts.
- No plan/trend/memory computations.

Guardrails:
- Allowed imports/calls: user_profile + user_hr_zones models and HR services.
- Must not import orchestrator or run-review modules.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from src.db.models.user_hr_zones import UserHrZones
from src.db.models.user_profile import UserProfile
from src.services.heart_rate.hrmax_resolution_service import HRMaxResolutionService
from src.smartcoach_mobile_coach.coach_context.schemas import AthleteSlice


def _unit_short(raw: Optional[str]) -> str:
    val = (raw or "").strip().lower()
    if val in ("metric", "km"):
        return "km"
    return "mi"


def _status_label(status_payload: Dict[str, Any]) -> str:
    status = str(status_payload.get("status") or "").strip().lower()
    if status == "calibrated":
        return "calibrated"
    if status == "uncalibrated":
        if int(status_payload.get("activities_needed") or 0) > 0:
            return "in_progress"
        return "unknown"
    return "unknown"


def _load_profile_dict(session: Session, internal_user_id: str) -> Dict[str, Any]:
    row = (
        session.query(UserProfile)
        .filter(UserProfile.user_id == str(internal_user_id))
        .one_or_none()
    )
    if row is None:
        return {}
    return {
        "max_hr_manual": row.max_hr_manual,
        "max_hr_auto": row.max_hr_auto,
        "max_hr_active": row.max_hr_active,
        "hrmax_confidence": row.hrmax_confidence,
        "hrmax_activity_count": row.hrmax_activity_count,
    }


def _load_zones_compact(
    session: Session, internal_user_id: str, calibrated: bool
) -> Optional[Dict[str, int]]:
    if not calibrated:
        return None
    row = (
        session.query(UserHrZones)
        .filter(UserHrZones.user_id == str(internal_user_id))
        .one_or_none()
    )
    if row is None:
        return None
    out: Dict[str, int] = {}
    for label, value in (
        ("z2_bpm", row.z2_high or row.z2_low),
        ("z3_bpm", row.z3_high or row.z3_low),
        ("z4_bpm", row.z4_high or row.z4_low),
    ):
        try:
            if value is not None:
                out[label] = int(round(float(value)))
        except (TypeError, ValueError):
            continue
    return out or None


def build_athlete_slice(
    *,
    session: Session,
    internal_user_id: str,
    user_context_payload: Dict[str, Any],
) -> AthleteSlice:
    """Build compact athlete context from canonical payload + profile rows."""
    prefs = user_context_payload.get("preferences") or {}
    profile_dict = _load_profile_dict(session, str(internal_user_id))
    status_payload = HRMaxResolutionService.get_hr_calibration_status(profile_dict)
    status = _status_label(status_payload)
    zones = _load_zones_compact(session, str(internal_user_id), status == "calibrated")
    return AthleteSlice(
        display_name=user_context_payload.get("display_name"),
        unit_system=_unit_short(prefs.get("unit_system")),
        baseline_status=user_context_payload.get("baseline_status"),
        hr_calibration_status=status,
        zones_compact=zones,
    )
