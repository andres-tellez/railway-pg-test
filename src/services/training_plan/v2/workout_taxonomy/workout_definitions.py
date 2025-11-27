"""
Global Workout Definitions - Single Source of Truth for All Workout Types
=========================================================================

PURPOSE
-------
This file defines ALL workout types used across the entire application.
It is race-agnostic, user-agnostic, and reusable across:
- Step 6 (workout placement)
- Step 7 (workout details)
- Step 8 (validation)
- Frontend/UI (labels, descriptions)
- Testing (expected values)

STRUCTURE
---------
Each workout type has:
- intensity: How hard the effort is (very_easy, easy, moderate, hard, very_hard)
- purpose: What physiological system it trains
- recovery_days: Days of easy running needed after this workout
- is_quality: Whether this is a "hard" workout that needs spacing
- default_distribution_pct: Suggested % of weekly mileage (None = calculated)
- description: Human-readable description for UI
- pace_guidance: Short pace instruction for UI
- ideal_for_races: Which race distances benefit most (for future filtering)

INVARIANTS (DO NOT VIOLATE)
---------------------------
1. Every workout type MUST have all fields defined
2. is_quality=True workouts MUST have recovery_days >= 2
3. Only one "long_run" type should exist
4. Intensity values MUST be one of: very_easy, easy, moderate, hard, very_hard

HOW TO ADD A NEW WORKOUT TYPE
-----------------------------
1. Add entry to WORKOUT_DEFINITIONS dict below
2. Ensure all required fields are populated
3. Update weekly_templates.py if the workout should appear in templates
4. Run tests to verify

Author: SmartCoach Development Team
Last Updated: November 2025
"""

from typing import Dict, Any, Optional, List

# =============================================================================
# WORKOUT DEFINITIONS - The core taxonomy
# =============================================================================

WORKOUT_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    # -------------------------------------------------------------------------
    # LONG RUN - The anchor of every training week
    # -------------------------------------------------------------------------
    "long_run": {
        "intensity": "easy",
        "purpose": "endurance",
        "recovery_days": 2,
        "is_quality": False,  # Not a "hard" workout despite length
        "default_distribution_pct": None,  # Determined by spine in Step 5
        "description": "Steady easy long run for aerobic endurance",
        "pace_guidance": "Easy",
        "ideal_for_races": ["5k", "10k", "half", "marathon"],
        "detail_archetype": "LONG",  # Step 7 segment generator to use
    },
    
    # -------------------------------------------------------------------------
    # EASY - Recovery and base building
    # -------------------------------------------------------------------------
    "easy": {
        "intensity": "easy",
        "purpose": "recovery",
        "recovery_days": 0,
        "is_quality": False,
        "default_distribution_pct": None,  # Fills remainder after other workouts
        "description": "Easy aerobic run for recovery and base building",
        "pace_guidance": "Easy",
        "ideal_for_races": ["5k", "10k", "half", "marathon"],
        "detail_archetype": "EASY",
    },
    
    # -------------------------------------------------------------------------
    # RECOVERY - Even easier than easy, for active recovery
    # -------------------------------------------------------------------------
    "recovery": {
        "intensity": "very_easy",
        "purpose": "active_recovery",
        "recovery_days": 0,
        "is_quality": False,
        "default_distribution_pct": 0.08,
        "description": "Very easy jog for active recovery",
        "pace_guidance": "Very Easy (slower than easy pace)",
        "ideal_for_races": ["5k", "10k", "half", "marathon"],
        "detail_archetype": "EASY",  # Use easy generator with shorter distance
    },
    
    # -------------------------------------------------------------------------
    # STEADY - Controlled aerobic development
    # -------------------------------------------------------------------------
    "steady": {
        "intensity": "moderate",
        "purpose": "aerobic",
        "recovery_days": 1,
        "is_quality": False,  # Moderate, not quality
        "default_distribution_pct": 0.15,
        "description": "Controlled aerobic run at steady effort; not hard",
        "pace_guidance": "Steady (comfortably moderate)",
        "ideal_for_races": ["10k", "half", "marathon"],
        "detail_archetype": "STEADY",
    },
    
    # -------------------------------------------------------------------------
    # TEMPO - Lactate threshold development
    # -------------------------------------------------------------------------
    "tempo": {
        "intensity": "hard",
        "purpose": "lactate_threshold",
        "recovery_days": 2,
        "is_quality": True,
        "default_distribution_pct": 0.10,
        "description": "Sustained effort at lactate threshold pace",
        "pace_guidance": "Tempo (comfortably hard, can speak in short phrases)",
        "ideal_for_races": ["10k", "half", "marathon"],
        "detail_archetype": "TEMPO",  # NEW: Continuous tempo block
    },
    
    # -------------------------------------------------------------------------
    # INTERVALS - VO2max development
    # -------------------------------------------------------------------------
    "intervals": {
        "intensity": "very_hard",
        "purpose": "vo2max",
        "recovery_days": 2,
        "is_quality": True,
        "default_distribution_pct": 0.07,
        "description": "High-intensity repeats with recovery jogs between",
        "pace_guidance": "Interval (hard effort, 3-5 min repeats)",
        "ideal_for_races": ["5k", "10k", "half"],
        "detail_archetype": "INTERVALS",  # NEW: Repeats with recovery
    },
    
    # -------------------------------------------------------------------------
    # HILLS - Strength and power development
    # -------------------------------------------------------------------------
    "hills": {
        "intensity": "hard",
        "purpose": "strength",
        "recovery_days": 2,
        "is_quality": True,
        "default_distribution_pct": 0.08,
        "description": "Hill repeats for running-specific strength and power",
        "pace_guidance": "Hard effort uphill, easy jog recovery down",
        "ideal_for_races": ["5k", "10k", "half", "marathon"],
        "detail_archetype": "HILLS",  # Use intervals pattern with hill notes
    },
    
    # -------------------------------------------------------------------------
    # THRESHOLD - Similar to tempo but shorter/harder intervals
    # -------------------------------------------------------------------------
    "threshold": {
        "intensity": "hard",
        "purpose": "lactate_threshold",
        "recovery_days": 2,
        "is_quality": True,
        "default_distribution_pct": 0.08,
        "description": "Cruise intervals at threshold pace with short recovery",
        "pace_guidance": "Threshold (slightly faster than tempo)",
        "ideal_for_races": ["10k", "half", "marathon"],
        "detail_archetype": "TEMPO",  # Use tempo generator (cruise intervals)
    },
    
    # -------------------------------------------------------------------------
    # FARTLEK - Unstructured speed play
    # -------------------------------------------------------------------------
    "fartlek": {
        "intensity": "moderate",
        "purpose": "aerobic_speed",
        "recovery_days": 1,
        "is_quality": False,  # Less structured, moderate stress
        "default_distribution_pct": 0.10,
        "description": "Unstructured speed play mixing easy and moderate efforts",
        "pace_guidance": "Varied (mix of easy and moderate surges)",
        "ideal_for_races": ["5k", "10k", "half"],
        "detail_archetype": "STEADY",  # Use steady with fartlek cues
    },
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_workout_definition(workout_type: str) -> Dict[str, Any]:
    """
    Get the full definition for a workout type.
    
    Args:
        workout_type: The workout type key (e.g., "tempo", "easy")
        
    Returns:
        Dict with all workout properties, or empty dict if not found
    """
    return WORKOUT_DEFINITIONS.get(workout_type, {})


def is_quality_workout(workout_type: str) -> bool:
    """
    Check if a workout is a "quality" (hard) workout.
    
    Quality workouts:
    - Require spacing (no back-to-back)
    - Need recovery days after
    - Should be limited per week
    
    Args:
        workout_type: The workout type key
        
    Returns:
        True if this is a quality workout
    """
    return WORKOUT_DEFINITIONS.get(workout_type, {}).get("is_quality", False)


def get_recovery_days(workout_type: str) -> int:
    """
    Get the number of easy days recommended after this workout.
    
    Args:
        workout_type: The workout type key
        
    Returns:
        Number of recovery days needed (0-2 typically)
    """
    return WORKOUT_DEFINITIONS.get(workout_type, {}).get("recovery_days", 0)


def get_detail_archetype(workout_type: str) -> str:
    """
    Get the detail archetype for Step 7 segment generation.
    
    Archetypes tell Pass4 which segment generator to use:
    - EASY: Simple easy run
    - STEADY: Controlled aerobic run
    - ENDURANCE: Medium-long run
    - LONG: Long run with optional MP finish
    - TEMPO: Continuous tempo block
    - INTERVALS: Repeats with recovery
    - HILLS: Hill repeats
    
    Args:
        workout_type: The workout type key
        
    Returns:
        Archetype string, defaults to "EASY" if not found
    """
    return WORKOUT_DEFINITIONS.get(workout_type, {}).get("detail_archetype", "EASY")


def get_intensity(workout_type: str) -> str:
    """
    Get the intensity level of a workout.
    
    Intensity levels:
    - very_easy: Recovery pace
    - easy: Conversational pace
    - moderate: Steady, controlled effort
    - hard: Challenging but sustainable
    - very_hard: Near maximal effort
    
    Args:
        workout_type: The workout type key
        
    Returns:
        Intensity string, defaults to "easy" if not found
    """
    return WORKOUT_DEFINITIONS.get(workout_type, {}).get("intensity", "easy")


def get_quality_workouts() -> List[str]:
    """
    Get list of all quality workout types.
    
    Returns:
        List of workout type keys that are quality workouts
    """
    return [k for k, v in WORKOUT_DEFINITIONS.items() if v.get("is_quality", False)]


def get_workouts_for_race(race_type: str) -> List[str]:
    """
    Get workout types ideal for a specific race distance.
    
    Args:
        race_type: Race type (e.g., "marathon", "half", "10k", "5k")
        
    Returns:
        List of workout type keys ideal for this race
    """
    return [
        k for k, v in WORKOUT_DEFINITIONS.items()
        if race_type in v.get("ideal_for_races", [])
    ]


# =============================================================================
# VALIDATION (run at import time)
# =============================================================================

def _validate_definitions() -> None:
    """Validate all workout definitions have required fields."""
    required_fields = [
        "intensity",
        "purpose", 
        "recovery_days",
        "is_quality",
        "description",
        "pace_guidance",
        "ideal_for_races",
        "detail_archetype",  # NEW: Required for Step 7 segment generation
    ]
    
    valid_intensities = {"very_easy", "easy", "moderate", "hard", "very_hard"}
    valid_archetypes = {"EASY", "STEADY", "ENDURANCE", "LONG", "TEMPO", "INTERVALS", "HILLS"}
    
    for workout_type, defn in WORKOUT_DEFINITIONS.items():
        # Check required fields
        for field in required_fields:
            assert field in defn, (
                f"Workout '{workout_type}' missing required field '{field}'"
            )
        
        # Validate intensity value
        assert defn["intensity"] in valid_intensities, (
            f"Workout '{workout_type}' has invalid intensity '{defn['intensity']}'"
        )
        
        # Validate detail_archetype
        assert defn["detail_archetype"] in valid_archetypes, (
            f"Workout '{workout_type}' has invalid detail_archetype '{defn['detail_archetype']}'"
        )
        
        # Quality workouts must have recovery days
        if defn["is_quality"]:
            assert defn["recovery_days"] >= 2, (
                f"Quality workout '{workout_type}' must have recovery_days >= 2"
            )


# Run validation at import
_validate_definitions()

