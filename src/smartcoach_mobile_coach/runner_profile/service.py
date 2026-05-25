from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.db.models.plans import Plan
from src.smartcoach_mobile_coach.runner_profile.hr_builder import compute_hr_zones
from src.smartcoach_mobile_coach.runner_profile.models import (
    HrZoneBand,
    PaceZoneComputation,
    PaceZoneBand,
    RunnerZoneProfileData,
)
from src.smartcoach_mobile_coach.runner_profile.pace_builder import (
    DEFAULT_PACE_ZONE_CONFIG,
    calculate_week1_long_cap,
    calibration_pace_zones,
    compute_pace_zones_from_activities,
)
from src.smartcoach_mobile_coach.runner_profile.persistence import (
    delete_runner_zone_profile,
    read_runner_zone_profile,
    upsert_runner_zone_profile,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.models import (
    TrainingPaceRecommendations,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.training_pace_recommendations import (
    build_training_pace_recommendations,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.training_phase_resolver import (
    TrainingPhaseResolution,
    resolve_current_training_phase,
)

logger = logging.getLogger(__name__)


def _profile_needs_pace_repair(profile: RunnerZoneProfileData) -> bool:
    """HR-only rows (legacy backfills) must refresh so Z2-Z4 pace bands are persisted."""
    if not profile.calibrated or profile.hr_z2 is None:
        return False
    return profile.pace_z2 is None


def _uncalibrated_profile(user_id: str) -> RunnerZoneProfileData:
    return RunnerZoneProfileData(
        user_id=user_id,
        calibrated=False,
        computed_at=None,
        hrmax_used=None,
        resting_hr_used=None,
        zone_method=None,
        hr_z1=None,
        hr_z2=None,
        hr_z3=None,
        hr_z4=None,
        hr_z5=None,
        pace_z2=None,
        pace_z3=None,
        pace_z4=None,
        pace_source=None,
        pace_computed_at=None,
    )


def get_runner_profile(session: Session, user_id: str) -> RunnerZoneProfileData:
    try:
        row = read_runner_zone_profile(session, user_id)
        if row is None:
            # Lazy backfill: compute on first read if absent.
            return refresh_runner_profile(session, user_id)
        if _profile_needs_pace_repair(row):
            return refresh_runner_profile(session, user_id)
        return row
    except SQLAlchemyError:
        logger.exception("Failed reading runner zone profile for user %s", user_id)
        return _uncalibrated_profile(user_id)


def refresh_runner_profile(session: Session, user_id: str) -> RunnerZoneProfileData:
    """
    Recompute and upsert runner profile zone bands.
    """
    hr = compute_hr_zones(session, user_id)
    if hr is None:
        try:
            delete_runner_zone_profile(session, user_id)
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            logger.exception(
                "Failed deleting runner zone profile for uncalibrated user %s", user_id
            )
        return _uncalibrated_profile(user_id)

    pace = compute_pace_zones_from_activities(session, user_id)
    if pace is None:
        pace = calibration_pace_zones()

    try:
        upsert_runner_zone_profile(session, user_id, hr=hr, pace=pace)
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        logger.exception("Failed upserting runner zone profile for user %s", user_id)
        return _uncalibrated_profile(user_id)

    return get_runner_profile(session, user_id)


def _pace_computation_from_profile(
    *,
    session: Session,
    user_id: str,
    profile: RunnerZoneProfileData,
) -> PaceZoneComputation | None:
    """
    Build a full ``PaceZoneComputation`` from persisted runner profile bands.

    ``runner_zone_profiles`` stores z2/z3/z4 pace bands and metadata, but not
    marathon pace or week1 long-run cap. For plan generation compatibility we
    reconstruct:
    - ``marathon_sec`` from z4 lower bound (same convention as pace_ranges `m`)
    - ``week1_long_cap`` from recent-run lookback using pace config defaults
    """
    if not profile.calibrated:
        return None
    if profile.pace_z2 is None or profile.pace_z3 is None or profile.pace_z4 is None:
        return None

    week1_long_cap = calculate_week1_long_cap(
        session=session,
        user_id=user_id,
        lookback_weeks=DEFAULT_PACE_ZONE_CONFIG.lookback_weeks,
        config=DEFAULT_PACE_ZONE_CONFIG,
    )
    pace_computed_at = profile.pace_computed_at or datetime.now(timezone.utc)
    marathon_sec = int(profile.pace_z4.low_sec)

    return PaceZoneComputation(
        pace_z2=profile.pace_z2,
        pace_z3=profile.pace_z3,
        pace_z4=profile.pace_z4,
        pace_source=profile.pace_source or "runner_profile",
        pace_computed_at=pace_computed_at,
        marathon_sec=marathon_sec,
        week1_long_cap=float(week1_long_cap),
    )


def get_runner_pace_zones_for_plan_generation(
    session: Session,
    user_id: str,
    *,
    force_refresh: bool = False,
    lookback_weeks: int | None = None,
) -> PaceZoneComputation:
    """
    Resolve canonical pace zones for plan generation, rebuild, and admin tools.

    Primary source is persisted ``runner_profile``. If pace bands are missing,
    fall back to direct pace computation from recent activities, then calibration.

    When ``force_refresh`` is True and ``lookback_weeks`` is None, refreshes the
    persisted profile before reading bands. When ``lookback_weeks`` is set,
    activity-based computation uses that window (admin/debug overrides).
    """
    if force_refresh and lookback_weeks is None:
        refresh_runner_profile(session, user_id)

    profile = get_runner_profile(session, user_id)
    if not (force_refresh and lookback_weeks is not None):
        pace_from_profile = _pace_computation_from_profile(
            session=session,
            user_id=user_id,
            profile=profile,
        )
        if pace_from_profile is not None:
            return pace_from_profile

    pace_from_activities = compute_pace_zones_from_activities(
        session,
        user_id,
        lookback_weeks=lookback_weeks,
    )
    if pace_from_activities is not None:
        return pace_from_activities
    return calibration_pace_zones()


def _zone_key_for_run_type(run_type_key: str) -> str:
    run_type_lower = str(run_type_key or "").lower()
    if run_type_lower in {"threshold", "tempo", "steady"}:
        return "z3"
    if run_type_lower in {"vo2", "intervals", "repetitions", "race"}:
        return "z4"
    return "z2"


def get_runner_pace_zone_key_for_run_type(
    run_type_key: str, *, has_marathon_finish: bool = False
) -> str:
    """
    Resolve canonical pace-band key for a planned workout.

    Returns one of ``z2``, ``z3``, ``z4``, or ``m``.
    """
    run_type_lower = str(run_type_key or "").lower()
    if has_marathon_finish and run_type_lower == "long":
        return "m"
    return _zone_key_for_run_type(run_type_key)


def _band_for_zone_key(
    profile: RunnerZoneProfileData, zone_key: str
) -> HrZoneBand | None:
    if zone_key == "z2":
        return profile.hr_z2
    if zone_key == "z3":
        return profile.hr_z3
    if zone_key == "z4":
        return profile.hr_z4
    if zone_key == "z1":
        return profile.hr_z1
    if zone_key == "z5":
        return profile.hr_z5
    return None


def _pace_band_for_zone_key(
    profile: RunnerZoneProfileData, zone_key: str
) -> PaceZoneBand | None:
    if zone_key == "z2":
        return profile.pace_z2
    if zone_key == "z3":
        return profile.pace_z3
    if zone_key == "z4":
        return profile.pace_z4
    return None


def runner_pace_ranges_payload(profile: RunnerZoneProfileData) -> dict[str, list[int]]:
    """
    Canonical plan_workouts.pace_ranges payload from runner profile SoT.

    Keys are zone-native (`z2`,`z3`,`z4`) with optional `m` single-value band.
    Returns empty dict when profile lacks calibrated pace bands.
    """
    if not profile.calibrated:
        return {}

    payload: dict[str, list[int]] = {}
    if profile.pace_z2 is not None:
        payload["z2"] = [int(profile.pace_z2.low_sec), int(profile.pace_z2.high_sec)]
    if profile.pace_z3 is not None:
        payload["z3"] = [int(profile.pace_z3.low_sec), int(profile.pace_z3.high_sec)]
    if profile.pace_z4 is not None:
        payload["z4"] = [int(profile.pace_z4.low_sec), int(profile.pace_z4.high_sec)]
    # Keep marathon value available for legacy displays/labels when present.
    if profile.pace_z4 is not None:
        payload["m"] = [int(profile.pace_z4.low_sec), int(profile.pace_z4.low_sec)]
    return payload


def get_runner_pace_band_for_run_type(
    session: Session,
    user_id: str,
    run_type_key: str,
    *,
    force_refresh: bool = False,
) -> tuple[int, int] | None:
    """
    Return canonical pace band seconds for a run type from runner profile.
    """
    profile = (
        refresh_runner_profile(session, user_id)
        if force_refresh
        else get_runner_profile(session, user_id)
    )
    if not profile.calibrated:
        return None
    zone_key = _zone_key_for_run_type(run_type_key)
    band = _pace_band_for_zone_key(profile, zone_key)
    if band is None:
        return None
    return int(band.low_sec), int(band.high_sec)


def get_runner_zone_string_for_run_type(
    session: Session,
    user_id: str,
    run_type_key: str,
    *,
    force_refresh: bool = False,
) -> str:
    """
    Shared formatter for plan/HR call sites that need `target_hr`-style strings.

    Returns an empty string when no calibrated SoT band exists.
    """
    profile = (
        refresh_runner_profile(session, user_id)
        if force_refresh
        else get_runner_profile(session, user_id)
    )
    if not profile.calibrated:
        return ""
    zone_key = _zone_key_for_run_type(run_type_key)
    band = _band_for_zone_key(profile, zone_key)
    if band is None:
        return ""
    return f"{zone_key.upper()} ({int(band.low)}–{int(band.high)} bpm)"


def get_runner_training_pace_recommendations(
    session: Session,
    user_id: str,
    *,
    target_time: str | None,
    plan: Plan | None = None,
    phase_resolution: TrainingPhaseResolution | None = None,
    profile: RunnerZoneProfileData | None = None,
    force_refresh: bool = False,
) -> TrainingPaceRecommendations | None:
    """
    Build composite pace recommendations from activity-derived and goal-aligned pace.

    This function intentionally lives under runner_profile so recommendation rules can
    later expand with HR recommendation logic in the same architecture.
    """
    profile_data = profile
    if profile_data is None:
        profile_data = (
            refresh_runner_profile(session, user_id)
            if force_refresh
            else get_runner_profile(session, user_id)
        )
    resolved = phase_resolution or resolve_current_training_phase(
        session, user_id, plan=plan
    )
    return build_training_pace_recommendations(
        profile=profile_data,
        target_time=target_time,
        phase=resolved.phase,
        phase_source=resolved.source,
        phase_week_start=(
            resolved.week_start.isoformat() if resolved.week_start is not None else None
        ),
    )
