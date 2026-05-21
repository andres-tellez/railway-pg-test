"""
Purpose:
- Define stable vocabulary enums for Memory module.

Responsibilities:
- Provide one source of truth for memory kinds, sources, and tags.

Non-goals:
- No business logic or policy evaluation.

Guardrails:
- Allowed imports/calls: stdlib enum only.
- Must not import service or adapter modules.
"""

from __future__ import annotations

from enum import StrEnum


class MemoryKind(StrEnum):
    DURABLE = "durable"
    STATE = "state"
    OPEN_THREAD = "open_thread"
    INTERACTION = "interaction"
    SUMMARY = "summary"


class Source(StrEnum):
    USER_STATEMENT = "user_statement"
    COACH_TOOL = "coach_tool"
    SUMMARIZER = "summarizer"
    INFERRED = "inferred"
    SYSTEM = "system"


class DurableType(StrEnum):
    GOAL = "goal"
    CONSTRAINT = "constraint"
    PREFERENCE = "preference"
    TRAINING_DAYS = "training_days"
    LONG_RUN_DAY = "long_run_day"
    OTHER = "other"


class StateTag(StrEnum):
    HEADACHE = "headache"
    SORE = "sore"
    LOW_SLEEP = "low_sleep"
    HIGH_STRESS = "high_stress"
    LOW_MOTIVATION = "low_motivation"
    SICK = "sick"
    INJURY_FLARE = "injury_flare"
    GOOD_DAY = "good_day"


class ThreadTopic(StrEnum):
    INJURY_RECHECK = "injury_recheck"
    PLAN_DECISION = "plan_decision"
    GOAL_REVISIT = "goal_revisit"
    PROGRESS_CHECKIN = "progress_checkin"
    USER_REQUEST = "user_request"


class InteractionFlag(StrEnum):
    RECAPPED_RUN = "recapped_run"
    DISCUSSED_TODAY = "discussed_today"
    DISCUSSED_SPLITS = "discussed_splits"
    DISCUSSED_PLAN = "discussed_plan"
