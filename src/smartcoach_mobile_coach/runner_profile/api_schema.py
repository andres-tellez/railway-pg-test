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
from src.smartcoach_mobile_coach.runner_profile.recommendations.hr_progress_tempo import (
    TempoHrProgressReference,
    tempo_hr_progress_zones_chart_api_payload,
)
from src.smartcoach_mobile_coach.runner_profile.plan_run_type_registry import (
    iter_run_type_registry_payload,
)
from src.smartcoach_mobile_coach.runner_profile.plan_workout_taxonomy import (
    iter_plan_workout_taxonomy_payload,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.goal_aligned_pace import (
    resolve_goal_aligned_status,
)
from src.services.training_plan.v2.race_distance_factory_v2 import (
    normalize_race_distance,
)
from src.smartcoach_mobile_coach.easy_kpi.efficiency_easy import (
    build_easy_efficiency_reference,
    efficiency_zones_chart_api_payload,
)
from src.smartcoach_mobile_coach.easy_kpi.hr_drift_easy import (
    build_easy_hr_drift_reference,
    hr_drift_zones_chart_api_payload,
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


def build_insights_easy_chart_authority_payload(
    recs: Optional[TrainingPaceRecommendations],
) -> dict[str, Any]:
    """Display authority for Insights Easy banner and chart footnotes (shared by /zones and /weekly-history)."""
    out: dict[str, Any] = {
        "pace_target_display": None,
        "hr_target_display": None,
        "hr_progress_z2_range_display": None,
        "insights_easy_banner": None,
    }
    if recs is None:
        return out

    pace_payload = _pace_progress_payload(recs.pace_progress)
    hr_payload = _hr_progress_payload(recs.hr_progress)

    if pace_payload is not None:
        target_easy = pace_payload.get("target_easy_pace")
        if isinstance(target_easy, dict):
            display = target_easy.get("display")
            if isinstance(display, str) and display.strip():
                out["pace_target_display"] = display.strip()

    if hr_payload is not None:
        target_display = hr_payload.get("target_display")
        if isinstance(target_display, str) and target_display.strip():
            out["hr_target_display"] = target_display.strip()
        z2 = hr_payload.get("target_hr_z2")
        if isinstance(z2, dict):
            lo, hi = z2.get("low"), z2.get("high")
            if lo is not None and hi is not None:
                out["hr_progress_z2_range_display"] = f"{int(lo)}–{int(hi)} bpm"

    if pace_payload is not None and hr_payload is not None:
        out["insights_easy_banner"] = {"subtitle": INSIGHTS_EASY_BANNER_SUBTITLE}

    return out


def build_insights_easy_global_kpi_chart_authority_payload() -> dict[str, Any]:
    """Global HR drift + efficiency chart authority (app-wide KPI bands; not profile-personalized)."""
    drift = build_easy_hr_drift_reference()
    eff = build_easy_efficiency_reference()
    return {
        "hr_drift_target_display": drift.target_display,
        "efficiency_goal_display": eff.goal_display,
        "zones": hr_drift_zones_chart_api_payload(drift.drift_zones_chart),
        "efficiency_zones": efficiency_zones_chart_api_payload(
            eff.efficiency_zones_chart
        ),
    }


def insights_easy_chart_authority_is_complete(authority: dict[str, Any]) -> bool:
    """True when both Easy HR and pace display strings are present."""
    pace = authority.get("pace_target_display")
    hr = authority.get("hr_target_display")
    return (
        isinstance(pace, str)
        and pace.strip() != ""
        and isinstance(hr, str)
        and hr.strip() != ""
    )


def build_insights_tempo_chart_authority_payload(
    recs: Optional[TrainingPaceRecommendations],
) -> dict[str, Any]:
    """Display authority for Insights Tempo banner and chart footnotes (shared by /zones and /weekly-history)."""
    out: dict[str, Any] = {
        "pace_target_display": None,
        "hr_target_display": None,
        "insights_tempo_banner": None,
    }
    if recs is None:
        return out

    pace_payload = _tempo_pace_progress_payload(recs.tempo_pace_progress)
    hr_payload = _tempo_hr_progress_payload(recs.tempo_hr_progress)

    if pace_payload is not None:
        target_display = pace_payload.get("target_display")
        if isinstance(target_display, str) and target_display.strip():
            out["pace_target_display"] = target_display.strip()
        else:
            target_tempo = pace_payload.get("target_tempo_pace")
            if isinstance(target_tempo, dict):
                display = target_tempo.get("display")
                if isinstance(display, str) and display.strip():
                    out["pace_target_display"] = display.strip()

    if hr_payload is not None:
        target_display = hr_payload.get("target_display")
        if isinstance(target_display, str) and target_display.strip():
            out["hr_target_display"] = target_display.strip()

    if pace_payload is not None:
        out["insights_tempo_banner"] = {"subtitle": INSIGHTS_TEMPO_BANNER_SUBTITLE}

    return out


def insights_tempo_chart_authority_is_complete(authority: dict[str, Any]) -> bool:
    """True when Tempo pace display string is present (banner + Avg Pace footnote)."""
    pace = authority.get("pace_target_display")
    return isinstance(pace, str) and pace.strip() != ""


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


def _tempo_hr_progress_payload(
    ref: Optional[TempoHrProgressReference],
) -> Optional[dict[str, Any]]:
    """Insights Tempo Avg HR chart authority (Z3 HR corridor + bilateral Y/O/R zones)."""
    if ref is None:
        return None
    return {
        "target_hr_z3": _hr_band_payload(ref.target_hr_z3),
        "target_display": ref.target_display,
        "hr_zones_chart": tempo_hr_progress_zones_chart_api_payload(ref.hr_zones_chart),
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
        "tempo_hr_progress": _tempo_hr_progress_payload(recs.tempo_hr_progress),
        "hr_progress": _hr_progress_payload(recs.hr_progress),
        "easy_gyor": _easy_gyor_payload(recs.easy_gyor),
    }
    return payload


def _pace_authorities_payload(
    profile: RunnerZoneProfileData,
    recs: Optional[TrainingPaceRecommendations],
) -> dict[str, Any]:
    """Explicit plan vs Insights pace authority contract."""
    plan_zones: dict[str, Any] = {}
    for key_name, pace_band in (
        ("z2", profile.pace_z2),
        ("z3", profile.pace_z3),
        ("z4", profile.pace_z4),
    ):
        band_payload = _pace_band_payload(pace_band)
        if band_payload is not None:
            plan_zones[key_name] = band_payload

    insights: dict[str, Any] = {
        "source": "marathon_goal",
        "target_time": recs.source_target_time if recs else None,
        "pace_progress": _pace_progress_payload(recs.pace_progress) if recs else None,
        "tempo_pace_progress": (
            _tempo_pace_progress_payload(recs.tempo_pace_progress) if recs else None
        ),
    }
    return {
        "plan": {
            "source": "activity_median",
            "pace_source": profile.pace_source,
            "zones": plan_zones if plan_zones else None,
        },
        "insights": insights,
    }


def _normalize_race_distance_for_inputs(race_distance: str | None) -> str | None:
    if race_distance is None or not str(race_distance).strip():
        return None
    return normalize_race_distance(str(race_distance))


def _zones_inputs_payload(
    profile: RunnerZoneProfileData,
    *,
    target_time: str | None,
    race_distance: str | None,
    training_pace_recommendations: Optional[TrainingPaceRecommendations],
) -> dict[str, Any]:
    has_goal_bands = (
        training_pace_recommendations is not None
        and training_pace_recommendations.goal_aligned_easy_pace is not None
    )
    return {
        "hrmax": profile.hrmax_used,
        "resting_hr": profile.resting_hr_used,
        "target_time": target_time,
        "race_distance": _normalize_race_distance_for_inputs(race_distance),
        "goal_aligned_status": resolve_goal_aligned_status(
            race_distance=race_distance,
            target_time=target_time,
            has_goal_bands=has_goal_bands,
        ),
    }


def runner_zone_profile_payload(
    profile: RunnerZoneProfileData,
    *,
    training_pace_recommendations: Optional[TrainingPaceRecommendations] = None,
    target_time: str | None = None,
    race_distance: str | None = None,
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

    easy_authority = build_insights_easy_chart_authority_payload(
        training_pace_recommendations
    )
    insights_easy_banner = easy_authority.get("insights_easy_banner")

    tempo_authority = build_insights_tempo_chart_authority_payload(
        training_pace_recommendations
    )
    insights_tempo_banner = tempo_authority.get("insights_tempo_banner")

    return {
        "calibrated": bool(profile.calibrated),
        "computed_at": profile.computed_at.isoformat() if profile.computed_at else None,
        "inputs": _zones_inputs_payload(
            profile,
            target_time=target_time,
            race_distance=race_distance,
            training_pace_recommendations=training_pace_recommendations,
        ),
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
        "run_type_registry": iter_run_type_registry_payload(),
        "plan_workout_taxonomy": iter_plan_workout_taxonomy_payload(),
        "pace_authorities": _pace_authorities_payload(
            profile, training_pace_recommendations
        ),
    }
