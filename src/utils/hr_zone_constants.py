"""
Standard Strava-compatible Heart Rate Zone Definitions

All HR zones are defined as percentages of maximum heart rate.
These zones are used consistently across the application for:
- Workout target HR assignment
- HR zone calculation from activity data
- Training plan generation
- Metrics and analytics

Zone Definitions:
- Z1: 50-60% (Recovery)
- Z2: 60-75% (Easy/Aerobic)
- Z3: 75-85% (Threshold/Steady-state)
- Z4: 85-95% (VO2 Max)
- Z5: 95-100% (Neuromuscular)

This file is the SINGLE SOURCE OF TRUTH for all HR zone constants.
No magic numbers should appear in service files - all constants must be here.
"""

from __future__ import annotations

from datetime import date
from typing import Optional, Tuple, Union

# Legacy: Strava-style zones (max HR percentage-based)
# Keep for backward compatibility
STRAVA_HR_ZONES = {
    "Z1": (0.50, 0.60),  # Recovery
    "Z2": (0.60, 0.75),  # Easy/Aerobic
    "Z3": (0.75, 0.85),  # Threshold/Steady-state
    "Z4": (0.85, 0.95),  # VO2 Max
    "Z5": (0.95, 1.00),  # Neuromuscular
}

# Zone thresholds for calculations (single values)
HR_ZONE_THRESHOLDS = {
    "Z1_MIN": 0.50,
    "Z1_MAX": 0.60,
    "Z2_MIN": 0.60,
    "Z2_MAX": 0.75,
    "Z3_MIN": 0.75,
    "Z3_MAX": 0.85,
    "Z4_MIN": 0.85,
    "Z4_MAX": 0.95,
    "Z5_MIN": 0.95,
    "Z5_MAX": 1.00,
}

# HRmax Estimation Configuration
# All constants for HRmax estimation from activities
HRMAX_ESTIMATION = {
    "MIN_ACTIVITIES_REQUIRED": 5,
    "MIN_ACTIVITIES_FOR_MEDIUM_CONFIDENCE": 10,
    "MIN_ACTIVITIES_FOR_HIGH_CONFIDENCE": 20,
    "MIN_DURATION_SECONDS": 600,  # 10 minutes
    "OUTLIER_STD_DEVIATIONS": 3,
    "PERCENTILE": 95,
    "MIN_FILTERED_VALUES": 3,
    "HRMAX_MIN": 120,
    "HRMAX_MAX": 220,
    "RESTING_HR_MIN": 35,
    "RESTING_HR_MAX": 110,
    "MIN_HRR": 30,  # Minimum Heart Rate Reserve
    "RECALC_DAYS_THRESHOLD": 30,  # Days before auto-recalc
    # If stored manual max HR exists and agrees with this band, do not persist/show
    # activity-based max_hr_auto when the estimate is farther away (avoids misleading
    # 95th-percentile values vs watch/Strava max).
    "HRMAX_AUTO_MAX_GAP_VS_MANUAL": 12,
    "HRMAX_PEAK_THRESHOLD": 2,  # bpm increase to trigger recalculation
    "AGE_FORMULA_BASE": 220,  # Standard "220 - age" formula for rough estimation
    "DEFAULT_FALLBACK_MAX_HR": 190,  # Conservative default when can't estimate from age or activities
    # Manual max HR rails vs birth_year (Tanaka predictor + margin).
    #
    # Tanaka et al. J Am Coll Cardiol 2001;37:153-156: HRmax ≈ 208 − 0.7×age for healthy adults
    # (narrower population mean than Fox 220−age). Individual variation remains large; accept a
    # ±MANUAL_HRMAX_MARGIN window, clamped to HRMAX_MIN / HRMAX_MAX for Karvonen + auto estimator.
    "TANAKA_HRMAX_INTERCEPT": 208.0,
    "TANAKA_HRMAX_AGE_COEFFICIENT": 0.7,
    "MANUAL_HRMAX_MARGIN_BPM": 35,
}

# Loose API guard only; onboarding route merges profile and applies manual_max_hr_bpm_bounds.
MANUAL_HR_SCHEMA_COARSE_MIN = 60
MANUAL_HR_SCHEMA_COARSE_MAX = 250

# Short coach-facing copy keyed by get_hr_calibration_status() reason_code.
HR_CALIBRATION_REASON_USER_HINTS: dict[str, str] = {
    "INSUFFICIENT_DATA": (
        "We need more runs with heart rate recorded—each at least about ten minutes moving "
        "time—and a few sessions that include harder work (tempo, hills, intervals, or a race) "
        "so we can see a realistic peak HR."
    ),
    "LOW_CONFIDENCE": (
        "We have some HR data, but it is not stable enough to lock zones yet. Add a few runs "
        "with clear harder efforts (not only easy mileage) so the estimate can firm up."
    ),
    "HRMAX_AUTO_NOT_TRUSTED": (
        "An activity-based max HR was not reliable enough to use. Set max HR manually from "
        "your watch or Strava, or keep logging varied runs with harder efforts and sync again."
    ),
    "ESTIMATION_NOT_AVAILABLE": (
        "Enough qualifying runs were counted, but we could not derive a saved auto max HR yet. "
        "Try syncing recent activities or add harder sessions; setting max HR manually is the "
        "fastest fix."
    ),
    "MANUAL_OUT_OF_RANGE": (
        "The max HR on file is outside the allowed range for your age. Update birth year "
        "and manual max HR in your profile—or use values from your watch / Strava."
    ),
    "UNKNOWN_UNCALIBRATED": (
        "Max HR is not available for personalized zones yet. Log more runs with HR—including "
        "some harder efforts—or enter max HR manually in your profile."
    ),
}


def manual_max_hr_bpm_bounds(
    birth_year: Optional[Union[int, float]],
    today: Optional[date] = None,
) -> Tuple[int, int]:
    """
    Inclusive ``[low, high]`` for validating *manual* ``max_hr_manual``.

    Uses Tanaka-equation midpoint ± margin when ``birth_year`` is known; otherwise the legacy
    flat ``HRMAX_MIN`` .. ``HRMAX_MAX`` envelope (typically 120–220).
    """
    legacy_lo = int(HRMAX_ESTIMATION["HRMAX_MIN"])
    legacy_hi = int(HRMAX_ESTIMATION["HRMAX_MAX"])
    if birth_year is None:
        return legacy_lo, legacy_hi
    try:
        by_int = int(birth_year)
    except (TypeError, ValueError):
        return legacy_lo, legacy_hi

    anchor = today or date.today()
    age = anchor.year - by_int
    age = max(13, min(110, age))

    intercept = float(HRMAX_ESTIMATION["TANAKA_HRMAX_INTERCEPT"])
    coeff = float(HRMAX_ESTIMATION["TANAKA_HRMAX_AGE_COEFFICIENT"])
    margin = int(HRMAX_ESTIMATION["MANUAL_HRMAX_MARGIN_BPM"])
    predicted = round(intercept - coeff * age)
    lo = max(legacy_lo, predicted - margin)
    hi = min(legacy_hi, predicted + margin)
    if lo > hi:
        return legacy_lo, legacy_hi
    return lo, hi


def hr_calibration_reason_user_hint(reason_code: Optional[str]) -> str:
    """Return stable user-facing coaching copy for a calibration reason code."""
    if not reason_code:
        return HR_CALIBRATION_REASON_USER_HINTS["UNKNOWN_UNCALIBRATED"]
    return HR_CALIBRATION_REASON_USER_HINTS.get(
        reason_code,
        HR_CALIBRATION_REASON_USER_HINTS["UNKNOWN_UNCALIBRATED"],
    )


# Karvonen Zone Percentages (HRR-based)
# These are percentages of Heart Rate Reserve (HRR), not max HR
KARVONEN_ZONE_PERCENTAGES = {
    "Z1": (0.50, 0.60),
    "Z2": (0.60, 0.75),
    "Z3": (0.75, 0.85),
    "Z4": (0.85, 0.95),
    "Z5": (0.95, 1.00),
}

# Easy Run Classification Thresholds
# Easy-run classification thresholds (used by execution_analytics).
# Canonical owner: execution_analytics/thresholds.py
EASY_RUN_THRESHOLDS = {
    "MIN_DURATION_SECONDS": 1800,  # 30 minutes — runs shorter than this are excluded
    "MIN_EASY_PCT": 0.70,  # 70% of splits must be at or below Z2 ceiling
}

# ---------------------------------------------------------------------------
# Coaching Preferences
# ---------------------------------------------------------------------------

# Controlled vocabulary for metrics the user can request or the level defaults to.
# Used for validation in save_coach_preference and prompt injection.
ALLOWED_METRICS = [
    "summary",
    "easy_pct",
    "hr_drift",
    "z2_adherence",
    "z2_pace",
    "efficiency",
    "pace_spread",
]

COACHING_LEVEL_DEFAULTS = {
    "beginner": {
        "metrics": ["summary", "easy_pct"],
        "tone": (
            "Encouraging and simple. Do NOT use terms like 'HR drift', "
            "'Z2 adherence', or 'efficiency'. Translate all metrics into "
            "plain language the user can feel (e.g. 'your effort stayed "
            "steady', 'you stayed in your easy zone')."
        ),
    },
    "intermediate": {
        "metrics": ["summary", "easy_pct", "hr_drift", "z2_pace"],
        "tone": (
            "Supportive with light education. Introduce metric concepts "
            "in plain English with a brief explanation on first mention "
            "(e.g. 'your heart rate stayed steady — only 3% drift, which "
            "means your body handled the effort well')."
        ),
    },
    "advanced": {
        "metrics": [
            "summary",
            "easy_pct",
            "hr_drift",
            "z2_adherence",
            "efficiency",
            "pace_spread",
        ],
        "tone": (
            "Direct and data-rich. Use metric names, values, and band "
            "colors directly (e.g. 'HR drift: 3.1% (green). Z2 adherence: "
            "92%.'). Keep it concise."
        ),
    },
}

VERBOSITY_RULES = {
    "minimal": "1-2 sentences maximum. Only the priority metrics.",
    "normal": "Short paragraph. Default metrics for the level plus brief coaching insight.",
    "detailed": "Full explanation with all available metrics, comparisons, and coaching context.",
}

# Allowed values for preference_scope (future-proof for training summaries, alerts, etc.)
PREFERENCE_SCOPES = ["run_summary", "training_summary", "global"]

# ---------------------------------------------------------------------------
# Weekly Insights — KPI Bands (R/O/Y/G)
# ---------------------------------------------------------------------------

# HR Drift: absolute thresholds (well-established in coaching science).
# Lower drift = more aerobic stability. Canonical logic lives in easy_kpi.hr_drift_easy.
from src.smartcoach_mobile_coach.easy_kpi.hr_drift_easy import (
    DEFAULT_HR_DRIFT_BAND_CONFIG,
    build_easy_hr_drift_zones_chart,
    classify_easy_hr_drift,
    hr_drift_zones_chart_api_payload,
)
from src.smartcoach_mobile_coach.easy_kpi.efficiency_easy import (
    DEFAULT_EFFICIENCY_BAND_CONFIG,
    build_easy_efficiency_zones_chart,
    classify_easy_efficiency,
    efficiency_zones_chart_api_payload,
)

HR_DRIFT_BANDS = {
    "green_max": DEFAULT_HR_DRIFT_BAND_CONFIG.green_max,
    "yellow_max": DEFAULT_HR_DRIFT_BAND_CONFIG.yellow_max,
    "orange_max": DEFAULT_HR_DRIFT_BAND_CONFIG.orange_max,
}


def hr_drift_band_from_pct(value: float | None) -> str | None:
    """
    Map per-run or weekly HR drift % to the same R/O/Y/G band as Insights.
    Delegates to ``easy_kpi.hr_drift_easy.classify_easy_hr_drift``.
    """
    return classify_easy_hr_drift(drift_pct=value)


def hr_drift_band_zones_chart() -> list[dict[str, float | str]]:
    """
    HR drift % bands for Weekly Insights charts and coach tools.
    Delegates to ``easy_kpi.hr_drift_easy``.
    """
    return hr_drift_zones_chart_api_payload(build_easy_hr_drift_zones_chart())


# Aerobic efficiency (weekly easy runs): global coaching bands on
# speed_mph/avg_hr*100 (mi/hr per 100 bpm). Higher = better.
# Canonical logic lives in easy_kpi.efficiency_easy.
AEROBIC_EFFICIENCY_BANDS = {
    "orange_min": DEFAULT_EFFICIENCY_BAND_CONFIG.orange_min,
    "yellow_min": DEFAULT_EFFICIENCY_BAND_CONFIG.yellow_min,
    "green_min": DEFAULT_EFFICIENCY_BAND_CONFIG.green_min,
}


def aerobic_efficiency_band_from_value(value: float | None) -> str | None:
    """
    Map weekly aerobic efficiency scalar to R/O/Y/G (same semantics as Insights).
    Delegates to ``easy_kpi.efficiency_easy.classify_easy_efficiency``.
    """
    return classify_easy_efficiency(efficiency=value)


def aerobic_efficiency_band_zones_chart() -> list[dict[str, float | str]]:
    """
    Y-axis bands for weekly aerobic efficiency charts and coach tools.
    Delegates to ``easy_kpi.efficiency_easy``.
    """
    return efficiency_zones_chart_api_payload(build_easy_efficiency_zones_chart())


# Z2 pace uses trend-based bands because absolute pace is user-specific.
# Efficiency / HR drift use easy_kpi global bands (see imports above).
# The delta (%) vs the prior-week value determines the Z2 band.
# "worse_pct" thresholds represent how much WORSE the current
# value is compared to the prior week (positive = decline).
TREND_BAND_THRESHOLDS = {
    "green_max_worse_pct": 0.0,
    "yellow_max_worse_pct": 3.0,
    "orange_max_worse_pct": 8.0,
}

# Overall score: "worst-of-three" with a 2-week persistence rule.
# A single bad week caps at yellow; same KPI red for 2+ consecutive
# weeks promotes overall to red.
OVERALL_SCORE_RULES = {
    "consecutive_red_weeks_for_overall_red": 2,
}

# HR Zone Issues Enum (used in status endpoint)
# These are the canonical issue codes that can block zone calculation
HR_ZONE_ISSUES = [
    "strava_not_connected",
    "resting_hr_missing",
    "not_enough_activities",
    "max_hr_missing",
    "hrmax_cannot_estimate",
    "unknown",
]

# Next Action Priority (canonical order for UX)
# When multiple actions are possible, use this priority to determine next_action
NEXT_ACTION_PRIORITY = [
    "connect_strava",  # 1. Highest priority - must connect Strava first
    "add_resting_hr",  # 2. Resting HR is required for Karvonen zones
    "run_more_activities",  # 3. Need more data for HRmax estimation
    "view_zones",  # 4. Zones are ready, user can view them
    "improve_accuracy",  # 5. Lowest priority - zones work but could be better
]

# Accuracy Tiers (UX indicator, not physiological measure)
# This indicates user experience expectations, NOT scientific zone reliability
ACCURACY_TIERS = {
    "HIGH": "User RHR provided + high confidence HRmax",
    "MEDIUM": "Estimated RHR OR medium/high confidence HRmax",
    "LOW": "Fallback to simple %maxHR calculation",
}
# Note: Accuracy tier is a UX indicator to set user expectations.
# Do NOT treat as a physiological measure of zone quality.

# Resting HR Estimation Configuration
RESTING_HR_ESTIMATION = {
    "MIN_RHR_UPDATE_INTERVAL_DAYS": 30,  # Don't re-estimate if updated < 30 days ago
    "ACCURACY_DISCLAIMER": (
        "Population-based estimates are coarse defaults intended only to "
        "unblock zone setup. For best accuracy, measure your resting HR "
        "manually (first thing in the morning after waking)."
    ),
    # Age-based resting HR estimates (population averages by age range)
    # Source: General population data - these are safe defaults, not precise
    "AGE_ESTIMATES": {
        "18-25": 72,  # Young adults
        "26-35": 72,  # Young adults
        "36-45": 73,  # Early middle age
        "46-55": 74,  # Middle age
        "56-65": 74,  # Late middle age
        "66-75": 73,  # Older adults (slightly lower due to less activity)
        "76+": 72,  # Seniors
    },
    # Default fallback if age cannot be determined
    "DEFAULT_RESTING_HR": 70,
}

# Writable resting HR sources (profile save / onboarding). ESTIMATED is legacy read-only.
ALLOWED_RESTING_HR_WRITE_SOURCES = frozenset({"USER", "APPLE_HEALTH"})
