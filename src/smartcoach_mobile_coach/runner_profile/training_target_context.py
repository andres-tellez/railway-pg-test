"""
Composed read-model for Coach: destination (goal) vs starting point (fitness).

Wires existing SSOT producers only — no new pace/HR math. See runner_profile/README.md
pace_authorities table.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from src.coaching_intelligence.ambition_gap import evaluate_ambition_gap
from src.db.dao.plans_dao import get_active_or_most_recent_plan
from src.db.dao.user_profile_dao import get_user_profile
from src.db.models.plans import Plan
from src.services.baseline.baseline_status import compute_baseline_status_for_athlete
from src.services.heart_rate.hrmax_resolution_service import HRMaxResolutionService
from src.services.metrics_helper_service import (
    get_weekly_fitness_from_materialized_view,
)
from src.smartcoach_mobile_coach.db_helpers import get_primary_athlete_id
from src.smartcoach_mobile_coach.runner_profile.api_schema import (
    pace_authorities_api_payload,
    training_pace_recommendations_api_payload,
    zones_inputs_api_payload,
    _hr_band_payload,
    _pace_band_payload,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.goal_aligned_pace import (
    marathon_sec_per_mi_from_target_time,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.training_phase_resolver import (
    resolve_current_training_phase,
)
from src.smartcoach_mobile_coach.runner_profile.service import (
    get_runner_profile,
    get_runner_training_pace_recommendations,
)

SCHEMA_VERSION = "training_target_context.v1"


def _resolve_goal_fields(
    *,
    plan: Plan | None,
    target_time: str | None,
    race_distance: str | None,
) -> tuple[str | None, str | None]:
    resolved_target_time = target_time
    resolved_race_distance = race_distance
    if plan is not None:
        if resolved_target_time is None:
            resolved_target_time = getattr(plan, "target_time", None)
        if resolved_race_distance is None:
            resolved_race_distance = getattr(plan, "race_distance", None)
    return resolved_target_time, resolved_race_distance


def _profile_pace_zones_payload(profile) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key_name, pace_band in (
        ("z2", profile.pace_z2),
        ("z3", profile.pace_z3),
        ("z4", profile.pace_z4),
    ):
        band_payload = _pace_band_payload(pace_band)
        if band_payload is not None:
            out[key_name] = band_payload
    return out


def _profile_hr_zones_payload(profile) -> dict[str, Any] | None:
    if not profile.calibrated:
        return None
    return {
        "z1": _hr_band_payload(profile.hr_z1),
        "z2": _hr_band_payload(profile.hr_z2),
        "z3": _hr_band_payload(profile.hr_z3),
        "z4": _hr_band_payload(profile.hr_z4),
        "z5": _hr_band_payload(profile.hr_z5),
    }


def build_training_target_context(
    session: Session,
    user_id: str,
    *,
    target_time: str | None = None,
    race_distance: str | None = None,
    plan: Plan | None = None,
    primary_goal: str | None = None,
) -> dict[str, Any]:
    """
    Build Coach-facing training target context from canonical producers.

    Prescription on plan rows remains activity-calibrated; this payload exposes
    both authorities for explanation and monitoring.
    """
    plan_row = plan
    if plan_row is None:
        plan_row = get_active_or_most_recent_plan(session, user_id)

    resolved_target_time, resolved_race_distance = _resolve_goal_fields(
        plan=plan_row,
        target_time=target_time,
        race_distance=race_distance,
    )
    resolved_primary_goal = primary_goal
    if resolved_primary_goal is None and plan_row is not None:
        resolved_primary_goal = getattr(plan_row, "primary_goal", None)

    profile = get_runner_profile(session, user_id)
    recs = get_runner_training_pace_recommendations(
        session,
        user_id,
        target_time=resolved_target_time,
        race_distance=resolved_race_distance,
        plan=plan_row,
        profile=profile,
    )
    phase_resolution = resolve_current_training_phase(session, user_id, plan=plan_row)

    weekly_mileage = 0.0
    longest_run_miles = 0.0
    try:
        weekly_mileage, longest_run_miles = get_weekly_fitness_from_materialized_view(
            session, user_id
        )
    except Exception:
        weekly_mileage = 0.0
        longest_run_miles = 0.0

    ambition_gap = evaluate_ambition_gap(
        weekly_mileage=weekly_mileage,
        primary_goal=resolved_primary_goal,
        target_time=resolved_target_time,
        longest_run_miles=longest_run_miles,
    )

    baseline_status_value: str | None = None
    try:
        athlete_id = get_primary_athlete_id(session, user_id)
        baseline_status_value = compute_baseline_status_for_athlete(
            session, athlete_id
        ).value
    except Exception:
        baseline_status_value = None

    profile_dict = get_user_profile(session, user_id) or {}
    hr_calibration = HRMaxResolutionService.get_hr_calibration_status(profile_dict)

    goal_mp_sec = marathon_sec_per_mi_from_target_time(
        resolved_target_time,
        race_distance=resolved_race_distance,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "inputs": zones_inputs_api_payload(
            profile,
            target_time=resolved_target_time,
            race_distance=resolved_race_distance,
            training_pace_recommendations=recs,
        ),
        "training_pace_recommendations": training_pace_recommendations_api_payload(
            recs
        ),
        "pace_authorities": pace_authorities_api_payload(profile, recs),
        "current_fitness": {
            "calibrated": bool(profile.calibrated),
            "pace_source": profile.pace_source,
            "pace_zones": _profile_pace_zones_payload(profile) or None,
            "weekly_mileage": round(float(weekly_mileage), 2),
            "longest_run_miles": round(float(longest_run_miles), 2),
        },
        "hr_guardrails": {
            "hr_calibration": hr_calibration,
            "hr_zones": _profile_hr_zones_payload(profile),
            "zone_method": profile.zone_method,
        },
        "plan_phase": {
            "phase": phase_resolution.phase,
            "phase_source": phase_resolution.source,
            "phase_week_start": (
                phase_resolution.week_start.isoformat()
                if phase_resolution.week_start is not None
                else None
            ),
        },
        "evidence": {
            "baseline_status": baseline_status_value,
            "ambition_gap": ambition_gap,
        },
        "gap_summary": {
            "goal_marathon_pace_sec_per_mi": goal_mp_sec,
            "stance": ambition_gap.get("stance"),
            "baseline_band": ambition_gap.get("baseline_band"),
            "goal_demand": ambition_gap.get("goal_demand"),
        },
        "product_principle": (
            "Train from where you are (current_fitness / plan prescription). "
            "Measure against where you want to go (training_pace_recommendations goal bands / Insights)."
        ),
    }
