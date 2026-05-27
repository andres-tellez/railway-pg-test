"""
Workout Taxonomy Module - Global Single Source of Truth
========================================================

This module provides the foundational workout definitions, templates, and rules
used throughout the entire training plan generation system. It is NOT specific
to any single step - it is the app-wide workout knowledge base.

ARCHITECTURE OVERVIEW
---------------------
┌─────────────────────────────────────────────────────────────────────────────┐
│                         WORKOUT TAXONOMY MODULE                              │
│                                                                              │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌───────────────────┐  │
│  │ workout_definitions  │  │   weekly_templates   │  │  placement_rules  │  │
│  │                      │  │                      │  │                   │  │
│  │ - Workout types      │  │ - By race type       │  │ - Safety rules    │  │
│  │ - Intensity levels   │  │ - By frequency       │  │ - Spacing rules   │  │
│  │ - Recovery needs     │  │ - By phase           │  │ - Phase rules     │  │
│  │ - Pace guidance      │  │ - Scenario overrides │  │ - Scenario rules  │  │
│  └──────────────────────┘  └──────────────────────┘  └───────────────────┘  │
│                                      │                                       │
│                                      ▼                                       │
│                    ┌─────────────────────────────────┐                       │
│                    │   workout_placement_engine.py   │                       │
│                    │                                 │                       │
│                    │   Central logic that combines   │                       │
│                    │   definitions + templates +     │                       │
│                    │   rules to place workouts       │                       │
│                    └─────────────────────────────────┘                       │
└─────────────────────────────────────────────────────────────────────────────┘

CONSUMERS (Who uses this module)
--------------------------------
- Step 6: Workout distribution (uses templates, placement engine)
- Step 7: Workout details (uses definitions for pace, intensity, descriptions)
- Step 8: Validation (uses definitions for is_quality, recovery_days)
- Frontend/UI: Labels, descriptions, pace guidance
- Future scenarios: Scenario overrides, rules
- Future race types: Race-specific templates
- Testing: Consistent expected values

DESIGN PRINCIPLES
-----------------
1. SINGLE SOURCE OF TRUTH: All workout knowledge lives here
2. RACE-AGNOSTIC BASE: Core definitions work for any race distance
3. RACE-SPECIFIC TEMPLATES: Templates organized by race type for future expansion
4. PHASE-AWARE: Templates vary by training phase (Base/Build/Peak/Taper)
5. SCENARIO-FLEXIBLE: Rules and templates can be overridden per scenario
6. ZERO DUPLICATION: No workout logic should exist outside this module

FUTURE EXPANSION
----------------
To add a new race type (e.g., half marathon):
1. Add templates to WEEKLY_TEMPLATES["half"] in weekly_templates.py
2. Optionally add scenario overrides
3. No changes needed to placement engine or definitions

To add a new workout type (e.g., fartlek):
1. Add definition to WORKOUT_DEFINITIONS in runner_profile/plan_workout_taxonomy.py
2. Update templates that should include it
3. Placement engine automatically handles it

To add a new rule:
1. Add to DEFAULT_RULES in placement_rules.py
2. Implement check in validate_placement()
3. Optionally add scenario overrides

Author: SmartCoach Development Team
Last Updated: November 2025
"""

from src.smartcoach_mobile_coach.runner_profile.plan_workout_taxonomy import (
    WORKOUT_DEFINITIONS,
    is_quality_workout,
    get_recovery_days,
    get_intensity,
    get_workout_definition,
)

from .weekly_templates import (
    WEEKLY_TEMPLATES,
    SCENARIO_OVERRIDES,
    get_template,
)

from .placement_rules import (
    DEFAULT_RULES,
    SCENARIO_RULES,
    get_rules,
    validate_placement,
)

from .workout_placement_engine import WorkoutPlacementEngine

__all__ = [
    # Definitions
    "WORKOUT_DEFINITIONS",
    "is_quality_workout",
    "get_recovery_days",
    "get_intensity",
    "get_workout_definition",
    # Templates
    "WEEKLY_TEMPLATES",
    "SCENARIO_OVERRIDES",
    "get_template",
    # Rules
    "DEFAULT_RULES",
    "SCENARIO_RULES",
    "get_rules",
    "validate_placement",
    # Engine
    "WorkoutPlacementEngine",
]
