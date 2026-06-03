from __future__ import annotations

import math
from typing import Any

from sqlalchemy.orm import Session

from src.db.dao.plans_dao import get_active_or_most_recent_plan
from src.smartcoach_mobile_coach.insights_systems import (
    INSIGHTS_SYSTEM_SPECS,
    InsightsSystem,
)
from src.smartcoach_mobile_coach.runner_profile.models import HrZoneBand, PaceZoneBand
from src.smartcoach_mobile_coach.runner_profile.recommendations.models import (
    TrainingPaceRecommendations,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.pace_progress_core import (
    PaceProgressChartZone,
    classify_corridor_pace_progress,
    classify_single_cap_pace_progress,
    pace_progress_zones_chart_api_payload,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.pace_progress_easy import (
    DEFAULT_PACE_PROGRESS_EASY_CONFIG,
    target_easy_pace_sec,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.pace_progress_core import (
    build_corridor_zones_chart,
    pace_progress_zones_chart_api_payload,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.pace_progress_tempo import (
    DEFAULT_PACE_PROGRESS_TEMPO_CONFIG,
    format_tempo_corridor_target_display,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.hr_progress_tempo import (
    DEFAULT_HR_PROGRESS_TEMPO_CONFIG,
    classify_tempo_hr_progress,
)
from src.smartcoach_mobile_coach.runner_profile.service import (
    get_runner_profile,
    get_runner_training_pace_recommendations,
)


def _coerce_finite_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x):
        return None
    return x


def fetch_training_pace_recommendations(
    session: Session,
    user_id: str,
) -> TrainingPaceRecommendations | None:
    plan_row = get_active_or_most_recent_plan(session, user_id)
    target_time = plan_row.target_time if plan_row is not None else None
    race_distance = (
        getattr(plan_row, "race_distance", None) if plan_row is not None else None
    )
    profile = get_runner_profile(session, user_id)
    return get_runner_training_pace_recommendations(
        session,
        user_id,
        target_time=target_time,
        race_distance=race_distance,
        plan=plan_row,
        profile=profile,
    )


def _pace_zones_chart_payload(
    zones_chart: tuple[PaceProgressChartZone, ...],
) -> list[dict[str, Any]]:
    zones: list[dict[str, Any]] = []
    for zone in pace_progress_zones_chart_api_payload(zones_chart):
        lo = _coerce_finite_float(zone.get("min"))
        hi = _coerce_finite_float(zone.get("max"))
        if lo is None or hi is None:
            continue
        zones.append({"color": str(zone["color"]), "min": lo, "max": hi})
    return zones


def resolve_pace_progress(
    session: Session,
    user_id: str,
    system: InsightsSystem,
    *,
    recs: TrainingPaceRecommendations | None = None,
) -> tuple[PaceZoneBand | None, list[dict[str, Any]], str | None]:
    """
    Resolve pace-progress target corridor/band, chart zones, and display string.

    Returns ``(target_pace, pace_zones, target_display)``. Display is only set for Tempo.
    """
    spec = INSIGHTS_SYSTEM_SPECS[system]
    if recs is None:
        recs = fetch_training_pace_recommendations(session, user_id)
    if recs is None:
        return None, [], None

    ref = getattr(recs, spec.pace_progress_attr, None)
    if ref is None:
        return None, [], None

    if system is InsightsSystem.EASY:
        return (
            ref.target_easy_pace,
            _pace_zones_chart_payload(ref.pace_zones_chart),
            None,
        )

    if system is InsightsSystem.TEMPO:
        return (
            ref.target_tempo_pace,
            _pace_zones_chart_payload(ref.pace_zones_chart),
            ref.target_display,
        )

    if system is InsightsSystem.THRESHOLD:
        z4 = recs.goal_aligned_z4_pace
        if z4 is None:
            return None, [], None
        zones_chart = build_corridor_zones_chart(
            z4,
            gap_cfg=DEFAULT_PACE_PROGRESS_TEMPO_CONFIG,
            axis_cfg=DEFAULT_PACE_PROGRESS_TEMPO_CONFIG,
        )
        return (
            z4,
            _pace_zones_chart_payload(zones_chart),
            format_tempo_corridor_target_display(z4),
        )

    return None, [], None


def attach_pace_progress_band(
    point: dict[str, Any],
    *,
    system: InsightsSystem,
    target_pace: PaceZoneBand | None,
) -> dict[str, Any]:
    """Set pace-progress band on a weekly history point (HR-free)."""
    spec = INSIGHTS_SYSTEM_SPECS[system]
    pace_pm = _coerce_finite_float(point.get(spec.history_pace_field))
    pace_sec = pace_pm * 60.0 if pace_pm is not None else None

    if system is InsightsSystem.EASY:
        band = classify_single_cap_pace_progress(
            pace_sec_per_mi=pace_sec,
            target_sec_per_mi=(
                target_easy_pace_sec(target_pace) if target_pace is not None else None
            ),
            gap_cfg=DEFAULT_PACE_PROGRESS_EASY_CONFIG,
        )
    elif system in (InsightsSystem.TEMPO, InsightsSystem.THRESHOLD):
        band = classify_corridor_pace_progress(
            pace_sec_per_mi=pace_sec,
            corridor=target_pace,
            gap_cfg=DEFAULT_PACE_PROGRESS_TEMPO_CONFIG,
        )
    else:
        band = None

    point[spec.history_band_field] = band
    return point


def resolve_easy_hr_progress(
    session: Session,
    user_id: str,
    *,
    recs: TrainingPaceRecommendations | None = None,
) -> tuple[HrZoneBand | None, list[dict[str, Any]]]:
    """HR-progress target and chart zones from training pace recommendations."""
    if recs is None:
        recs = fetch_training_pace_recommendations(session, user_id)
    if recs is None or recs.hr_progress is None:
        return None, []

    from src.smartcoach_mobile_coach.runner_profile.recommendations.hr_progress_easy import (
        hr_progress_zones_chart_api_payload,
    )

    hp = recs.hr_progress
    zones: list[dict[str, Any]] = []
    for zone in hr_progress_zones_chart_api_payload(hp.hr_zones_chart):
        lo = _coerce_finite_float(zone.get("min"))
        hi = _coerce_finite_float(zone.get("max"))
        if lo is None or hi is None:
            continue
        zones.append({"color": str(zone["color"]), "min": lo, "max": hi})
    return hp.target_hr_z2, zones


def resolve_tempo_hr_progress(
    session: Session,
    user_id: str,
    *,
    recs: TrainingPaceRecommendations | None = None,
) -> tuple[HrZoneBand | None, list[dict[str, Any]], str | None]:
    """Tempo HR-progress target corridor, chart zones, and display string."""
    if recs is None:
        recs = fetch_training_pace_recommendations(session, user_id)
    if recs is None or recs.tempo_hr_progress is None:
        return None, [], None

    from src.smartcoach_mobile_coach.runner_profile.recommendations.hr_progress_tempo import (
        tempo_hr_progress_zones_chart_api_payload,
    )

    hp = recs.tempo_hr_progress
    zones: list[dict[str, Any]] = []
    for zone in tempo_hr_progress_zones_chart_api_payload(hp.hr_zones_chart):
        lo = _coerce_finite_float(zone.get("min"))
        hi = _coerce_finite_float(zone.get("max"))
        if lo is None or hi is None:
            continue
        zones.append({"color": str(zone["color"]), "min": lo, "max": hi})
    return hp.target_hr_z3, zones, hp.target_display


def attach_tempo_hr_progress_band(
    point: dict[str, Any],
    *,
    target_hr_z3: HrZoneBand | None,
) -> dict[str, Any]:
    """Set tempo hr-progress band on a weekly history point (vs calibrated Z3)."""
    avg_hr = _coerce_finite_float(point.get("tempo_segment_avg_hr_bpm"))
    point["tempo_hr_progress_band"] = classify_tempo_hr_progress(
        avg_hr_bpm=avg_hr,
        target_hr_z3=target_hr_z3,
        config=DEFAULT_HR_PROGRESS_TEMPO_CONFIG,
    )
    return point
