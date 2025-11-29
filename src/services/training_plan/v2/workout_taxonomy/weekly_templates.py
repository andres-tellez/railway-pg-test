"""
Weekly Templates - Phase-Aware Workout Structure by Race Type and Frequency
===========================================================================

PURPOSE
-------
This file defines the STRUCTURE of training weeks - which workout types appear
on which days, organized by:
1. Race type (marathon, half, 10k, 5k)
2. Training frequency (3, 4, 5, or 6 days per week)
3. Training phase (Base, Build, Peak, Taper)

This is based on established coaching methodologies:
- Pfitzinger (Advanced Marathoning)
- Daniels (Running Formula)
- Hansons (Marathon Method)
- McMillan (Run-Specific Training)

STRUCTURE
---------
WEEKLY_TEMPLATES = {
    "race_type": {
        frequency: {
            "phase": [workout_type, workout_type, ..., "long_run"]
        }
    }
}

Templates are ORDERED lists where:
- Last element is always "long_run"
- Order represents suggested day sequence (not actual days)
- Actual day mapping happens in workout_placement_engine.py

INVARIANTS (DO NOT VIOLATE)
---------------------------
1. Every template MUST end with "long_run"
2. Template length MUST equal frequency
3. All workout types MUST exist in workout_definitions.py
4. Quality workouts should not be adjacent in the template
5. Taper templates should have NO quality workouts

HOW TO ADD A NEW RACE TYPE
--------------------------
1. Add entry to WEEKLY_TEMPLATES with race type key
2. Populate all frequency/phase combinations
3. Optionally add scenario overrides in SCENARIO_OVERRIDES
4. Run tests to verify

HOW TO MODIFY A TEMPLATE
------------------------
1. Find the race_type/frequency/phase combination
2. Update the workout list (maintain length = frequency)
3. Ensure last element is "long_run"
4. Ensure no adjacent quality workouts
5. Run tests to verify

Author: SmartCoach Development Team
Last Updated: November 2025

METHODOLOGY NOTES
-----------------
Base Phase:  Focus on aerobic development, no speedwork
Build Phase: Introduce threshold/tempo work, maintain aerobic base
Peak Phase:  Race-specific intensity, maintain but don't increase volume
Taper Phase: Reduce volume and intensity, maintain leg turnover
"""

from typing import Dict, List, Optional

# =============================================================================
# WEEKLY TEMPLATES - Organized by race_type > frequency > phase
# =============================================================================

WEEKLY_TEMPLATES: Dict[str, Dict[int, Dict[str, List[str]]]] = {
    # =========================================================================
    # MARATHON - Fully implemented
    # =========================================================================
    "marathon": {
        # ---------------------------------------------------------------------
        # 3-day plans (minimal frequency)
        # ---------------------------------------------------------------------
        3: {
            "Base": ["easy", "easy", "long_run"],
            "Build": ["tempo", "easy", "long_run"],
            "Peak": ["intervals", "easy", "long_run"],
            "Taper": ["easy", "easy", "long_run"],
        },
        # ---------------------------------------------------------------------
        # 4-day plans (common recreational runner frequency)
        # ---------------------------------------------------------------------
        4: {
            "Base": ["easy", "steady", "easy", "long_run"],
            "Build": ["tempo", "easy", "steady", "long_run"],
            "Peak": ["intervals", "easy", "tempo", "long_run"],
            "Taper": ["easy", "easy", "easy", "long_run"],
        },
        # ---------------------------------------------------------------------
        # 5-day plans (serious recreational/sub-elite)
        # ---------------------------------------------------------------------
        5: {
            "Base": ["easy", "steady", "easy", "easy", "long_run"],
            "Build": ["tempo", "easy", "steady", "easy", "long_run"],
            "Peak": ["intervals", "easy", "tempo", "easy", "long_run"],
            "Taper": ["easy", "easy", "easy", "easy", "long_run"],
        },
        # ---------------------------------------------------------------------
        # 6-day plans (competitive runners)
        # ---------------------------------------------------------------------
        6: {
            "Base": ["easy", "steady", "easy", "steady", "easy", "long_run"],
            "Build": ["tempo", "easy", "steady", "threshold", "easy", "long_run"],
            "Peak": ["intervals", "easy", "steady", "tempo", "easy", "long_run"],
            "Taper": ["easy", "easy", "easy", "easy", "easy", "long_run"],
        },
    },
    # =========================================================================
    # HALF MARATHON - Fully implemented
    # More tempo/threshold focus than marathon, less pure endurance
    # =========================================================================
    "half": {
        # ---------------------------------------------------------------------
        # 3-day plans (minimal frequency)
        # ---------------------------------------------------------------------
        3: {
            "Base": ["easy", "steady", "long_run"],
            "Build": ["tempo", "easy", "long_run"],
            "Peak": ["intervals", "easy", "long_run"],
            "Taper": ["easy", "easy", "long_run"],
        },
        # ---------------------------------------------------------------------
        # 4-day plans (common recreational runner frequency)
        # ---------------------------------------------------------------------
        4: {
            "Base": ["easy", "steady", "easy", "long_run"],
            "Build": ["tempo", "easy", "steady", "long_run"],
            "Peak": ["intervals", "easy", "tempo", "long_run"],
            "Taper": ["easy", "easy", "easy", "long_run"],
        },
        # ---------------------------------------------------------------------
        # 5-day plans (serious recreational/sub-elite)
        # ---------------------------------------------------------------------
        5: {
            "Base": ["easy", "steady", "easy", "easy", "long_run"],
            "Build": ["tempo", "easy", "steady", "easy", "long_run"],
            "Peak": ["intervals", "easy", "tempo", "easy", "long_run"],
            "Taper": ["easy", "easy", "easy", "easy", "long_run"],
        },
        # ---------------------------------------------------------------------
        # 6-day plans (competitive runners)
        # ---------------------------------------------------------------------
        6: {
            "Base": ["easy", "steady", "easy", "steady", "easy", "long_run"],
            "Build": ["tempo", "easy", "steady", "threshold", "easy", "long_run"],
            "Peak": ["intervals", "easy", "steady", "tempo", "easy", "long_run"],
            "Taper": ["easy", "easy", "easy", "easy", "easy", "long_run"],
        },
    },
    # =========================================================================
    # 10K - Placeholder for future implementation
    # More intervals/VO2max focus, shorter long runs
    # =========================================================================
    "10k": {
        # To be implemented - example structure:
        # 4: {
        #     "Base":  ["easy", "fartlek", "easy", "long_run"],
        #     "Build": ["intervals", "easy", "tempo", "long_run"],
        #     "Peak":  ["intervals", "easy", "threshold", "long_run"],
        #     "Taper": ["easy", "easy", "easy", "long_run"],
        # },
    },
    # =========================================================================
    # 5K - Placeholder for future implementation
    # Heavy intervals/speed focus, shorter long runs
    # =========================================================================
    "5k": {
        # To be implemented - example structure:
        # 4: {
        #     "Base":  ["easy", "fartlek", "easy", "long_run"],
        #     "Build": ["intervals", "easy", "intervals", "long_run"],
        #     "Peak":  ["intervals", "easy", "tempo", "long_run"],
        #     "Taper": ["easy", "easy", "easy", "long_run"],
        # },
    },
}


# =============================================================================
# SCENARIO OVERRIDES - Modify templates for special situations
# =============================================================================

SCENARIO_OVERRIDES: Dict[str, Dict[str, Dict[int, Dict[str, List[str]]]]] = {
    # -------------------------------------------------------------------------
    # INJURY-SAFE: Reduce intensity, avoid intervals
    # -------------------------------------------------------------------------
    "injury_safe": {
        "marathon": {
            3: {
                "Build": ["steady", "easy", "long_run"],  # No tempo
                "Peak": ["tempo", "easy", "long_run"],  # Tempo instead of intervals
            },
            4: {
                "Build": ["steady", "easy", "steady", "long_run"],
                "Peak": ["tempo", "easy", "steady", "long_run"],
            },
            5: {
                "Build": ["steady", "easy", "steady", "easy", "long_run"],
                "Peak": ["tempo", "easy", "steady", "easy", "long_run"],
            },
        },
        "half": {},  # Placeholder
        "10k": {},  # Placeholder
        "5k": {},  # Placeholder
    },
    # -------------------------------------------------------------------------
    # RETURNING-TO-RUNNING: Very conservative, minimal intensity
    # -------------------------------------------------------------------------
    "returning_to_running": {
        "marathon": {
            3: {
                "Base": ["easy", "easy", "long_run"],
                "Build": ["easy", "steady", "long_run"],  # Very conservative
                "Peak": ["steady", "easy", "long_run"],  # No intervals
                "Taper": ["easy", "easy", "long_run"],
            },
            4: {
                "Base": ["easy", "easy", "easy", "long_run"],
                "Build": ["easy", "steady", "easy", "long_run"],
                "Peak": ["steady", "easy", "steady", "long_run"],
                "Taper": ["easy", "easy", "easy", "long_run"],
            },
            5: {
                "Base": ["easy", "easy", "easy", "easy", "long_run"],
                "Build": ["easy", "steady", "easy", "easy", "long_run"],
                "Peak": ["steady", "easy", "steady", "easy", "long_run"],
                "Taper": ["easy", "easy", "easy", "easy", "long_run"],
            },
        },
        "half": {},
        "10k": {},
        "5k": {},
    },
    # -------------------------------------------------------------------------
    # HILLS-FOCUS: Include hill workouts for hilly race courses
    # -------------------------------------------------------------------------
    "hills_focus": {
        "marathon": {
            4: {
                "Build": ["hills", "easy", "steady", "long_run"],
                "Peak": ["intervals", "easy", "hills", "long_run"],
            },
            5: {
                "Build": ["hills", "easy", "steady", "easy", "long_run"],
                "Peak": ["intervals", "easy", "hills", "easy", "long_run"],
            },
        },
        "half": {},
        "10k": {},
        "5k": {},
    },
    # -------------------------------------------------------------------------
    # TIME-CONSTRAINED: More aggressive intensity to compensate for less time
    # -------------------------------------------------------------------------
    "time_constrained": {
        "marathon": {
            3: {
                "Build": ["tempo", "easy", "long_run"],
                "Peak": ["intervals", "tempo", "long_run"],  # Two quality sessions
            },
            4: {
                "Build": ["tempo", "easy", "threshold", "long_run"],
                "Peak": ["intervals", "easy", "tempo", "long_run"],
            },
        },
        "half": {},
        "10k": {},
        "5k": {},
    },
}


# =============================================================================
# TEMPLATE LOOKUP FUNCTION
# =============================================================================


def get_template(
    race_type: str,
    frequency: int,
    phase: str,
    scenario: Optional[str] = None,
) -> List[str]:
    """
    Get the workout template for given parameters.

    Lookup order:
    1. Check scenario override (if scenario provided)
    2. Fall back to default race_type template
    3. Fall back to marathon template (if race_type not implemented)
    4. Fall back to generic template (all easy + long_run)

    Args:
        race_type: Race distance ("marathon", "half", "10k", "5k")
        frequency: Training days per week (3, 4, 5, or 6)
        phase: Training phase ("Base", "Build", "Peak", "Taper")
        scenario: Optional scenario override ("injury_safe", etc.)

    Returns:
        List of workout types for the week, ending with "long_run"
    """
    # 1. Check scenario override first
    if scenario and scenario in SCENARIO_OVERRIDES:
        scenario_templates = SCENARIO_OVERRIDES[scenario]
        race_overrides = scenario_templates.get(race_type, {})
        freq_overrides = race_overrides.get(frequency, {})
        if phase in freq_overrides:
            return freq_overrides[phase].copy()

    # 2. Try race-specific template
    race_templates = WEEKLY_TEMPLATES.get(race_type, {})
    freq_templates = race_templates.get(frequency, {})
    if phase in freq_templates:
        return freq_templates[phase].copy()

    # 3. Fall back to marathon template (most complete)
    if race_type != "marathon":
        marathon_templates = WEEKLY_TEMPLATES.get("marathon", {})
        marathon_freq = marathon_templates.get(frequency, {})
        if phase in marathon_freq:
            return marathon_freq[phase].copy()

    # 4. Ultimate fallback: all easy + long_run
    return ["easy"] * (frequency - 1) + ["long_run"]


def get_available_frequencies(race_type: str) -> List[int]:
    """
    Get list of implemented frequencies for a race type.

    Args:
        race_type: Race distance

    Returns:
        List of available frequency options (e.g., [3, 4, 5, 6])
    """
    race_templates = WEEKLY_TEMPLATES.get(race_type, {})
    return sorted(race_templates.keys())


def get_available_phases(race_type: str, frequency: int) -> List[str]:
    """
    Get list of implemented phases for a race type and frequency.

    Args:
        race_type: Race distance
        frequency: Training days per week

    Returns:
        List of available phases (e.g., ["Base", "Build", "Peak", "Taper"])
    """
    race_templates = WEEKLY_TEMPLATES.get(race_type, {})
    freq_templates = race_templates.get(frequency, {})
    return list(freq_templates.keys())


# =============================================================================
# VALIDATION (run at import time)
# =============================================================================


def _validate_templates() -> None:
    """Validate all templates have correct structure."""
    from .workout_definitions import WORKOUT_DEFINITIONS

    valid_workout_types = set(WORKOUT_DEFINITIONS.keys())

    def validate_template(template: List[str], context: str) -> None:
        """Validate a single template."""
        # Must end with long_run
        assert (
            template[-1] == "long_run"
        ), f"{context}: Template must end with 'long_run', got '{template[-1]}'"

        # All workout types must be valid
        for wt in template:
            assert wt in valid_workout_types, f"{context}: Unknown workout type '{wt}'"

    # Validate main templates
    for race_type, freq_dict in WEEKLY_TEMPLATES.items():
        for frequency, phase_dict in freq_dict.items():
            for phase, template in phase_dict.items():
                context = f"WEEKLY_TEMPLATES[{race_type}][{frequency}][{phase}]"

                # Length must match frequency
                assert (
                    len(template) == frequency
                ), f"{context}: Template length {len(template)} != frequency {frequency}"

                validate_template(template, context)

    # Validate scenario overrides
    for scenario, race_dict in SCENARIO_OVERRIDES.items():
        for race_type, freq_dict in race_dict.items():
            for frequency, phase_dict in freq_dict.items():
                for phase, template in phase_dict.items():
                    context = (
                        f"SCENARIO_OVERRIDES[{scenario}][{race_type}]"
                        f"[{frequency}][{phase}]"
                    )

                    assert (
                        len(template) == frequency
                    ), f"{context}: Template length {len(template)} != frequency {frequency}"

                    validate_template(template, context)


# Run validation at import
_validate_templates()
