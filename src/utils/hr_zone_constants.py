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
    "HRMAX_PEAK_THRESHOLD": 2,  # bpm increase to trigger recalculation
}

# Karvonen Zone Percentages (HRR-based)
# These are percentages of Heart Rate Reserve (HRR), not max HR
KARVONEN_ZONE_PERCENTAGES = {
    "Z1": (0.50, 0.60),
    "Z2": (0.60, 0.70),
    "Z3": (0.70, 0.80),
    "Z4": (0.80, 0.90),
    "Z5": (0.90, 1.00),
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
