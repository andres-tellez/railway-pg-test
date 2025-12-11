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
"""

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
