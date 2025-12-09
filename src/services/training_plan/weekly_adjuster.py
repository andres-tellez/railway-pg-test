"""
Weekly Adjuster Service

Purpose:
    Adjust pace seed based on week completion logs (completion rate + RPE, optionally HR).
    Used in rolling mode to adapt paces weekly based on runner feedback.

Integration:
    Called when rebuilding upcoming week in rolling mode.
    Takes previous week's logs (from database or user input) and adjusts pace zones.

Author: SmartCoach Development Team
Last Updated: January 2026
"""

# Re-export from pace module for backward compatibility
from src.services.training_plan.pace import (
    adjust_pace_seed,
    WeekLogRun,
    PaceSeed,
)

# Alias for backward compatibility
adjust_seed_from_week = adjust_pace_seed
