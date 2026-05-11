"""
Plan generation readiness (v1).

Deterministic coaching recommendation layer for deciding whether the current
runner profile supports generating the requested plan. This module is pure:
no planner imports, no database access, no LLM calls.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

SCHEMA_VERSION = "plan_generation_readiness.v1"

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

_SUB3_SECONDS = 3 * 60 * 60
_SUB3_ESTABLISHED_MIN_MPW = 30.0
_SUB3_ADEQUATE_LONG_RUN_MILES = 14.0
_SUB3_VERY_LOW_MPW = 20.0
_SUB3_SHORT_LONG_RUN_MILES = 10.0
_SHORT_TIMELINE_WEEKS = 16.0

_REQUIRED_PLAN_FIELDS = ("race_distance", "race_date", "primary_goal", "training_days")


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_clock_seconds(value: Any) -> Optional[int]:
    raw = str(value or "").strip()
    if not raw:
        return None
    match = re.match(r"^\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*$", raw)
    if not match:
        return None
    try:
        if match.group(3) is not None:
            return (
                int(match.group(1)) * 3600
                + int(match.group(2)) * 60
                + int(match.group(3))
            )
        return int(match.group(1)) * 60 + int(match.group(2))
    except (TypeError, ValueError):
        return None


def _weeks_until_race(plan_request: Dict[str, Any]) -> Optional[float]:
    raw = plan_request.get("race_date")
    if raw is None:
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        race_day = raw
    elif isinstance(raw, datetime):
        race_day = raw.date()
    else:
        try:
            race_day = datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    days = (race_day - date.today()).days
    if days <= 0:
        return 0.0
    return days / 7.0


def _is_marathon(plan_request: Dict[str, Any]) -> bool:
    raw = str(plan_request.get("race_distance") or "").strip().lower()
    if "half" in raw:
        return False
    return "marathon" in raw


def _is_target_time_goal(plan_request: Dict[str, Any]) -> bool:
    goal = str(plan_request.get("primary_goal") or "").strip().lower()
    return goal == "target time" or ("target" in goal and "time" in goal)


def _training_day_count(plan_request: Dict[str, Any]) -> int:
    days = plan_request.get("training_days")
    if not isinstance(days, list):
        return 0
    return len([day for day in days if str(day or "").strip()])


def _missing_required_fields(plan_request: Dict[str, Any]) -> List[str]:
    missing: List[str] = []
    for field in _REQUIRED_PLAN_FIELDS:
        value = plan_request.get(field)
        if field == "training_days":
            if not isinstance(value, list) or not value:
                missing.append(field)
        elif not str(value or "").strip():
            missing.append(field)
    if (
        _is_target_time_goal(plan_request)
        and not str(plan_request.get("target_time") or "").strip()
    ):
        missing.append("target_time")
    return missing


def _assessment_parts(
    assessment_api: Dict[str, Any]
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    activity = assessment_api.get("activity_summary")
    ambition = assessment_api.get("ambition_gap")
    alignment = assessment_api.get("intake_alignment_state")
    return (
        activity if isinstance(activity, dict) else {},
        ambition if isinstance(ambition, dict) else {},
        alignment if isinstance(alignment, dict) else {},
    )


def _ordered_unique(values: Sequence[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


class _ReadinessBuilder:
    def __init__(
        self, plan_request: Dict[str, Any], assessment_api: Dict[str, Any]
    ) -> None:
        self.plan_request = plan_request
        self.assessment_api = assessment_api
        self.activity, self.ambition, self.alignment = _assessment_parts(assessment_api)
        self.reason_codes: List[str] = []
        self.key_findings: List[str] = []
        self.limiting_factors: List[str] = []
        self.required_changes: List[str] = []

    @property
    def avg_mpw(self) -> float:
        return _safe_float(self.activity.get("avg_miles_per_week_approx")) or 0.0

    @property
    def longest_run_miles(self) -> float:
        return _safe_float(self.activity.get("longest_run_miles")) or 0.0

    @property
    def activities_found(self) -> int:
        return _safe_int(self.activity.get("activities_found")) or 0

    @property
    def baseline_band(self) -> str:
        return str(self.ambition.get("baseline_band") or "").strip()

    @property
    def goal_demand(self) -> str:
        return str(self.ambition.get("goal_demand") or "").strip()

    @property
    def ambition_stance(self) -> str:
        return str(self.ambition.get("stance") or "").strip()

    @property
    def weeks_to_race(self) -> Optional[float]:
        return _weeks_until_race(self.plan_request)

    @property
    def is_sub3_marathon(self) -> bool:
        seconds = _parse_clock_seconds(self.plan_request.get("target_time"))
        return bool(
            _is_marathon(self.plan_request)
            and _is_target_time_goal(self.plan_request)
            and seconds is not None
            and seconds <= _SUB3_SECONDS
        )

    def add_reason(self, code: str) -> None:
        self.reason_codes.append(code)

    def add_limiting_factor(self, factor: str) -> None:
        self.limiting_factors.append(factor)

    def require(self, change: str) -> None:
        self.required_changes.append(change)

    def add_standard_findings(self) -> None:
        if self.activities_found:
            self.key_findings.append(
                f"Found {self.activities_found} recent running activit"
                f"{'y' if self.activities_found == 1 else 'ies'}."
            )
        else:
            self.key_findings.append("No recent running activities were found.")
        self.key_findings.append(
            f"Recent running volume is about {self.avg_mpw:.1f} miles per week."
        )
        if self.longest_run_miles > 0:
            self.key_findings.append(
                f"Longest recent run is about {self.longest_run_miles:.1f} miles."
            )
        days = _training_day_count(self.plan_request)
        if days:
            self.key_findings.append(
                f"Requested schedule has {days} run days per week."
            )


def _decision_for_level(readiness_level: str) -> str:
    if readiness_level in (LEVEL_READY, LEVEL_STRETCH):
        return DECISION_ALLOW
    if readiness_level == LEVEL_INSUFFICIENT_DATA:
        return DECISION_DEFER
    return DECISION_DEFER


def _confidence(builder: _ReadinessBuilder, readiness_level: str) -> str:
    if readiness_level == LEVEL_INSUFFICIENT_DATA:
        return CONFIDENCE_LOW
    if builder.activities_found <= 0 or not builder.ambition:
        return CONFIDENCE_LOW
    if builder.activities_found < 3 or builder.baseline_band == "THIN":
        return CONFIDENCE_MEDIUM
    return CONFIDENCE_HIGH


def _allowed_actions_for(
    *,
    decision: str,
    readiness_level: str,
    required_changes: Sequence[str],
) -> List[str]:
    if decision == DECISION_ALLOW:
        actions = [ACTION_CREATE_PLAN]
        if readiness_level == LEVEL_STRETCH:
            actions.append(ACTION_CONTINUE_WITH_WARNING)
        return actions

    if readiness_level == LEVEL_CURRENTLY_UNREALISTIC:
        return [
            ACTION_ADD_RUNNING_DAY,
            ACTION_ADJUST_GOAL,
            ACTION_ADJUST_TIMELINE,
            ACTION_BUILD_BASE_FIRST,
        ]

    actions: List[str] = []
    for change in required_changes:
        if change == "add_running_day":
            actions.append(ACTION_ADD_RUNNING_DAY)
        elif change == "adjust_goal":
            actions.append(ACTION_ADJUST_GOAL)
        elif change == "adjust_timeline":
            actions.append(ACTION_ADJUST_TIMELINE)
        elif change == "build_base_first":
            actions.append(ACTION_BUILD_BASE_FIRST)
        elif change == "complete_alignment_questions":
            actions.append(ACTION_PROVIDE_ALIGNMENT_ANSWERS)
        elif change == "collect_more_activity_data":
            actions.append(ACTION_INGEST_MORE_ACTIVITY)
    return _ordered_unique(actions) or [ACTION_ADJUST_GOAL, ACTION_ADJUST_TIMELINE]


def _recommended_goal_adjustment(
    readiness_level: str,
    required_changes: Sequence[str],
    reason_codes: Sequence[str],
) -> Optional[Dict[str, Any]]:
    if readiness_level == LEVEL_READY:
        return None
    if "build_base_first" in required_changes:
        kind = "build_base_first"
    elif "add_running_day" in required_changes:
        kind = "add_running_day"
    elif "adjust_goal" in required_changes:
        kind = "adjust_goal"
    elif "adjust_timeline" in required_changes:
        kind = "adjust_timeline"
    elif "collect_more_activity_data" in required_changes:
        kind = "collect_more_activity_data"
    else:
        kind = "complete_alignment_questions"
    return {
        "kind": kind,
        "rationale_code": reason_codes[0] if reason_codes else None,
    }


def _recommended_path(
    *,
    readiness_level: str,
    required_changes: Sequence[str],
    reason_codes: Sequence[str],
) -> Dict[str, str]:
    if readiness_level == LEVEL_READY:
        return {
            "type": PATH_CREATE_PLAN,
            "message": "The requested plan is supported by the current profile.",
            "suggested_next_step": "Create the training plan.",
        }
    if readiness_level == LEVEL_STRETCH:
        return {
            "type": PATH_CREATE_PLAN,
            "message": "The requested plan is ambitious but workable with a clear warning.",
            "suggested_next_step": "Confirm the runner understands the stretch before creating the plan.",
        }
    if readiness_level == LEVEL_CURRENTLY_UNREALISTIC:
        return {
            "type": PATH_BUILD_BASE_FIRST,
            "message": (
                "The requested goal does not line up with the current mileage and long-run baseline."
            ),
            "suggested_next_step": "Build more base first, add running frequency, adjust the goal, or move the race farther out.",
        }
    if "complete_alignment_questions" in required_changes:
        return {
            "type": PATH_PROVIDE_ALIGNMENT,
            "message": "One or more alignment answers are still unresolved.",
            "suggested_next_step": "Collect the missing alignment answer before generating.",
        }
    if "collect_more_activity_data" in required_changes:
        return {
            "type": PATH_INGEST_MORE_ACTIVITY,
            "message": "Recent activity data is too thin to make a confident recommendation.",
            "suggested_next_step": "Use synced activity data or revise the intake before creating a plan.",
        }
    if "add_running_day" in required_changes:
        return {
            "type": PATH_ADD_RUNNING_DAY,
            "message": "Adding a running day is the cleanest way to support this goal.",
            "suggested_next_step": "Ask the runner to add a training day or adjust the goal.",
        }
    if "adjust_timeline" in required_changes:
        return {
            "type": PATH_ADJUST_TIMELINE,
            "message": "The requested timeline is tight for this marathon goal.",
            "suggested_next_step": "Move the race farther out or adjust the goal.",
        }
    return {
        "type": PATH_ADJUST_GOAL,
        "message": "The requested goal needs a change before plan generation.",
        "suggested_next_step": "Adjust goal, timeline, or weekly running frequency.",
    }


def _input_digest(builder: _ReadinessBuilder) -> Dict[str, Any]:
    weeks = builder.weeks_to_race
    return {
        "primary_goal": builder.plan_request.get("primary_goal"),
        "race_distance": builder.plan_request.get("race_distance"),
        "race_date": builder.plan_request.get("race_date"),
        "target_time": builder.plan_request.get("target_time"),
        "training_day_count": _training_day_count(builder.plan_request),
        "weeks_to_race": round(weeks, 1) if weeks is not None else None,
        "avg_miles_per_week_approx": round(builder.avg_mpw, 1),
        "longest_run_miles": round(builder.longest_run_miles, 1),
        "activities_found": builder.activities_found,
        "ambition_stance": builder.ambition_stance or None,
        "baseline_band": builder.baseline_band or None,
        "goal_demand": builder.goal_demand or None,
        "alignment_generation_ready": builder.alignment.get("generation_ready"),
    }


def _finalize(
    builder: _ReadinessBuilder,
    *,
    readiness_level: str,
    decision: Optional[str] = None,
) -> Dict[str, Any]:
    builder.add_standard_findings()
    reason_codes = _ordered_unique(builder.reason_codes)
    limiting_factors = _ordered_unique(builder.limiting_factors)
    required_changes = _ordered_unique(builder.required_changes)
    final_decision = decision or _decision_for_level(readiness_level)
    return {
        "schema_version": SCHEMA_VERSION,
        "decision": final_decision,
        "readiness_level": readiness_level,
        "confidence": _confidence(builder, readiness_level),
        "reason_codes": reason_codes,
        "key_findings": builder.key_findings[:5],
        "limiting_factors": limiting_factors,
        "required_changes": required_changes,
        "recommended_goal_adjustment": _recommended_goal_adjustment(
            readiness_level, required_changes, reason_codes
        ),
        "recommended_path": _recommended_path(
            readiness_level=readiness_level,
            required_changes=required_changes,
            reason_codes=reason_codes,
        ),
        "allowed_user_actions": _allowed_actions_for(
            decision=final_decision,
            readiness_level=readiness_level,
            required_changes=required_changes,
        ),
        "inputs_digest": _input_digest(builder),
    }


def evaluate_plan_generation_readiness(
    *,
    plan_request: Dict[str, Any],
    assessment_api: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Return the deterministic readiness decision for a requested plan.

    The LLM may explain this result, but callers must not let the LLM override
    ``decision`` or ``allowed_user_actions``.
    """
    if not isinstance(plan_request, dict) or not isinstance(assessment_api, dict):
        plan = plan_request if isinstance(plan_request, dict) else {}
        assessment = assessment_api if isinstance(assessment_api, dict) else {}
        builder = _ReadinessBuilder(plan, assessment)
        builder.add_reason("RULE_INVALID_READINESS_INPUT")
        builder.add_limiting_factor("invalid_state")
        builder.require("adjust_goal")
        return _finalize(
            builder,
            readiness_level=LEVEL_INSUFFICIENT_DATA,
            decision=DECISION_BLOCK,
        )

    builder = _ReadinessBuilder(plan_request, assessment_api)
    missing = _missing_required_fields(plan_request)
    if missing:
        builder.add_reason("RULE_REQUIRED_PLAN_FIELDS_MISSING")
        builder.add_limiting_factor("missing_required_fields")
        for field in missing:
            builder.add_limiting_factor(f"missing_{field}")
        builder.require("adjust_goal")
        return _finalize(
            builder,
            readiness_level=LEVEL_INSUFFICIENT_DATA,
            decision=DECISION_BLOCK,
        )

    unresolved = [
        str(flag)
        for flag in list(builder.alignment.get("unresolved_flags") or [])
        if str(flag).strip()
    ]
    if (
        builder.alignment
        and not builder.alignment.get("generation_ready", True)
        and unresolved
    ):
        builder.add_reason("RULE_ALIGNMENT_UNRESOLVED")
        builder.add_limiting_factor("alignment_unresolved")
        builder.require("complete_alignment_questions")
        return _finalize(builder, readiness_level=LEVEL_INSUFFICIENT_DATA)

    if builder.ambition_stance == "INSUFFICIENT_GOAL_CONTEXT":
        builder.add_reason("RULE_INSUFFICIENT_GOAL_CONTEXT")
        builder.add_limiting_factor("insufficient_goal_context")
        builder.require("adjust_goal")
        return _finalize(builder, readiness_level=LEVEL_INSUFFICIENT_DATA)

    if builder.activities_found == 0:
        builder.add_reason("RULE_ACTIVITIES_FOUND_ZERO")
        builder.add_limiting_factor("insufficient_activity_data")
        builder.require("collect_more_activity_data")
        return _finalize(builder, readiness_level=LEVEL_INSUFFICIENT_DATA)

    n_days = _training_day_count(plan_request)
    weeks = builder.weeks_to_race
    short_timeline = weeks is not None and weeks < _SHORT_TIMELINE_WEEKS

    if builder.is_sub3_marathon:
        if (
            builder.avg_mpw < _SUB3_VERY_LOW_MPW
            and builder.longest_run_miles < _SUB3_SHORT_LONG_RUN_MILES
        ):
            builder.add_reason("RULE_SUB3_VERY_LOW_MILEAGE_AND_SHORT_LONG_RUN")
            builder.add_limiting_factor("very_low_weekly_mileage")
            builder.add_limiting_factor("short_long_run_for_goal")
            builder.require("build_base_first")
            builder.require("add_running_day")
            builder.require("adjust_goal")
            builder.require("adjust_timeline")
            return _finalize(builder, readiness_level=LEVEL_CURRENTLY_UNREALISTIC)
        if n_days <= 3:
            builder.add_reason("RULE_SUB3_THREE_DAYS_HIGH_RISK")
            builder.add_limiting_factor("few_run_days_for_sub3_marathon")
            builder.require("add_running_day")
            builder.require("adjust_goal")
            return _finalize(builder, readiness_level=LEVEL_HIGH_RISK)
        if n_days == 4 and builder.baseline_band != "ESTABLISHED":
            builder.add_reason("RULE_SUB3_FOUR_DAYS_WEAK_BASELINE")
            builder.add_limiting_factor("weak_baseline_for_sub3_marathon")
            builder.require("add_running_day")
            builder.require("adjust_goal")
            return _finalize(builder, readiness_level=LEVEL_HIGH_RISK)
        if short_timeline:
            builder.add_reason("RULE_SUB3_SHORT_TIMELINE")
            builder.add_limiting_factor("short_timeline_for_sub3_marathon")
            builder.require("adjust_timeline")
            builder.require("adjust_goal")
            return _finalize(builder, readiness_level=LEVEL_HIGH_RISK)
        if (
            builder.avg_mpw >= _SUB3_ESTABLISHED_MIN_MPW
            and builder.longest_run_miles >= _SUB3_ADEQUATE_LONG_RUN_MILES
        ):
            builder.add_reason("RULE_SUB3_ESTABLISHED_BASELINE")
            return _finalize(builder, readiness_level=LEVEL_STRETCH)

        builder.add_reason("RULE_SUB3_BASELINE_NOT_ESTABLISHED")
        builder.add_limiting_factor("baseline_not_established_for_sub3_marathon")
        builder.require("build_base_first")
        builder.require("adjust_goal")
        return _finalize(builder, readiness_level=LEVEL_HIGH_RISK)

    if _is_marathon(plan_request) and _is_target_time_goal(plan_request):
        if builder.baseline_band == "THIN":
            builder.add_reason("RULE_MARATHON_TIME_TARGET_THIN_BASELINE")
            builder.add_limiting_factor("thin_baseline_for_marathon_time_goal")
            builder.require("add_running_day")
            builder.require("adjust_goal")
            return _finalize(builder, readiness_level=LEVEL_HIGH_RISK)
        if short_timeline:
            builder.add_reason("RULE_MARATHON_TIME_TARGET_SHORT_TIMELINE")
            builder.add_limiting_factor("short_timeline_for_marathon_time_goal")
            builder.require("adjust_timeline")
            return _finalize(builder, readiness_level=LEVEL_HIGH_RISK)

    if builder.ambition_stance in ("HIGH_TENSION", "MANAGEABLE_TENSION"):
        builder.add_reason("RULE_TENSION_AFTER_ALIGNMENT")
        builder.add_limiting_factor("goal_training_tension")
        return _finalize(builder, readiness_level=LEVEL_STRETCH)

    builder.add_reason("RULE_DEFAULT_READY")
    return _finalize(builder, readiness_level=LEVEL_READY)
