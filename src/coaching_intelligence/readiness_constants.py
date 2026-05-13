"""Shared readiness / display string constants (Phase 5 split)."""

from __future__ import annotations

from typing import Dict, Tuple

GOAL_PROFILE_COMPLETION = "completion"
GOAL_PROFILE_MODERATE_PERFORMANCE = "moderate_performance"
GOAL_PROFILE_COMPETITIVE_PERFORMANCE = "competitive_performance"

CATEGORY_GOAL_DEMAND = "goal_demand"
CATEGORY_PERFORMANCE_ALIGNMENT = "performance_alignment"
CATEGORY_TRAINING_AVAILABILITY = "training_availability"
CATEGORY_VOLUME_BASELINE = "volume_baseline"
CATEGORY_LONG_RUN_DURABILITY = "long_run_durability"
CATEGORY_TIMELINE = "timeline"
CATEGORY_CONSISTENCY = "consistency"
CATEGORY_DATA_CONFIDENCE = "data_confidence"
CATEGORY_EFFORT_CONTROL = "effort_control"

CATEGORY_ORDER: Tuple[str, ...] = (
    CATEGORY_GOAL_DEMAND,
    CATEGORY_PERFORMANCE_ALIGNMENT,
    CATEGORY_TRAINING_AVAILABILITY,
    CATEGORY_VOLUME_BASELINE,
    CATEGORY_LONG_RUN_DURABILITY,
    CATEGORY_TIMELINE,
    CATEGORY_CONSISTENCY,
    CATEGORY_DATA_CONFIDENCE,
    CATEGORY_EFFORT_CONTROL,
)

STATUS_OK = "ok"
STATUS_WARN = "warn"
STATUS_BAD = "bad"

DECISION_ALLOW = "allow"
DECISION_DEFER = "defer"
DECISION_BLOCK = "block"

LEVEL_READY = "ready"
LEVEL_STRETCH = "stretch"
LEVEL_HIGH_RISK = "high_risk"
LEVEL_CURRENTLY_UNREALISTIC = "currently_unrealistic"
LEVEL_INSUFFICIENT_DATA = "insufficient_data"

CONFIDENCE_LOW = "low"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_HIGH = "high"

ACTION_CREATE_PLAN = "create_plan"
ACTION_ADD_RUNNING_DAY = "add_running_day"
ACTION_ADJUST_GOAL = "adjust_goal"
ACTION_ADJUST_TIMELINE = "adjust_timeline"
ACTION_BUILD_BASE_FIRST = "build_base_first"
ACTION_PROVIDE_ALIGNMENT_ANSWERS = "provide_alignment_answers"
ACTION_INGEST_MORE_ACTIVITY = "ingest_more_activity"
ACTION_CONTINUE_WITH_WARNING = "continue_with_warning"

PATH_CREATE_PLAN = "create_plan"
PATH_ADD_RUNNING_DAY = "add_running_day"
PATH_ADJUST_GOAL = "adjust_goal"
PATH_ADJUST_TIMELINE = "adjust_timeline"
PATH_BUILD_BASE_FIRST = "build_base_first"
PATH_PROVIDE_ALIGNMENT = "provide_alignment_answers"
PATH_INGEST_MORE_ACTIVITY = "ingest_more_activity"

_DEVELOPMENTAL_MODERATE_MARATHON_PATH_MESSAGE = (
    "This goal is more realistic than sub-3, but it is still a developmental performance build. "
    "The plan can be created, but success depends on closing the pace gap, improving consistency, "
    "and building long-run durability."
)
_DEVELOPMENTAL_MODERATE_MARATHON_RECOMMENDED_PATH: Dict[str, str] = {
    "type": PATH_CREATE_PLAN,
    "message": _DEVELOPMENTAL_MODERATE_MARATHON_PATH_MESSAGE,
    "suggested_next_step": (
        "Create the plan with a patience-first mindset — prioritize consistency and durable long runs."
    ),
}

# Distinct from competitive ``RULE_PERFORMANCE_*`` — developmental WARN for moderate profile only.
RULE_MODERATE_PERFORMANCE_PACE_GAP = "RULE_MODERATE_PERFORMANCE_PACE_GAP"
