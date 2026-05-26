from __future__ import annotations

from typing import Any, Optional

from src.smartcoach_mobile_coach.runner_profile.models import (
    HrZoneBand,
    PaceZoneBand,
    RunnerZoneProfileData,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.gyor.models import (
    EasyGyorReference,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.models import (
    TrainingPaceRecommendations,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.hr_progress_easy import (
    EasyHrProgressReference,
    hr_progress_zones_chart_api_payload,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.pace_progress_easy import (
    EasyPaceProgressReference,
    pace_progress_zones_chart_api_payload,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.pace_progress_tempo import (
    TempoPaceProgressReference,
    tempo_pace_progress_zones_chart_api_payload,
)

# Canonical copy for Insights › Easy banner (emitted whenever Z2 HR + Z2 pace are present).
INSIGHTS_EASY_BANNER_SUBTITLE = (
    "Stay within this HR range to keep easy runs truly easy and avoid carrying "
    "fatigue into harder days."
)

# Canonical copy for Insights › Tempo banner (emitted whenever tempo pace corridor exists).
INSIGHTS_TEMPO_BANNER_SUBTITLE = (
    "Stay within this tempo pace range to hit the right stimulus — too fast or "
    "too slow can miss the workout intent."
)


def _hr_band_payload(band: Optional[HrZoneBand]) -> Optional[dict[str, int]]:
    if band is None:
        return None
    return {"low": int(band.low), "high": int(band.high)}


def _pace_band_payload(band: Optional[PaceZoneBand]) -> Optional[dict[str, Any]]:
    if band is None:
        return None
    return {
        "low_sec": int(band.low_sec),
        "high_sec": int(band.high_sec),
        "display": band.display,
    }


def _hr_progress_payload(
    ref: Optional[EasyHrProgressReference],
) -> Optional[dict[str, Any]]:
    """Insights Avg HR chart authority (Z2 high cap + Y/O/R zones)."""
    if ref is None:
        return None
    return {
        "target_hr_z2": _hr_band_payload(ref.target_hr_z2),
        "target_display": ref.target_display,
        "hr_zones_chart": hr_progress_zones_chart_api_payload(ref.hr_zones_chart),
    }


def _pace_progress_payload(
    ref: Optional[EasyPaceProgressReference],
) -> Optional[dict[str, Any]]:
    """Insights Avg Pace chart authority (HR-free target + Y/O/R zones)."""
    if ref is None:
        return None
    return {
        "target_easy_pace": _pace_band_payload(ref.target_easy_pace),
        "pace_zones_chart": pace_progress_zones_chart_api_payload(ref.pace_zones_chart),
    }


def _tempo_pace_progress_payload(
    ref: Optional[TempoPaceProgressReference],
) -> Optional[dict[str, Any]]:
    """Insights Tempo Avg Pace chart authority (Z3 corridor + bilateral Y/O/R zones)."""
    if ref is None:
        return None
    return {
        "target_tempo_pace": _pace_band_payload(ref.target_tempo_pace),
        "target_display": ref.target_display,
        "pace_zones_chart": tempo_pace_progress_zones_chart_api_payload(
            ref.pace_zones_chart
        ),
    }


def _easy_gyor_payload(ref: Optional[EasyGyorReference]) -> Optional[dict[str, Any]]:
    """HR-fused easy GYOR reference only (no pace-progress chart fields).

    Chart target and zones live under ``training_pace_recommendations.pace_progress``.
    Goal easy envelope lives under ``training_pace_recommendations.goal_aligned_easy_pace``.
    """
    if ref is None:
        return None
    return {
        "policy": ref.policy,
        "hr_target_z2": _hr_band_payload(ref.hr_target_z2),
    }


def _training_pace_recommendations_payload(
    recs: Optional[TrainingPaceRecommendations],
) -> Optional[dict[str, Any]]:
    if recs is None:
        return None

    tempo_payload = _tempo_pace_progress_payload(recs.tempo_pace_progress)
    payload: dict[str, Any] = {
        "phase": recs.phase,
        "phase_source": recs.phase_source,
        "phase_week_start": recs.phase_week_start,
        "source_target_time": recs.source_target_time,
        "activity_easy_pace": _pace_band_payload(recs.activity_easy_pace),
        "activity_z3_pace": _pace_band_payload(recs.activity_z3_pace),
        "activity_z4_pace": _pace_band_payload(recs.activity_z4_pace),
        "goal_aligned_easy_pace": _pace_band_payload(recs.goal_aligned_easy_pace),
        "goal_aligned_z3_pace": _pace_band_payload(recs.goal_aligned_z3_pace),
        "goal_aligned_z4_pace": _pace_band_payload(recs.goal_aligned_z4_pace),
        "goal_aligned_marathon_pace": _pace_band_payload(
            recs.goal_aligned_marathon_pace
        ),
        "pace_progress": _pace_progress_payload(recs.pace_progress),
        "tempo_pace_progress": tempo_payload,
        "hr_progress": _hr_progress_payload(recs.hr_progress),
        "easy_gyor": _easy_gyor_payload(recs.easy_gyor),
    }
    if tempo_payload is not None:
        payload["threshold_pace_progress"] = tempo_payload
    return payload


def runner_zone_profile_payload(
    profile: RunnerZoneProfileData,
    *,
    training_pace_recommendations: Optional[TrainingPaceRecommendations] = None,
) -> dict[str, Any]:
    pace_zones: dict[str, Any] = {}
    for key_name, pace_band in (
        ("z2", profile.pace_z2),
        ("z3", profile.pace_z3),
        ("z4", profile.pace_z4),
    ):
        band_payload = _pace_band_payload(pace_band)
        if band_payload is not None:
            pace_zones[key_name] = band_payload

    insights_easy_banner = None
    if (
        training_pace_recommendations is not None
        and training_pace_recommendations.hr_progress is not None
        and training_pace_recommendations.pace_progress is not None
    ):
        insights_easy_banner = {"subtitle": INSIGHTS_EASY_BANNER_SUBTITLE}

    insights_tempo_banner = None
    if (
        training_pace_recommendations is not None
        and training_pace_recommendations.tempo_pace_progress is not None
    ):
        insights_tempo_banner = {"subtitle": INSIGHTS_TEMPO_BANNER_SUBTITLE}

    return {
        "calibrated": bool(profile.calibrated),
        "computed_at": profile.computed_at.isoformat() if profile.computed_at else None,
        "hrmax": profile.hrmax_used,
        "resting_hr": profile.resting_hr_used,
        "zone_method": profile.zone_method,
        "hr_zones": (
            {
                "z1": _hr_band_payload(profile.hr_z1),
                "z2": _hr_band_payload(profile.hr_z2),
                "z3": _hr_band_payload(profile.hr_z3),
                "z4": _hr_band_payload(profile.hr_z4),
                "z5": _hr_band_payload(profile.hr_z5),
            }
            if profile.calibrated
            else None
        ),
        "pace_zones": pace_zones if pace_zones else None,
        "pace_source": profile.pace_source,
        "pace_computed_at": (
            profile.pace_computed_at.isoformat() if profile.pace_computed_at else None
        ),
        "insights_easy_banner": insights_easy_banner,
        "insights_tempo_banner": insights_tempo_banner,
        "training_pace_recommendations": _training_pace_recommendations_payload(
            training_pace_recommendations
        ),
    }
