"""
Plan generation readiness (v2.2).

Deterministic coaching recommendation layer for deciding whether the current
runner profile supports generating the requested plan. This module is pure:
no planner imports, no database access, no LLM calls.

v2 adds ``category_assessments`` (ok / warn / bad). v2.1 gates performance
rules by ``goal_profile`` (completion vs moderate vs competitive). v2.2 adds
**performance_alignment** (pace vs marathon goal pace, reliability-gated),
extends **long-run durability** with pattern signals from the activity snapshot,
and keeps **one** policy surface in this module.

``activities_found`` is a data-confidence signal only, never a fitness proxy.

**Goal profiles (policy defaults):**

- **completion** — finish / no target time / first marathon or just-finish wording.
- **moderate_performance** — PR, strong finish, or marathon target time **strictly slower than 3:30:00**.
- **competitive_performance** — marathon **<= 3:30:00**, sub-3 branch, BQ-style intent, or
  **HIGH_TENSION** with a time goal (aggressive vs baseline).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


def _json_safe_scalar(value: Any) -> Any:
    """Coerce date/datetime to ISO strings for API JSON payloads (readiness only)."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _json_safe_facts(value: Any) -> Any:
    """Recursively JSON-safe structures for category ``facts_used``."""
    if isinstance(value, dict):
        return {str(k): _json_safe_facts(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe_facts(v) for v in value]
    return _json_safe_scalar(value)


SCHEMA_VERSION = "plan_generation_readiness.v2.2"

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

_SUB3_SECONDS = 3 * 60 * 60
# Marathon clock <= 3:30:00 inclusive → competitive; strictly slower → moderate.
_COMPETITIVE_MARATHON_MAX_SECONDS = 3 * 3600 + 30 * 60  # 3:30:00
_MARATHON_DISTANCE_MI = 26.2
_SUB3_ESTABLISHED_MIN_MPW = 30.0
_SUB3_ADEQUATE_LONG_RUN_MILES = 14.0
_SUB3_VERY_LOW_MPW = 20.0
_SUB3_SHORT_LONG_RUN_MILES = 10.0
_SHORT_TIMELINE_WEEKS = 16.0
_COMPLETION_MARATHON_CRITICAL_WEEKS = 8.0
_CONSISTENCY_LOOKBACK_MIN_WEEKS = 4
_CONSISTENCY_ACTIVE_WEEK_RATIO_WARN = 0.35
_CONSISTENCY_WEEKLY_SPREAD_MI_WARN = 30.0
_CONSISTENCY_MIN_COMPLETED_WEEKS_FOR_SPREAD = 3
_EFFORT_CONTROL_MIN_RUNS = 4

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


def _marathon_goal_pace_sec_per_mi(plan_request: Dict[str, Any]) -> Optional[float]:
    """Observational goal marathon pace from stated marathon target time (sec/mi)."""
    if not (_is_marathon(plan_request) and _is_target_time_goal(plan_request)):
        return None
    secs = _parse_clock_seconds(plan_request.get("target_time"))
    if secs is None or secs <= 0:
        return None
    return float(secs) / _MARATHON_DISTANCE_MI


def _fmt_pace_min_mi(sec_per_mi: float) -> str:
    if sec_per_mi <= 0 or sec_per_mi > 3600:
        return "—"
    m = int(sec_per_mi // 60)
    s = int(round(sec_per_mi % 60))
    if s >= 60:
        m += 1
        s = 0
    return f"{m}:{s:02d}/mi"


def _assessment_parts(
    assessment_api: Dict[str, Any],
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
                f"{self.activities_found} run(s) in the lookback window "
                f"(data coverage for readiness — not a fitness score)."
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


def _bq_marathon_intent(plan_request: Dict[str, Any]) -> bool:
    """Boston-qualify / BQ phrasing in goal or notes (marathon only; heuristic)."""
    if not _is_marathon(plan_request):
        return False
    pg = str(plan_request.get("primary_goal") or "").strip().lower()
    notes = str(plan_request.get("notes") or "").strip().lower()
    blob = f"{pg} {notes}"
    if re.search(r"\bbq\b", blob):
        return True
    if "boston" in blob and "qual" in blob:
        return True
    return False


def _completion_style_primary_goal(plan_request: Dict[str, Any]) -> bool:
    pg = str(plan_request.get("primary_goal") or "").strip().lower()
    if not pg:
        return False
    if "just finish" in pg or ("just" in pg and "finish" in pg):
        return True
    if "first marathon" in pg or "first half" in pg:
        return True
    if "complete" in pg and "time" not in pg:
        return True
    if pg in ("finish", "completion", "finish strong"):
        return True
    return False


def _infer_goal_profile(builder: _ReadinessBuilder) -> str:
    """
    Coaching goal profile — single policy surface.

    Sub-3 (<= 3:00:00 marathon time goal) is always competitive and keeps the
    existing highest-demand evaluation branch. BQ wording, marathon <= 3:30, or
    HIGH_TENSION on a time goal → competitive; else marathon time slower than
    3:30 → moderate.
    """
    if builder.is_sub3_marathon:
        return GOAL_PROFILE_COMPETITIVE_PERFORMANCE

    gd = builder.goal_demand
    if gd == "FINISH":
        return GOAL_PROFILE_COMPLETION
    if gd == "GENERAL":
        if _completion_style_primary_goal(builder.plan_request):
            return GOAL_PROFILE_COMPLETION
        return GOAL_PROFILE_MODERATE_PERFORMANCE

    if gd == "TIME_TARGET":
        if _is_marathon(builder.plan_request):
            if _bq_marathon_intent(builder.plan_request):
                return GOAL_PROFILE_COMPETITIVE_PERFORMANCE
            if builder.ambition_stance == "HIGH_TENSION":
                return GOAL_PROFILE_COMPETITIVE_PERFORMANCE
            secs = _parse_clock_seconds(builder.plan_request.get("target_time"))
            if secs is not None and secs <= _COMPETITIVE_MARATHON_MAX_SECONDS:
                return GOAL_PROFILE_COMPETITIVE_PERFORMANCE
        return GOAL_PROFILE_MODERATE_PERFORMANCE

    return GOAL_PROFILE_MODERATE_PERFORMANCE


def _effort_control_reliable(activity: Dict[str, Any]) -> bool:
    total = int(_safe_int(activity.get("effort_signal_runs")) or 0)
    return (
        bool(activity.get("has_effort_control_signal"))
        and total >= _EFFORT_CONTROL_MIN_RUNS
    )


def _category_applies_to_goal(
    category_id: str, goal_profile: str, builder: _ReadinessBuilder
) -> bool:
    """When False, severity is shown as ok for UX; category does not encode policy for that profile."""
    if category_id == CATEGORY_PERFORMANCE_ALIGNMENT:
        if goal_profile != GOAL_PROFILE_COMPETITIVE_PERFORMANCE:
            return False
        return bool(
            _is_marathon(builder.plan_request)
            and _is_target_time_goal(builder.plan_request)
        )
    if category_id == CATEGORY_EFFORT_CONTROL:
        if goal_profile == GOAL_PROFILE_COMPLETION:
            return False
        return _effort_control_reliable(builder.activity)
    return True


def _apply_marathon_performance_alignment_rules(
    builder: _ReadinessBuilder,
    goal_profile: str,
    plan_request: Dict[str, Any],
) -> None:
    """P1: competitive marathon time goals — observed pace vs goal marathon pace (reliability-gated)."""
    if goal_profile != GOAL_PROFILE_COMPETITIVE_PERFORMANCE:
        return
    if not (_is_marathon(plan_request) and _is_target_time_goal(plan_request)):
        return
    goal_pace = _marathon_goal_pace_sec_per_mi(plan_request)
    if goal_pace is None:
        return
    rel = str(builder.activity.get("pace_reliability") or "none")
    easy = _safe_float(builder.activity.get("typical_easy_pace_sec_per_mi"))
    sustained = _safe_float(
        builder.activity.get("best_sustained_endurance_pace_sec_per_mi")
    )

    if rel in ("none", "low"):
        builder.add_reason("RULE_PERFORMANCE_PACE_DATA_THIN")
        builder.add_limiting_factor("thin_pace_data_for_time_goal")
        return

    if easy is not None:
        gap = easy - goal_pace
        if gap > 115:
            builder.add_reason("RULE_PERFORMANCE_LARGE_GAP_EASY_VS_GOAL_PACE")
            builder.add_limiting_factor(
                "observed_easy_pace_far_from_goal_marathon_pace"
            )
            builder.require("adjust_goal")
        elif gap > 72:
            builder.add_reason("RULE_PERFORMANCE_MODERATE_GAP_EASY_VS_GOAL_PACE")

    if sustained is not None:
        gap_s = sustained - goal_pace
        if gap_s > 95:
            builder.add_reason("RULE_PERFORMANCE_NO_SUSTAINED_PACE_NEAR_GOAL")
            builder.add_limiting_factor(
                "sustained_run_pace_not_near_goal_marathon_pace"
            )
            builder.require("adjust_goal")
        elif gap_s > 58:
            builder.add_reason("RULE_PERFORMANCE_STRETCH_SUSTAINED_VS_GOAL")


def _apply_long_run_quality_rules(
    builder: _ReadinessBuilder,
    goal_profile: str,
    plan_request: Dict[str, Any],
) -> None:
    """P2: long-run durability pattern (distinct from single longest-run scalar)."""
    if goal_profile != GOAL_PROFILE_COMPETITIVE_PERFORMANCE:
        return
    if not (_is_marathon(plan_request) and _is_target_time_goal(plan_request)):
        return
    lookback = int(_safe_int(builder.activity.get("lookback_weeks")) or 0)
    if lookback < 4 or builder.activities_found < 3:
        return
    n10 = int(_safe_int(builder.activity.get("long_runs_ge_10_mi_count")) or 0)
    weeks_lr = int(_safe_int(builder.activity.get("weeks_with_long_run_10plus")) or 0)
    trend = str(builder.activity.get("long_run_progression_trend") or "")

    if builder.longest_run_miles >= 8.0 or builder.is_sub3_marathon:
        if n10 <= 1 and builder.activities_found >= 5:
            builder.add_reason("RULE_LONG_RUN_PATTERN_THIN")
        if weeks_lr <= 1 and lookback >= 6 and n10 >= 1:
            builder.add_reason("RULE_LONG_RUN_FREQUENCY_LOW")
    if trend == "down" and builder.longest_run_miles >= 8.0:
        builder.add_reason("RULE_LONG_RUN_RECENT_REGRESSION")


def _escalate_readiness_for_performance_alignment(
    builder: _ReadinessBuilder,
    goal_profile: str,
    plan_request: Dict[str, Any],
    level: str,
) -> str:
    if goal_profile != GOAL_PROFILE_COMPETITIVE_PERFORMANCE:
        return level
    if not (_is_marathon(plan_request) and _is_target_time_goal(plan_request)):
        return level
    rel = str(builder.activity.get("pace_reliability") or "none")
    if rel in ("none", "low"):
        return level
    rc = set(builder.reason_codes)
    bad = {
        "RULE_PERFORMANCE_LARGE_GAP_EASY_VS_GOAL_PACE",
        "RULE_PERFORMANCE_NO_SUSTAINED_PACE_NEAR_GOAL",
    }
    warn_only = {
        "RULE_PERFORMANCE_MODERATE_GAP_EASY_VS_GOAL_PACE",
        "RULE_PERFORMANCE_STRETCH_SUSTAINED_VS_GOAL",
    }
    if rc & bad:
        if level in (LEVEL_READY, LEVEL_STRETCH):
            return LEVEL_HIGH_RISK
        return level
    if rc & warn_only and level == LEVEL_READY:
        return LEVEL_STRETCH
    return level


def _escalate_readiness_for_long_run_patterns(
    builder: _ReadinessBuilder,
    goal_profile: str,
    plan_request: Dict[str, Any],
    level: str,
) -> str:
    if goal_profile != GOAL_PROFILE_COMPETITIVE_PERFORMANCE:
        return level
    if not (_is_marathon(plan_request) and _is_target_time_goal(plan_request)):
        return level
    rc = set(builder.reason_codes)
    if builder.is_sub3_marathon and "RULE_LONG_RUN_PATTERN_THIN" in rc:
        if level == LEVEL_STRETCH:
            return LEVEL_HIGH_RISK
    if (
        "RULE_LONG_RUN_RECENT_REGRESSION" in rc
        and "RULE_PERFORMANCE_LARGE_GAP_EASY_VS_GOAL_PACE" in rc
        and level == LEVEL_STRETCH
    ):
        return LEVEL_HIGH_RISK
    return level


def _resolve_readiness_level_after_signals(
    builder: _ReadinessBuilder,
    goal_profile: str,
    plan_request: Dict[str, Any],
    preliminary_level: str,
) -> str:
    level = preliminary_level
    level = _escalate_readiness_for_performance_alignment(
        builder, goal_profile, plan_request, level
    )
    level = _escalate_readiness_for_long_run_patterns(
        builder, goal_profile, plan_request, level
    )
    return level


def _finalize_evaluated(
    builder: _ReadinessBuilder,
    *,
    readiness_level: str,
    goal_profile: str,
    decision: Optional[str] = None,
) -> Dict[str, Any]:
    final_level = _resolve_readiness_level_after_signals(
        builder, goal_profile, builder.plan_request, readiness_level
    )
    return _finalize(
        builder,
        readiness_level=final_level,
        goal_profile=goal_profile,
        decision=decision,
    )


def _decision_for_level(readiness_level: str) -> str:
    if readiness_level in (LEVEL_READY, LEVEL_STRETCH):
        return DECISION_ALLOW
    if readiness_level == LEVEL_INSUFFICIENT_DATA:
        return DECISION_DEFER
    return DECISION_DEFER


def _confidence(
    builder: _ReadinessBuilder, readiness_level: str, goal_profile: str
) -> str:
    if readiness_level == LEVEL_INSUFFICIENT_DATA:
        return CONFIDENCE_LOW
    if builder.activities_found <= 0 or not builder.ambition:
        return CONFIDENCE_LOW
    out = CONFIDENCE_HIGH
    if builder.activities_found < 3 or builder.baseline_band == "THIN":
        out = CONFIDENCE_MEDIUM
    if (
        goal_profile == GOAL_PROFILE_COMPETITIVE_PERFORMANCE
        and _is_marathon(builder.plan_request)
        and _is_target_time_goal(builder.plan_request)
    ):
        pr = str(builder.activity.get("pace_reliability") or "none")
        if pr in ("none", "low"):
            if out == CONFIDENCE_HIGH:
                out = CONFIDENCE_MEDIUM
            elif out == CONFIDENCE_MEDIUM:
                out = CONFIDENCE_LOW
        if "RULE_PERFORMANCE_PACE_DATA_THIN" in set(builder.reason_codes):
            out = CONFIDENCE_LOW
    return out


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


def _input_digest(builder: _ReadinessBuilder, *, goal_profile: str) -> Dict[str, Any]:
    weeks = builder.weeks_to_race
    act = builder.activity if isinstance(builder.activity, dict) else {}
    gp_pace = _marathon_goal_pace_sec_per_mi(builder.plan_request)
    return {
        "goal_profile": goal_profile,
        "primary_goal": builder.plan_request.get("primary_goal"),
        "race_distance": builder.plan_request.get("race_distance"),
        "race_date": _json_safe_scalar(builder.plan_request.get("race_date")),
        "target_time": builder.plan_request.get("target_time"),
        "training_day_count": _training_day_count(builder.plan_request),
        "weeks_to_race": round(weeks, 1) if weeks is not None else None,
        "avg_miles_per_week_approx": round(builder.avg_mpw, 1),
        "longest_run_miles": round(builder.longest_run_miles, 1),
        "activities_found": builder.activities_found,
        "lookback_weeks": act.get("lookback_weeks"),
        "active_weeks": act.get("active_weeks"),
        "completed_calendar_weeks_count": act.get("completed_calendar_weeks_count"),
        "ambition_stance": builder.ambition_stance or None,
        "baseline_band": builder.baseline_band or None,
        "goal_demand": builder.goal_demand or None,
        "alignment_generation_ready": builder.alignment.get("generation_ready"),
        "pace_reliability": act.get("pace_reliability"),
        "runs_usable_pace_count": act.get("runs_usable_pace_count"),
        "typical_easy_pace_sec_per_mi": act.get("typical_easy_pace_sec_per_mi"),
        "best_sustained_endurance_pace_sec_per_mi": act.get(
            "best_sustained_endurance_pace_sec_per_mi"
        ),
        "goal_marathon_pace_sec_per_mi": (
            round(gp_pace, 1) if gp_pace is not None else None
        ),
        "long_runs_ge_10_mi_count": act.get("long_runs_ge_10_mi_count"),
        "weeks_with_long_run_10plus": act.get("weeks_with_long_run_10plus"),
        "long_run_progression_trend": act.get("long_run_progression_trend"),
    }


_SEV_OK = 0
_SEV_WARN = 1
_SEV_BAD = 2

_STATUS_FROM_SEV = {0: STATUS_OK, 1: STATUS_WARN, 2: STATUS_BAD}

# (rule_code, category_id, severity) — severity is WARN or BAD (OK is baseline)
_REASON_CATEGORY_BUMPS: Tuple[Tuple[str, str, int], ...] = (
    ("RULE_INVALID_READINESS_INPUT", CATEGORY_DATA_CONFIDENCE, _SEV_BAD),
    ("RULE_REQUIRED_PLAN_FIELDS_MISSING", CATEGORY_DATA_CONFIDENCE, _SEV_BAD),
    ("RULE_REQUIRED_PLAN_FIELDS_MISSING", CATEGORY_GOAL_DEMAND, _SEV_BAD),
    ("RULE_ALIGNMENT_UNRESOLVED", CATEGORY_TRAINING_AVAILABILITY, _SEV_WARN),
    ("RULE_INSUFFICIENT_GOAL_CONTEXT", CATEGORY_GOAL_DEMAND, _SEV_BAD),
    ("RULE_ACTIVITIES_FOUND_ZERO", CATEGORY_DATA_CONFIDENCE, _SEV_BAD),
    (
        "RULE_SUB3_VERY_LOW_MILEAGE_AND_SHORT_LONG_RUN",
        CATEGORY_VOLUME_BASELINE,
        _SEV_BAD,
    ),
    (
        "RULE_SUB3_VERY_LOW_MILEAGE_AND_SHORT_LONG_RUN",
        CATEGORY_LONG_RUN_DURABILITY,
        _SEV_BAD,
    ),
    ("RULE_SUB3_THREE_DAYS_HIGH_RISK", CATEGORY_TRAINING_AVAILABILITY, _SEV_BAD),
    ("RULE_SUB3_FOUR_DAYS_WEAK_BASELINE", CATEGORY_TRAINING_AVAILABILITY, _SEV_WARN),
    ("RULE_SUB3_SHORT_TIMELINE", CATEGORY_TIMELINE, _SEV_BAD),
    ("RULE_SUB3_BASELINE_NOT_ESTABLISHED", CATEGORY_VOLUME_BASELINE, _SEV_WARN),
    ("RULE_SUB3_BASELINE_NOT_ESTABLISHED", CATEGORY_LONG_RUN_DURABILITY, _SEV_WARN),
    ("RULE_MARATHON_TIME_TARGET_THIN_BASELINE", CATEGORY_VOLUME_BASELINE, _SEV_BAD),
    ("RULE_MARATHON_TIME_TARGET_SHORT_TIMELINE", CATEGORY_TIMELINE, _SEV_WARN),
    ("RULE_TENSION_AFTER_ALIGNMENT", CATEGORY_GOAL_DEMAND, _SEV_WARN),
    ("RULE_COMPLETION_MARATHON_TIMELINE_CRITICAL", CATEGORY_TIMELINE, _SEV_BAD),
    ("RULE_COMPLETION_MARATHON_SHORT_RAMP", CATEGORY_LONG_RUN_DURABILITY, _SEV_WARN),
    ("RULE_COMPLETION_MARATHON_SHORT_RAMP", CATEGORY_TIMELINE, _SEV_WARN),
    (
        "RULE_PERFORMANCE_LARGE_GAP_EASY_VS_GOAL_PACE",
        CATEGORY_PERFORMANCE_ALIGNMENT,
        _SEV_BAD,
    ),
    (
        "RULE_PERFORMANCE_NO_SUSTAINED_PACE_NEAR_GOAL",
        CATEGORY_PERFORMANCE_ALIGNMENT,
        _SEV_BAD,
    ),
    (
        "RULE_PERFORMANCE_MODERATE_GAP_EASY_VS_GOAL_PACE",
        CATEGORY_PERFORMANCE_ALIGNMENT,
        _SEV_WARN,
    ),
    (
        "RULE_PERFORMANCE_STRETCH_SUSTAINED_VS_GOAL",
        CATEGORY_PERFORMANCE_ALIGNMENT,
        _SEV_WARN,
    ),
    ("RULE_PERFORMANCE_PACE_DATA_THIN", CATEGORY_PERFORMANCE_ALIGNMENT, _SEV_WARN),
    ("RULE_PERFORMANCE_PACE_DATA_THIN", CATEGORY_DATA_CONFIDENCE, _SEV_WARN),
    ("RULE_LONG_RUN_PATTERN_THIN", CATEGORY_LONG_RUN_DURABILITY, _SEV_WARN),
    ("RULE_LONG_RUN_FREQUENCY_LOW", CATEGORY_LONG_RUN_DURABILITY, _SEV_WARN),
    ("RULE_LONG_RUN_RECENT_REGRESSION", CATEGORY_LONG_RUN_DURABILITY, _SEV_WARN),
)

_REASON_CODES_BY_CATEGORY: Dict[str, frozenset] = {
    CATEGORY_GOAL_DEMAND: frozenset(
        {
            "RULE_INSUFFICIENT_GOAL_CONTEXT",
            "RULE_TENSION_AFTER_ALIGNMENT",
            "RULE_REQUIRED_PLAN_FIELDS_MISSING",
        }
    ),
    CATEGORY_PERFORMANCE_ALIGNMENT: frozenset(
        {
            "RULE_PERFORMANCE_LARGE_GAP_EASY_VS_GOAL_PACE",
            "RULE_PERFORMANCE_NO_SUSTAINED_PACE_NEAR_GOAL",
            "RULE_PERFORMANCE_MODERATE_GAP_EASY_VS_GOAL_PACE",
            "RULE_PERFORMANCE_STRETCH_SUSTAINED_VS_GOAL",
            "RULE_PERFORMANCE_PACE_DATA_THIN",
        }
    ),
    CATEGORY_TRAINING_AVAILABILITY: frozenset(
        {
            "RULE_ALIGNMENT_UNRESOLVED",
            "RULE_SUB3_THREE_DAYS_HIGH_RISK",
            "RULE_SUB3_FOUR_DAYS_WEAK_BASELINE",
        }
    ),
    CATEGORY_VOLUME_BASELINE: frozenset(
        {
            "RULE_SUB3_VERY_LOW_MILEAGE_AND_SHORT_LONG_RUN",
            "RULE_SUB3_BASELINE_NOT_ESTABLISHED",
            "RULE_MARATHON_TIME_TARGET_THIN_BASELINE",
        }
    ),
    CATEGORY_LONG_RUN_DURABILITY: frozenset(
        {
            "RULE_SUB3_VERY_LOW_MILEAGE_AND_SHORT_LONG_RUN",
            "RULE_SUB3_BASELINE_NOT_ESTABLISHED",
            "RULE_COMPLETION_MARATHON_SHORT_RAMP",
            "RULE_LONG_RUN_PATTERN_THIN",
            "RULE_LONG_RUN_FREQUENCY_LOW",
            "RULE_LONG_RUN_RECENT_REGRESSION",
        }
    ),
    CATEGORY_TIMELINE: frozenset(
        {
            "RULE_SUB3_SHORT_TIMELINE",
            "RULE_MARATHON_TIME_TARGET_SHORT_TIMELINE",
            "RULE_COMPLETION_MARATHON_TIMELINE_CRITICAL",
            "RULE_COMPLETION_MARATHON_SHORT_RAMP",
        }
    ),
    CATEGORY_CONSISTENCY: frozenset(
        {
            "RULE_CONSISTENCY_SPARSE_ACTIVE_WEEKS",
            "RULE_CONSISTENCY_HIGH_WEEKLY_VARIANCE",
        }
    ),
    CATEGORY_DATA_CONFIDENCE: frozenset(
        {
            "RULE_INVALID_READINESS_INPUT",
            "RULE_REQUIRED_PLAN_FIELDS_MISSING",
            "RULE_ACTIVITIES_FOUND_ZERO",
            "RULE_PERFORMANCE_PACE_DATA_THIN",
        }
    ),
    CATEGORY_EFFORT_CONTROL: frozenset({"RULE_EFFORT_CONTROL_DOMINANT_TOO_HARD"}),
}


def _bump_cat(
    severities: Dict[str, int],
    category_id: str,
    level: int,
) -> None:
    severities[category_id] = max(severities.get(category_id, _SEV_OK), level)


def _apply_reason_code_bumps(
    severities: Dict[str, int],
    reason_codes: Sequence[str],
) -> None:
    rc = set(reason_codes)
    for rule, cat, sev in _REASON_CATEGORY_BUMPS:
        if rule in rc:
            _bump_cat(severities, cat, sev)


def _apply_fact_category_severity(
    builder: _ReadinessBuilder,
    severities: Dict[str, int],
    goal_profile: str,
) -> None:
    """Fact floors for categories; competitive time-goal and sub-3 rules never apply to completion profile."""
    n_days = _training_day_count(builder.plan_request)
    weeks = builder.weeks_to_race
    short_timeline = weeks is not None and weeks < _SHORT_TIMELINE_WEEKS
    completed_wk = int(
        _safe_int(builder.activity.get("completed_calendar_weeks_count")) or 0
    )
    lookback = int(_safe_int(builder.activity.get("lookback_weeks")) or 0)
    active_wk = int(_safe_int(builder.activity.get("active_weeks")) or 0)
    performance_profile = goal_profile != GOAL_PROFILE_COMPLETION

    if builder.activities_found <= 0:
        _bump_cat(severities, CATEGORY_DATA_CONFIDENCE, _SEV_BAD)
    elif builder.activities_found < 3:
        _bump_cat(severities, CATEGORY_DATA_CONFIDENCE, _SEV_WARN)
    elif builder.activities_found > 0 and completed_wk == 0:
        _bump_cat(severities, CATEGORY_DATA_CONFIDENCE, _SEV_WARN)

    if (
        builder.goal_demand == "UNSPECIFIED"
        or builder.ambition_stance == "INSUFFICIENT_GOAL_CONTEXT"
    ):
        _bump_cat(severities, CATEGORY_GOAL_DEMAND, _SEV_BAD)
    elif builder.ambition_stance in ("HIGH_TENSION", "MANAGEABLE_TENSION"):
        _bump_cat(severities, CATEGORY_GOAL_DEMAND, _SEV_WARN)

    if builder.is_sub3_marathon:
        if n_days <= 3:
            _bump_cat(severities, CATEGORY_TRAINING_AVAILABILITY, _SEV_BAD)
        elif n_days == 4 and builder.baseline_band != "ESTABLISHED":
            _bump_cat(severities, CATEGORY_TRAINING_AVAILABILITY, _SEV_WARN)
    elif (
        performance_profile
        and _is_marathon(builder.plan_request)
        and _is_target_time_goal(builder.plan_request)
        and n_days <= 3
    ):
        _bump_cat(severities, CATEGORY_TRAINING_AVAILABILITY, _SEV_WARN)

    tdays = builder.plan_request.get("training_days")
    lr = builder.plan_request.get("long_run_day")
    if (
        isinstance(tdays, list)
        and lr
        and str(lr).strip()
        and str(lr).strip() not in tdays
    ):
        _bump_cat(severities, CATEGORY_TRAINING_AVAILABILITY, _SEV_WARN)

    band = builder.baseline_band
    if band == "THIN":
        _bump_cat(severities, CATEGORY_VOLUME_BASELINE, _SEV_WARN)
        if (
            performance_profile
            and _is_marathon(builder.plan_request)
            and _is_target_time_goal(builder.plan_request)
        ):
            _bump_cat(severities, CATEGORY_VOLUME_BASELINE, _SEV_BAD)
    elif band == "MODERATE" and builder.is_sub3_marathon:
        _bump_cat(severities, CATEGORY_VOLUME_BASELINE, _SEV_WARN)

    if (
        builder.is_sub3_marathon
        and builder.avg_mpw < _SUB3_VERY_LOW_MPW
        and builder.longest_run_miles < _SUB3_SHORT_LONG_RUN_MILES
    ):
        _bump_cat(severities, CATEGORY_VOLUME_BASELINE, _SEV_BAD)
        _bump_cat(severities, CATEGORY_LONG_RUN_DURABILITY, _SEV_BAD)
    elif builder.is_sub3_marathon and (
        builder.longest_run_miles < _SUB3_ADEQUATE_LONG_RUN_MILES
        or builder.avg_mpw < _SUB3_ESTABLISHED_MIN_MPW
    ):
        _bump_cat(severities, CATEGORY_LONG_RUN_DURABILITY, _SEV_WARN)
        _bump_cat(severities, CATEGORY_VOLUME_BASELINE, _SEV_WARN)

    if (
        performance_profile
        and _is_marathon(builder.plan_request)
        and _is_target_time_goal(builder.plan_request)
        and builder.longest_run_miles > 0
        and builder.longest_run_miles < 8.0
    ):
        _bump_cat(severities, CATEGORY_LONG_RUN_DURABILITY, _SEV_WARN)

    if builder.is_sub3_marathon and short_timeline:
        _bump_cat(severities, CATEGORY_TIMELINE, _SEV_BAD)
    elif (
        performance_profile
        and _is_marathon(builder.plan_request)
        and _is_target_time_goal(builder.plan_request)
        and short_timeline
    ):
        _bump_cat(severities, CATEGORY_TIMELINE, _SEV_WARN)

    if (
        lookback >= _CONSISTENCY_LOOKBACK_MIN_WEEKS
        and active_wk > 0
        and active_wk / float(max(lookback, 1)) < _CONSISTENCY_ACTIVE_WEEK_RATIO_WARN
    ):
        _bump_cat(severities, CATEGORY_CONSISTENCY, _SEV_WARN)
        builder.add_reason("RULE_CONSISTENCY_SPARSE_ACTIVE_WEEKS")

    wmin_c = _safe_float(builder.activity.get("weekly_miles_min_completed"))
    wmax_c = _safe_float(builder.activity.get("weekly_miles_max_completed"))
    if (
        completed_wk >= _CONSISTENCY_MIN_COMPLETED_WEEKS_FOR_SPREAD
        and wmin_c is not None
        and wmax_c is not None
        and (wmax_c - wmin_c) >= _CONSISTENCY_WEEKLY_SPREAD_MI_WARN
    ):
        _bump_cat(severities, CATEGORY_CONSISTENCY, _SEV_WARN)
        builder.add_reason("RULE_CONSISTENCY_HIGH_WEEKLY_VARIANCE")

    if goal_profile != GOAL_PROFILE_COMPLETION and _effort_control_reliable(
        builder.activity
    ):
        if builder.activity.get("dominant_deviation_direction") == "too_hard":
            _bump_cat(severities, CATEGORY_EFFORT_CONTROL, _SEV_WARN)
            builder.add_reason("RULE_EFFORT_CONTROL_DOMINANT_TOO_HARD")

    unresolved = [
        str(x)
        for x in list(builder.alignment.get("unresolved_flags") or [])
        if str(x).strip()
    ]
    if builder.alignment and not builder.alignment.get("generation_ready", True):
        if unresolved:
            _bump_cat(severities, CATEGORY_TRAINING_AVAILABILITY, _SEV_WARN)


def _facts_goal_demand(builder: _ReadinessBuilder, goal_profile: str) -> Dict[str, Any]:
    return {
        "goal_profile": goal_profile,
        "primary_goal": builder.plan_request.get("primary_goal"),
        "target_time": builder.plan_request.get("target_time"),
        "goal_demand": builder.goal_demand or None,
        "ambition_stance": builder.ambition_stance or None,
    }


def _facts_performance_alignment(builder: _ReadinessBuilder) -> Dict[str, Any]:
    act = builder.activity
    gp = _marathon_goal_pace_sec_per_mi(builder.plan_request)
    out: Dict[str, Any] = {
        "pace_reliability": act.get("pace_reliability"),
        "runs_usable_pace_count": act.get("runs_usable_pace_count"),
        "typical_easy_pace_sec_per_mi": act.get("typical_easy_pace_sec_per_mi"),
        "best_sustained_endurance_pace_sec_per_mi": act.get(
            "best_sustained_endurance_pace_sec_per_mi"
        ),
        "hr_coverage_ratio": act.get("hr_coverage_ratio"),
        "goal_marathon_pace_sec_per_mi": round(gp, 1) if gp is not None else None,
    }
    if gp is not None:
        out["goal_marathon_pace_display"] = _fmt_pace_min_mi(gp)
        e = _safe_float(act.get("typical_easy_pace_sec_per_mi"))
        s = _safe_float(act.get("best_sustained_endurance_pace_sec_per_mi"))
        if e is not None:
            out["gap_easy_minus_goal_sec_per_mi"] = round(e - gp, 1)
            out["typical_easy_pace_display"] = _fmt_pace_min_mi(e)
        if s is not None:
            out["gap_sustained_minus_goal_sec_per_mi"] = round(s - gp, 1)
            out["best_sustained_pace_display"] = _fmt_pace_min_mi(s)
    return out


def _facts_training_availability(builder: _ReadinessBuilder) -> Dict[str, Any]:
    tdays = builder.plan_request.get("training_days")
    if isinstance(tdays, list):
        days = [str(d) for d in tdays if d]
    else:
        days = []
    return {
        "training_days": days,
        "training_day_count": len(days),
        "long_run_day": builder.plan_request.get("long_run_day"),
    }


def _facts_volume_baseline(builder: _ReadinessBuilder) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "avg_miles_per_week_approx": round(builder.avg_mpw, 1),
        "baseline_band": builder.baseline_band or None,
        "active_weeks": builder.activity.get("active_weeks"),
    }
    wmin = _safe_float(builder.activity.get("weekly_miles_min_completed"))
    wmax = _safe_float(builder.activity.get("weekly_miles_max_completed"))
    if wmin is not None:
        out["weekly_miles_min_completed"] = round(wmin, 1)
    if wmax is not None:
        out["weekly_miles_max_completed"] = round(wmax, 1)
    return out


def _facts_long_run(builder: _ReadinessBuilder) -> Dict[str, Any]:
    return {
        "longest_run_miles": round(builder.longest_run_miles, 1),
        "longest_run_date": builder.activity.get("longest_run_date"),
        "long_runs_ge_10_mi_count": builder.activity.get("long_runs_ge_10_mi_count"),
        "long_runs_ge_12_mi_count": builder.activity.get("long_runs_ge_12_mi_count"),
        "weeks_with_long_run_10plus": builder.activity.get(
            "weeks_with_long_run_10plus"
        ),
        "long_run_progression_trend": builder.activity.get(
            "long_run_progression_trend"
        ),
    }


def _facts_timeline(builder: _ReadinessBuilder) -> Dict[str, Any]:
    w = builder.weeks_to_race
    return {
        "weeks_to_race": round(w, 1) if w is not None else None,
    }


def _facts_data_confidence(builder: _ReadinessBuilder) -> Dict[str, Any]:
    return {
        "activities_found": builder.activities_found,
        "lookback_weeks": builder.activity.get("lookback_weeks"),
        "completed_calendar_weeks_count": builder.activity.get(
            "completed_calendar_weeks_count"
        ),
    }


def _facts_consistency(builder: _ReadinessBuilder) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "active_weeks": builder.activity.get("active_weeks"),
        "completed_calendar_weeks_count": builder.activity.get(
            "completed_calendar_weeks_count"
        ),
        "lookback_weeks": builder.activity.get("lookback_weeks"),
        "runs_per_week_approx": builder.activity.get("runs_per_week_approx"),
    }
    wmin = _safe_float(builder.activity.get("weekly_miles_min_completed"))
    wmax = _safe_float(builder.activity.get("weekly_miles_max_completed"))
    if wmin is not None:
        out["weekly_miles_min_completed"] = round(wmin, 1)
    if wmax is not None:
        out["weekly_miles_max_completed"] = round(wmax, 1)
    return out


def _facts_effort_control(builder: _ReadinessBuilder) -> Dict[str, Any]:
    return {
        "has_effort_control_signal": builder.activity.get("has_effort_control_signal"),
        "effort_signal_runs": builder.activity.get("effort_signal_runs"),
        "dominant_deviation_direction": builder.activity.get(
            "dominant_deviation_direction"
        ),
    }


_FACT_BUILDERS: Dict[str, Any] = {
    CATEGORY_PERFORMANCE_ALIGNMENT: _facts_performance_alignment,
    CATEGORY_TRAINING_AVAILABILITY: _facts_training_availability,
    CATEGORY_VOLUME_BASELINE: _facts_volume_baseline,
    CATEGORY_LONG_RUN_DURABILITY: _facts_long_run,
    CATEGORY_TIMELINE: _facts_timeline,
    CATEGORY_CONSISTENCY: _facts_consistency,
    CATEGORY_DATA_CONFIDENCE: _facts_data_confidence,
    CATEGORY_EFFORT_CONTROL: _facts_effort_control,
}


def _category_reason_codes(
    category_id: str,
    reason_codes: Sequence[str],
) -> List[str]:
    allowed = _REASON_CODES_BY_CATEGORY.get(category_id, frozenset())
    return [r for r in reason_codes if r in allowed]


def _build_category_assessments(
    builder: _ReadinessBuilder,
    *,
    goal_profile: str,
) -> List[Dict[str, Any]]:
    prior_reasons = list(builder.reason_codes)
    severities: Dict[str, int] = {c: _SEV_OK for c in CATEGORY_ORDER}
    _apply_reason_code_bumps(severities, prior_reasons)
    _apply_fact_category_severity(builder, severities, goal_profile)
    final_rc = _ordered_unique(builder.reason_codes)
    out: List[Dict[str, Any]] = []
    for cat in CATEGORY_ORDER:
        applies = _category_applies_to_goal(cat, goal_profile, builder)
        if applies:
            sev = severities.get(cat, _SEV_OK)
            codes = _category_reason_codes(cat, final_rc)
        else:
            sev = _SEV_OK
            codes = []
        if cat == CATEGORY_GOAL_DEMAND:
            fact_payload = _facts_goal_demand(builder, goal_profile)
        else:
            fact_payload = _FACT_BUILDERS[cat](builder)
        out.append(
            {
                "category_id": cat,
                "applies_to_goal": applies,
                "status": _STATUS_FROM_SEV[sev],
                "reason_codes": codes,
                "facts_used": _json_safe_facts(fact_payload),
            }
        )
    return out


COACH_ANALYSIS_FOR_LLM_SCHEMA = "coach_analysis_for_llm.v1.1"


def _main_concern_lines(
    plan_generation_readiness: Dict[str, Any],
    applicable_rows: List[Dict[str, Any]],
) -> List[str]:
    """Concern bullets from existing readiness only (no new policy)."""
    out: List[str] = []
    seen_lower: set[str] = set()

    def add(text: str) -> None:
        t = str(text).strip()
        if not t:
            return
        key = t.lower()
        if key in seen_lower:
            return
        seen_lower.add(key)
        out.append(t)

    for kf in plan_generation_readiness.get("key_findings") or []:
        add(str(kf))
    for lf in plan_generation_readiness.get("limiting_factors") or []:
        add(str(lf))
    for row in applicable_rows:
        st = str(row.get("status") or "")
        if st not in (STATUS_WARN, STATUS_BAD):
            continue
        cid = str(row.get("category_id") or "").replace("_", " ")
        codes = row.get("reason_codes") or []
        code_str = ", ".join(str(c) for c in codes if str(c).strip())
        line = f"{cid}: {st}"
        if code_str:
            line += f" ({code_str})"
        add(line)
    return out[:24]


def build_coach_analysis_for_llm(
    plan_generation_readiness: Dict[str, Any],
) -> Dict[str, Any]:
    """Deterministic UI + LLM-tone summary; derived only from readiness."""
    if not isinstance(plan_generation_readiness, dict):
        return {
            "schema_version": COACH_ANALYSIS_FOR_LLM_SCHEMA,
            "error": "invalid_readiness",
        }
    digest = plan_generation_readiness.get("inputs_digest") or {}
    rp_raw = plan_generation_readiness.get("recommended_path")
    rp = rp_raw if isinstance(rp_raw, dict) else {}
    decision = str(plan_generation_readiness.get("decision") or "").strip()
    goal_profile = str(plan_generation_readiness.get("goal_profile") or "").strip()

    facts_reviewed: List[Dict[str, str]] = []

    goal_parts: List[str] = []
    rd = digest.get("race_distance")
    if rd:
        goal_parts.append(str(rd))
    pg = digest.get("primary_goal")
    if pg:
        goal_parts.append(str(pg))
    tt = digest.get("target_time")
    if tt:
        goal_parts.append(f"target {tt}")
    if goal_parts:
        facts_reviewed.append({"label": "Goal", "value": " — ".join(goal_parts)})

    if goal_profile:
        facts_reviewed.append({"label": "Goal profile", "value": goal_profile})

    for row in plan_generation_readiness.get("category_assessments") or []:
        if row.get("category_id") != CATEGORY_TRAINING_AVAILABILITY:
            continue
        fu = row.get("facts_used") if isinstance(row.get("facts_used"), dict) else {}
        n = fu.get("training_day_count")
        days = fu.get("training_days")
        if n is not None or (isinstance(days, list) and len(days) > 0):
            parts: List[str] = []
            if n is not None:
                parts.append(f"{n} running day(s)/week")
            if isinstance(days, list) and days:
                day_names = [
                    str(d).strip().capitalize() for d in days if str(d).strip()
                ]
                if day_names:
                    parts.append(", ".join(day_names))
            if parts:
                facts_reviewed.append(
                    {"label": "Training schedule", "value": " — ".join(parts)}
                )
        break

    avg = digest.get("avg_miles_per_week_approx")
    if avg is None:
        avg = digest.get("avg_weekly_mileage_last_42d_mi")
    if avg is not None and str(avg).strip():
        facts_reviewed.append(
            {"label": "Recent mileage (approx)", "value": f"{avg} mi/week"}
        )

    longest = digest.get("longest_run_miles")
    if longest is None:
        longest = digest.get("longest_run_last_56d_mi")
    if longest is not None and str(longest).strip():
        facts_reviewed.append(
            {"label": "Longest recent run (approx)", "value": f"{longest} mi"}
        )

    weeks = digest.get("weeks_to_race")
    if weeks is not None and str(weeks).strip():
        facts_reviewed.append(
            {"label": "Timeline", "value": f"{weeks} week(s) to race"}
        )

    activities = digest.get("activities_found")
    if activities is None:
        activities = digest.get("activities_found_last_42d")
    lookback = digest.get("lookback_weeks")
    active = digest.get("active_weeks")
    ccw = digest.get("completed_calendar_weeks_count")
    coverage_bits: List[str] = []
    if activities is not None and str(activities).strip():
        coverage_bits.append(
            f"{activities} logged activities in sync lookback (coverage only, not fitness)"
        )
    if active is not None and lookback is not None and str(lookback).strip():
        coverage_bits.append(f"{active} active week(s) in ~{lookback} lookback week(s)")
    elif ccw is not None and str(ccw).strip():
        coverage_bits.append(f"{ccw} calendar week(s) with completed mileage data")
    if coverage_bits:
        facts_reviewed.append(
            {"label": "Data confidence (coverage)", "value": " — ".join(coverage_bits)}
        )

    applicable = [
        row
        for row in (plan_generation_readiness.get("category_assessments") or [])
        if isinstance(row, dict) and row.get("applies_to_goal") is True
    ]
    cat_lines: List[str] = []
    for row in applicable:
        cid = str(row.get("category_id") or "")
        status = str(row.get("status") or "")
        codes = row.get("reason_codes") or []
        code_str = ", ".join(str(c) for c in codes if str(c).strip())
        cat_lines.append(f"{cid}: {status}" + (f" ({code_str})" if code_str else ""))

    headline = str(rp.get("message") or "").strip()
    coach_read = headline
    if decision:
        coach_read = f"Decision: {decision}. {headline}".strip()

    rec_path_ui = _json_safe_facts(
        {
            "type": rp.get("type"),
            "message": rp.get("message"),
            "suggested_next_step": rp.get("suggested_next_step"),
        }
    )

    required_changes = [
        str(x)
        for x in (plan_generation_readiness.get("required_changes") or [])
        if str(x).strip()
    ]
    limiting_factors = [
        str(x)
        for x in (plan_generation_readiness.get("limiting_factors") or [])
        if str(x).strip()
    ]

    return {
        "schema_version": COACH_ANALYSIS_FOR_LLM_SCHEMA,
        "goal_profile": goal_profile,
        "decision": decision,
        "readiness_level": str(
            plan_generation_readiness.get("readiness_level") or ""
        ).strip(),
        "headline": headline,
        "coach_read": coach_read,
        "recommended_path": rec_path_ui,
        "required_changes": required_changes,
        "limiting_factors": limiting_factors,
        "key_findings": list(plan_generation_readiness.get("key_findings") or [])[:5],
        "main_concerns": _main_concern_lines(plan_generation_readiness, applicable),
        "facts_reviewed": facts_reviewed,
        "applicable_category_summaries": cat_lines[:24],
        "recommended_actions": list(
            plan_generation_readiness.get("allowed_user_actions") or []
        ),
        "enforcement_codes": list(plan_generation_readiness.get("reason_codes") or []),
    }


RUNNER_ANALYSIS_DISPLAY_SCHEMA = "runner_analysis_display.v1.1"

# User-facing concern copy keyed by deterministic rule codes (no new policy).
_RULE_CONCERN_COPY: Dict[str, str] = {
    "RULE_INVALID_READINESS_INPUT": "We need clean intake and activity inputs before planning.",
    "RULE_REQUIRED_PLAN_FIELDS_MISSING": "Some required plan details are still missing.",
    "RULE_ALIGNMENT_UNRESOLVED": "A few intake choices still need to be resolved before planning.",
    "RULE_INSUFFICIENT_GOAL_CONTEXT": "Your race goal still needs to be clearer before we plan around it.",
    "RULE_ACTIVITIES_FOUND_ZERO": "There’s no recent synced running history to anchor this plan on.",
    "RULE_SUB3_VERY_LOW_MILEAGE_AND_SHORT_LONG_RUN": (
        "Your current weekly volume and longest run are a long way from what this time goal "
        "demands—more base work comes first."
    ),
    "RULE_SUB3_THREE_DAYS_HIGH_RISK": (
        "Three runs per week is very low frequency for a marathon time goal this aggressive. "
        "Most successful builds **progress toward five or more running days per week over time**, "
        "not a token extra day, plus a real build in sustainable mileage and long-run durability."
    ),
    "RULE_SUB3_FOUR_DAYS_WEAK_BASELINE": (
        "Four days can work for some athletes, but your aerobic baseline still looks light for this "
        "target—you’ll need more consistent weekly running and volume before this plan is realistic."
    ),
    "RULE_SUB3_SHORT_TIMELINE": (
        "The calendar to race day is tight for absorbing this kind of training load."
    ),
    "RULE_SUB3_BASELINE_NOT_ESTABLISHED": (
        "Your recent mileage and long-run pattern don’t yet support stacking marathon-specific work "
        "for this target."
    ),
    "RULE_SUB3_ESTABLISHED_BASELINE": (
        "You have a respectable training backbone; the remaining question is how hard you want to push the goal."
    ),
    "RULE_MARATHON_TIME_TARGET_THIN_BASELINE": (
        "Your recent training volume is thin for a strong marathon time goal—"
        "we’d need a steadier aerobic base."
    ),
    "RULE_MARATHON_TIME_TARGET_SHORT_TIMELINE": (
        "There isn’t much runway left to build durability before race day."
    ),
    "RULE_TENSION_AFTER_ALIGNMENT": (
        "Your goal and recent training pattern still don’t line up cleanly—worth pausing before we commit."
    ),
    "RULE_COMPLETION_MARATHON_TIMELINE_CRITICAL": (
        "The timeline to race day is very tight for a first marathon build."
    ),
    "RULE_COMPLETION_MARATHON_SHORT_RAMP": (
        "Both volume and long-run progression look rushed for the timeline you chose."
    ),
    "RULE_CONSISTENCY_SPARSE_ACTIVE_WEEKS": (
        "Your training weeks are hit-or-miss, which makes progression harder to rely on."
    ),
    "RULE_CONSISTENCY_HIGH_WEEKLY_VARIANCE": (
        "Weekly mileage jumps around a lot—consistency usually beats hero weeks for marathon fitness."
    ),
    "RULE_EFFORT_CONTROL_DOMINANT_TOO_HARD": (
        "A lot of your recent running skews hard; easier aerobic work may need more room in the picture."
    ),
    "RULE_PERFORMANCE_PACE_DATA_THIN": (
        "We don’t yet have enough **varied runs with dependable pace data** to compare your training paces fairly "
        "to your marathon goal pace—I'll weigh volume and durability more until the picture fills in."
    ),
    "RULE_PERFORMANCE_LARGE_GAP_EASY_VS_GOAL_PACE": (
        "Your **typical easy-day pace** is still **well slower** than the pace your goal implies for 26.2—"
        "that’s an aerobic capability gap experienced coaches take seriously."
    ),
    "RULE_PERFORMANCE_MODERATE_GAP_EASY_VS_GOAL_PACE": (
        "Your easy-running pace and your stated goal pace are **not in the same neighborhood** yet—"
        "not a forever verdict, but it means this sits as a **stretch** until training closes the gap."
    ),
    "RULE_PERFORMANCE_NO_SUSTAINED_PACE_NEAR_GOAL": (
        "Even on your **longer runs**, recent pacing is **still far from goal marathon pace** in a sustainable way—"
        "capability for the time target hasn’t shown up in what we can observe."
    ),
    "RULE_PERFORMANCE_STRETCH_SUSTAINED_VS_GOAL": (
        "Your best sustained long-run type pacing is **getting closer**, but it’s **still behind** what this goal "
        "usually requires over the full marathon."
    ),
    "RULE_LONG_RUN_PATTERN_THIN": (
        "Long-run **durability** looks thin—you’ve rarely repeated meaningful long work in this window, not just a "
        "single longest run."
    ),
    "RULE_LONG_RUN_FREQUENCY_LOW": (
        "Meaningful long runs aren’t showing up **often enough on the calendar** to match how an experienced coach "
        "would build marathon endurance."
    ),
    "RULE_LONG_RUN_RECENT_REGRESSION": (
        "Your long-run **arc is sliding backward** recently—coaches care about trend, not one hero week."
    ),
}


def _goal_profile_label_for_user(goal_profile: str) -> str:
    return {
        GOAL_PROFILE_COMPLETION: "Finish-the-race focus",
        GOAL_PROFILE_MODERATE_PERFORMANCE: "Moderate performance goal",
        GOAL_PROFILE_COMPETITIVE_PERFORMANCE: "High-demand marathon time goal",
    }.get(goal_profile, "Your stated goal")


def _is_sub3_marathon_digest(digest: Dict[str, Any]) -> bool:
    rd = str(digest.get("race_distance") or "").lower()
    if "marathon" not in rd or "half" in rd:
        return False
    secs = _parse_clock_seconds(digest.get("target_time"))
    return secs is not None and secs <= 3 * 3600


def _aggressive_marathon_goal(digest: Dict[str, Any], goal_profile: str) -> bool:
    if goal_profile == GOAL_PROFILE_COMPETITIVE_PERFORMANCE:
        return True
    secs = _parse_clock_seconds(digest.get("target_time"))
    if secs is None:
        return False
    rd = str(digest.get("race_distance") or "").lower()
    return (
        "marathon" in rd
        and "half" not in rd
        and secs <= _COMPETITIVE_MARATHON_MAX_SECONDS
    )


def _safe_float_fact(val: Any) -> Optional[float]:
    try:
        if val is None:
            return None
        return float(val)
    except (TypeError, ValueError):
        return None


def _mileage_interpretation(mpw: float, *, sub3: bool, aggressive: bool) -> str:
    if sub3:
        if mpw < 30:
            return (
                f"At ~{mpw:.0f} mi/week recently, you’re below the kind of chronic weekly load most "
                "sub-3 builds need later in a cycle—not a verdict, just a gap to respect."
            )
        if mpw < 50:
            return (
                f"~{mpw:.0f} mi/week is a workable starting point, but sub-3 training usually trends "
                "toward **meaningfully higher sustainable volume** over many weeks, earned carefully."
            )
        return (
            f"~{mpw:.0f} mi/week gives something to build from, but frequency and durability still have "
            "to catch up to what this time goal asks for."
        )
    if aggressive:
        if mpw < 25:
            return (
                "Weekly volume looks modest for a punchy marathon time goal—you’ll likely need "
                "more consistent miles over time."
            )
        return "Volume is part of the picture; we still need the schedule and endurance side to match the goal."
    if mpw < 15:
        return "Weekly mileage is on the low side for most marathon plans—we’d plan a patient build."
    return "We’ll use this snapshot to shape a sensible progression."


def _long_run_interpretation(miles: float, *, sub3: bool) -> str:
    if miles <= 0:
        return "No reliable long-run signal in the recent window we used."
    if sub3:
        if miles < 10:
            return (
                f"Your longest recent run (~{miles:.0f} mi) is still far from the long-run "
                "durability sub-3 plans typically grow into."
            )
        if miles < 16:
            return (
                f"A ~{miles:.0f} mi long run is a start; this goal usually demands **much more** "
                "marathon-specific endurance over months, not a quick jump."
            )
        return f"A ~{miles:.0f} mi long run is meaningful, but it’s only one piece of the durability picture."
    if miles < 8:
        return "Long runs are still short relative to many marathon builds—expect gradual extension over time."
    return "Long-run exposure will guide how aggressively we can progress."


def _race_month_year_phrase(digest: Dict[str, Any]) -> str:
    """User-facing race timing, e.g. ``October 2026`` — display only."""
    raw = digest.get("race_date")
    if raw is None:
        return "this goal race"
    try:
        if isinstance(raw, str) and len(raw.strip()) >= 10:
            d = datetime.strptime(raw.strip()[:10], "%Y-%m-%d").date()
            return d.strftime("%B %Y")
    except ValueError:
        pass
    return "this goal race"


def _compact_pace_and_pattern_facts(digest: Dict[str, Any]) -> List[Dict[str, str]]:
    """Single-line fact rows only (no coaching notes)."""
    rows: List[Dict[str, str]] = []
    gp = _safe_float_fact(digest.get("goal_marathon_pace_sec_per_mi"))
    if gp is not None:
        rows.append(
            {
                "title": "Goal marathon pace (from target time)",
                "summary": f"~{_fmt_pace_min_mi(gp)}",
            }
        )
    easy = _safe_float_fact(digest.get("typical_easy_pace_sec_per_mi"))
    if easy is not None:
        rows.append(
            {"title": "Typical training pace", "summary": f"~{_fmt_pace_min_mi(easy)}"}
        )
    sustained = _safe_float_fact(digest.get("best_sustained_endurance_pace_sec_per_mi"))
    if sustained is not None:
        rows.append(
            {
                "title": "Best sustained pace (8+ mi)",
                "summary": f"~{_fmt_pace_min_mi(sustained)}",
            }
        )
    n10 = digest.get("long_runs_ge_10_mi_count")
    ww = digest.get("weeks_with_long_run_10plus")
    if n10 is not None and ww is not None:
        rows.append(
            {
                "title": "Long-run pattern",
                "summary": f"{n10} runs ≥10 mi across {ww} calendar week(s)",
            }
        )
    elif n10 is not None:
        rows.append(
            {"title": "Long-run pattern", "summary": f"{n10} runs ≥10 mi (lookback)"}
        )
    pr = digest.get("pace_reliability")
    if pr and str(pr) in ("none", "low"):
        rows.append(
            {
                "title": "Pace data reliability",
                "summary": f"Limited ({pr}) — fewer usable pace samples in sync",
            }
        )
    return rows


def _main_reason_bullets(
    codes: Set[str],
    *,
    aggressive: bool,
    sub3: bool,
    n_run_days: int,
) -> List[str]:
    """Max 3 short bullets; themes only — avoids repeating long ``RULE_*`` template copy."""
    out: List[str] = []

    def add(line: str) -> None:
        if len(out) >= 3 or not line.strip():
            return
        key = line.strip().lower()
        if any(key == o.strip().lower() for o in out):
            return
        out.append(line.strip())

    perf_bad = codes & {
        "RULE_PERFORMANCE_LARGE_GAP_EASY_VS_GOAL_PACE",
        "RULE_PERFORMANCE_NO_SUSTAINED_PACE_NEAR_GOAL",
    }
    perf_mod = codes & {
        "RULE_PERFORMANCE_MODERATE_GAP_EASY_VS_GOAL_PACE",
        "RULE_PERFORMANCE_STRETCH_SUSTAINED_VS_GOAL",
    }
    if perf_bad:
        add("Observed training pace is **far** from goal marathon pace.")
    elif perf_mod:
        add("Training pace is still **well behind** goal marathon pace.")
    elif "RULE_PERFORMANCE_PACE_DATA_THIN" in codes and aggressive:
        add("Pace signal from synced runs is still **thin** for a full read.")

    if "RULE_SUB3_THREE_DAYS_HIGH_RISK" in codes or (
        aggressive and sub3 and n_run_days > 0 and n_run_days <= 3
    ):
        add("**Three** running days/week is **too low** for this standard.")
    elif "RULE_SUB3_FOUR_DAYS_WEAK_BASELINE" in codes or (
        aggressive and sub3 and n_run_days == 4
    ):
        add("**Four** days/week is usually **still short** for this standard.")

    if "RULE_LONG_RUN_PATTERN_THIN" in codes:
        add("Long-run **pattern** is thin — few repeated quality long efforts.")
    elif "RULE_LONG_RUN_FREQUENCY_LOW" in codes:
        add("Meaningful long runs show up **too rarely**.")
    elif "RULE_LONG_RUN_RECENT_REGRESSION" in codes:
        add("Long-run trend has **slipped** recently.")

    if len(out) >= 3:
        return out[:3]

    if "RULE_SUB3_SHORT_TIMELINE" in codes or (
        "RULE_MARATHON_TIME_TARGET_SHORT_TIMELINE" in codes
    ):
        add("**Timeline** to the race is **tight** for earning this goal safely.")
    if len(out) >= 3:
        return out[:3]
    if "RULE_MARATHON_TIME_TARGET_THIN_BASELINE" in codes or (
        "RULE_SUB3_BASELINE_NOT_ESTABLISHED" in codes
    ):
        add("Aerobic **base volume** is still **light** for this target.")
    if len(out) >= 3:
        return out[:3]
    if "RULE_SUB3_VERY_LOW_MILEAGE_AND_SHORT_LONG_RUN" in codes:
        add("**Volume** and **long run** are both far below this demand.")
    if len(out) >= 3:
        return out[:3]
    if "RULE_EFFORT_CONTROL_DOMINANT_TOO_HARD" in codes:
        add("Recent running skews **too hard** for easy aerobic development.")

    return out[:3]


def _strip_md_for_compare(s: str) -> str:
    return re.sub(r"\*+", "", s).lower()


def _dedupe_bullets_vs_verdict(verdict: str, bullets: Sequence[str]) -> List[str]:
    """Drop bullets that largely repeat the verdict (display-only de-duplication)."""
    v = _strip_md_for_compare(verdict)
    vwords = {w for w in re.findall(r"[a-z0-9]+", v) if len(w) > 2}
    out: List[str] = []
    for b in bullets:
        bb = _strip_md_for_compare(str(b))
        if not bb.strip():
            continue
        if bb in v:
            continue
        bwords = {w for w in re.findall(r"[a-z0-9]+", bb) if len(w) > 2}
        if bwords and vwords and len(bwords & vwords) / len(bwords) >= 0.55:
            continue
        out.append(str(b).strip())
        if len(out) >= 3:
            break
    return out


def _display_recommended_path(
    rp: Dict[str, Any],
    *,
    aggressive: bool,
    sub3: bool,
    codes: Set[str],
    n_run_days: int,
) -> Dict[str, str]:
    _ = (codes, n_run_days)
    ptype = str(rp.get("type") or "").strip()
    lead = ""
    support = ""

    if ptype == PATH_ADD_RUNNING_DAY and aggressive and sub3:
        lead = (
            "**Not a one-extra-day fix.** Earn **5–6 easy running days/week over time**, "
            "**sustainable mileage**, repeated **quality long runs**, and a smaller **pace gap** — then "
            "**reassess** the time goal."
        )
    elif ptype == PATH_ADD_RUNNING_DAY and aggressive:
        lead = "**Frequency first** — sustained weekly structure, not one cosmetic extra easy day."
    elif ptype == PATH_BUILD_BASE_FIRST and aggressive and sub3:
        lead = (
            "**Base phase first**: easy volume, steadier weeks, and **repeatable long runs** before this "
            "time target is grounded."
        )
    elif ptype == PATH_BUILD_BASE_FIRST and aggressive:
        lead = "**Build base first**: more easy aerobic volume and steadier weeks before this time goal is realistic."
    elif ptype == PATH_ADJUST_GOAL and aggressive and sub3:
        lead = "If structure and timeline won’t move, **the time goal** has to — sub-3 won’t bend to thin weeks."
    elif ptype == PATH_ADJUST_GOAL and aggressive:
        lead = "**Adjust the time goal** (or timeline/frequency) so the plan matches what training can support."
    elif ptype == PATH_ADJUST_TIMELINE and aggressive:
        lead = "**More runway** before the race is a clean lever — extra weeks to earn fitness safely."
    elif ptype == PATH_CREATE_PLAN:
        lead = str(rp.get("message") or "").strip()
    else:
        lead = str(rp.get("message") or "").strip()

    if not lead:
        lead = (
            "Pick what you’re willing to change below, then we can build responsibly."
        )

    out: Dict[str, str] = {"lead": lead}
    if support:
        out["support"] = support
    return out


def _coach_verdict_user(
    r: Dict[str, Any],
    digest: Dict[str, Any],
    *,
    aggressive: bool,
    sub3: bool,
    codes: Set[str],
    n_run_days: int,
) -> str:
    _ = n_run_days
    decision = str(r.get("decision") or "").strip()
    lvl = str(r.get("readiness_level") or "").strip()
    gp_label = _goal_profile_label_for_user(str(r.get("goal_profile") or ""))
    when = _race_month_year_phrase(digest)

    if decision == DECISION_ALLOW and lvl == LEVEL_READY:
        return (
            f"Based on what we can see, you’re **reasonable to plan forward** for this marathon "
            f"({when}). ({gp_label})"
        )

    if decision == DECISION_ALLOW and lvl == LEVEL_STRETCH:
        if sub3 and aggressive:
            return (
                f"This is a **serious stretch** for {when}. We can still build a plan — treat it as "
                "**patient development** on frequency, volume, durability, and pace, not a quick bridge."
            )
        return (
            "This goal is a **stretch** from your current baseline — expect a **consistency-first** build "
            f"for {when}."
        )

    if decision != DECISION_ALLOW and aggressive and sub3:
        s1 = f"You are **not** currently in **sub-3 marathon shape** for **{when}**."
        s2 = (
            "The gap is **structural**: aerobic development, weekly frequency, long-run durability, "
            "and observed pace — not a small schedule tweak."
        )
        s3 = (
            "Treat **sub-3 as a longer-term target** for this cycle unless you **change the race goal** "
            "or **move the race**."
        )
        if "RULE_PERFORMANCE_PACE_DATA_THIN" in codes and not (
            codes
            & {
                "RULE_PERFORMANCE_LARGE_GAP_EASY_VS_GOAL_PACE",
                "RULE_PERFORMANCE_NO_SUSTAINED_PACE_NEAR_GOAL",
            }
        ):
            return f"{s1} {s2} Pace data is still **limited** — I’ll weight rhythm and volume until it firms up. {s3}"
        return f"{s1} {s2} {s3}"

    if decision != DECISION_ALLOW and aggressive:
        return (
            f"You’re **not** lined up with this **aggressive marathon time goal** for **{when}** yet. "
            "The levers are **frequency**, **durability**, **base volume**, and **pace evidence** — "
            "**adjust goal, timeline, or weekly structure** before locking a plan."
        )

    rp = (
        r.get("recommended_path") if isinstance(r.get("recommended_path"), dict) else {}
    )
    fallback = str(rp.get("message") or "").strip()
    if fallback:
        return fallback
    return "Let’s adjust a few inputs before we generate your plan."


def build_runner_analysis_display(
    plan_generation_readiness: Dict[str, Any],
) -> Dict[str, Any]:
    """Deterministic, user-facing Runner Analysis only—no engine enums or RULE_* labels."""

    if not isinstance(plan_generation_readiness, dict):
        return {
            "schema_version": RUNNER_ANALYSIS_DISPLAY_SCHEMA,
            "error": "invalid_readiness",
        }

    digest = plan_generation_readiness.get("inputs_digest") or {}
    digest = digest if isinstance(digest, dict) else {}
    goal_profile = str(plan_generation_readiness.get("goal_profile") or "").strip()
    reason_codes = list(plan_generation_readiness.get("reason_codes") or [])
    codes = {str(c).strip() for c in reason_codes if str(c).strip()}
    rp_raw = plan_generation_readiness.get("recommended_path")
    rp = rp_raw if isinstance(rp_raw, dict) else {}

    aggressive = _aggressive_marathon_goal(digest, goal_profile)
    sub3 = _is_sub3_marathon_digest(digest)

    n_days = int(_safe_int(digest.get("training_day_count")) or 0)
    run_days_list: List[str] = []
    for row in plan_generation_readiness.get("category_assessments") or []:
        if not isinstance(row, dict):
            continue
        if row.get("category_id") != CATEGORY_TRAINING_AVAILABILITY:
            continue
        fu = row.get("facts_used") if isinstance(row.get("facts_used"), dict) else {}
        td = fu.get("training_days")
        if isinstance(td, list):
            run_days_list = [str(d).strip() for d in td if str(d).strip()]
        break
    if n_days <= 0 and run_days_list:
        n_days = len(run_days_list)

    mpw = _safe_float_fact(digest.get("avg_miles_per_week_approx"))
    longest = _safe_float_fact(digest.get("longest_run_miles"))
    weeks = digest.get("weeks_to_race")
    activities = digest.get("activities_found")
    lookback = digest.get("lookback_weeks")
    active = digest.get("active_weeks")

    goal_line_parts: List[str] = []
    rd = digest.get("race_distance")
    if rd:
        goal_line_parts.append(str(rd))
    pg = digest.get("primary_goal")
    if pg:
        goal_line_parts.append(str(pg))
    tt = digest.get("target_time")
    if tt:
        goal_line_parts.append(f"target {tt}")
    goal_summary = " — ".join(goal_line_parts) if goal_line_parts else ""

    facts: List[Dict[str, str]] = []
    if goal_summary:
        facts.append({"title": "Goal", "summary": goal_summary})

    sched_summary = (
        f"{n_days} running days per week" if n_days else "Training days not set"
    )
    if run_days_list:
        sched_summary += f" ({', '.join(run_days_list)})"
    facts.append({"title": "Training rhythm", "summary": sched_summary})

    if mpw is not None:
        facts.append(
            {
                "title": "Recent weekly volume",
                "summary": f"~{mpw:.1f} mi/week (recent snapshot)",
            }
        )
    if longest is not None and longest > 0:
        facts.append(
            {
                "title": "Longest recent run",
                "summary": f"~{longest:.1f} mi",
            }
        )
    if aggressive:
        facts.extend(_compact_pace_and_pattern_facts(digest))
    if weeks is not None and str(weeks).strip():
        facts.append(
            {
                "title": "Timeline",
                "summary": f"{weeks} week(s) to race",
            }
        )
    if activities is not None and str(activities).strip():
        cov = f"{activities} logged runs in the lookback we used"
        if active is not None and lookback is not None:
            cov += f" · {active} active week(s) in ~{lookback} week window"
        facts.append(
            {
                "title": "Recent logs",
                "summary": cov,
            }
        )

    facts = facts[:12]

    coach_read = _coach_verdict_user(
        plan_generation_readiness,
        digest,
        aggressive=aggressive,
        sub3=sub3,
        codes=codes,
        n_run_days=n_days,
    )
    raw_bullets = _main_reason_bullets(
        codes,
        aggressive=aggressive,
        sub3=sub3,
        n_run_days=n_days,
    )
    why = _dedupe_bullets_vs_verdict(coach_read, raw_bullets)
    path_ui = _display_recommended_path(
        rp,
        aggressive=aggressive,
        sub3=sub3,
        codes=codes,
        n_run_days=n_days,
    )
    actions = [
        str(x)
        for x in (plan_generation_readiness.get("allowed_user_actions") or [])
        if str(x).strip()
    ]

    return {
        "schema_version": RUNNER_ANALYSIS_DISPLAY_SCHEMA,
        "coach_read": coach_read,
        "why_concerned": why,
        "facts": facts,
        "recommended_path": path_ui,
        "recommended_actions": actions,
    }


def _finalize(
    builder: _ReadinessBuilder,
    *,
    readiness_level: str,
    goal_profile: str,
    decision: Optional[str] = None,
) -> Dict[str, Any]:
    builder.add_standard_findings()
    category_assessments = _build_category_assessments(
        builder, goal_profile=goal_profile
    )
    reason_codes = _ordered_unique(builder.reason_codes)
    limiting_factors = _ordered_unique(builder.limiting_factors)
    required_changes = _ordered_unique(builder.required_changes)
    final_decision = decision or _decision_for_level(readiness_level)
    core: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "goal_profile": goal_profile,
        "decision": final_decision,
        "readiness_level": readiness_level,
        "confidence": _confidence(builder, readiness_level, goal_profile),
        "reason_codes": reason_codes,
        "key_findings": builder.key_findings[:5],
        "limiting_factors": limiting_factors,
        "required_changes": required_changes,
        "category_assessments": category_assessments,
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
        "inputs_digest": _input_digest(builder, goal_profile=goal_profile),
    }
    core["coach_analysis_for_llm"] = build_coach_analysis_for_llm(core)
    core["runner_analysis_display"] = build_runner_analysis_display(core)
    return core


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
            goal_profile=GOAL_PROFILE_MODERATE_PERFORMANCE,
        )

    builder = _ReadinessBuilder(plan_request, assessment_api)
    goal_profile = _infer_goal_profile(builder)
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
            goal_profile=goal_profile,
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
        return _finalize(
            builder,
            readiness_level=LEVEL_INSUFFICIENT_DATA,
            goal_profile=goal_profile,
        )

    if builder.ambition_stance == "INSUFFICIENT_GOAL_CONTEXT":
        builder.add_reason("RULE_INSUFFICIENT_GOAL_CONTEXT")
        builder.add_limiting_factor("insufficient_goal_context")
        builder.require("adjust_goal")
        return _finalize(
            builder,
            readiness_level=LEVEL_INSUFFICIENT_DATA,
            goal_profile=goal_profile,
        )

    if builder.activities_found == 0:
        builder.add_reason("RULE_ACTIVITIES_FOUND_ZERO")
        builder.add_limiting_factor("insufficient_activity_data")
        builder.require("collect_more_activity_data")
        return _finalize(
            builder,
            readiness_level=LEVEL_INSUFFICIENT_DATA,
            goal_profile=goal_profile,
        )

    _apply_marathon_performance_alignment_rules(builder, goal_profile, plan_request)
    _apply_long_run_quality_rules(builder, goal_profile, plan_request)

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
            return _finalize_evaluated(
                builder,
                readiness_level=LEVEL_CURRENTLY_UNREALISTIC,
                goal_profile=goal_profile,
            )
        if n_days <= 3:
            builder.add_reason("RULE_SUB3_THREE_DAYS_HIGH_RISK")
            builder.add_limiting_factor("few_run_days_for_sub3_marathon")
            builder.require("add_running_day")
            builder.require("adjust_goal")
            return _finalize_evaluated(
                builder,
                readiness_level=LEVEL_HIGH_RISK,
                goal_profile=goal_profile,
            )
        if n_days == 4 and builder.baseline_band != "ESTABLISHED":
            builder.add_reason("RULE_SUB3_FOUR_DAYS_WEAK_BASELINE")
            builder.add_limiting_factor("weak_baseline_for_sub3_marathon")
            builder.require("add_running_day")
            builder.require("adjust_goal")
            return _finalize_evaluated(
                builder,
                readiness_level=LEVEL_HIGH_RISK,
                goal_profile=goal_profile,
            )
        if short_timeline:
            builder.add_reason("RULE_SUB3_SHORT_TIMELINE")
            builder.add_limiting_factor("short_timeline_for_sub3_marathon")
            builder.require("adjust_timeline")
            builder.require("adjust_goal")
            return _finalize_evaluated(
                builder,
                readiness_level=LEVEL_HIGH_RISK,
                goal_profile=goal_profile,
            )
        if (
            builder.avg_mpw >= _SUB3_ESTABLISHED_MIN_MPW
            and builder.longest_run_miles >= _SUB3_ADEQUATE_LONG_RUN_MILES
        ):
            builder.add_reason("RULE_SUB3_ESTABLISHED_BASELINE")
            return _finalize_evaluated(
                builder,
                readiness_level=LEVEL_STRETCH,
                goal_profile=goal_profile,
            )

        builder.add_reason("RULE_SUB3_BASELINE_NOT_ESTABLISHED")
        builder.add_limiting_factor("baseline_not_established_for_sub3_marathon")
        builder.require("build_base_first")
        builder.require("adjust_goal")
        return _finalize_evaluated(
            builder,
            readiness_level=LEVEL_HIGH_RISK,
            goal_profile=goal_profile,
        )

    if goal_profile == GOAL_PROFILE_COMPLETION and _is_marathon(plan_request):
        if weeks is not None and weeks < _COMPLETION_MARATHON_CRITICAL_WEEKS:
            builder.add_reason("RULE_COMPLETION_MARATHON_TIMELINE_CRITICAL")
            builder.add_limiting_factor("completion_marathon_timeline_critical")
            builder.require("adjust_timeline")
            builder.require("adjust_goal")
            return _finalize_evaluated(
                builder,
                readiness_level=LEVEL_HIGH_RISK,
                goal_profile=goal_profile,
            )
        if (
            weeks is not None
            and weeks < _SHORT_TIMELINE_WEEKS
            and builder.longest_run_miles < 6.0
            and builder.avg_mpw < 18.0
        ):
            builder.add_reason("RULE_COMPLETION_MARATHON_SHORT_RAMP")
            builder.add_limiting_factor("completion_marathon_short_training_ramp")
            builder.require("adjust_timeline")
            builder.require("build_base_first")
            return _finalize_evaluated(
                builder,
                readiness_level=LEVEL_STRETCH,
                goal_profile=goal_profile,
            )

    if (
        goal_profile != GOAL_PROFILE_COMPLETION
        and _is_marathon(plan_request)
        and _is_target_time_goal(plan_request)
    ):
        if builder.baseline_band == "THIN":
            builder.add_reason("RULE_MARATHON_TIME_TARGET_THIN_BASELINE")
            builder.add_limiting_factor("thin_baseline_for_marathon_time_goal")
            builder.require("add_running_day")
            builder.require("adjust_goal")
            return _finalize_evaluated(
                builder,
                readiness_level=LEVEL_HIGH_RISK,
                goal_profile=goal_profile,
            )
        if short_timeline:
            builder.add_reason("RULE_MARATHON_TIME_TARGET_SHORT_TIMELINE")
            builder.add_limiting_factor("short_timeline_for_marathon_time_goal")
            builder.require("adjust_timeline")
            return _finalize_evaluated(
                builder,
                readiness_level=LEVEL_HIGH_RISK,
                goal_profile=goal_profile,
            )

    if builder.ambition_stance in ("HIGH_TENSION", "MANAGEABLE_TENSION"):
        builder.add_reason("RULE_TENSION_AFTER_ALIGNMENT")
        builder.add_limiting_factor("goal_training_tension")
        return _finalize_evaluated(
            builder,
            readiness_level=LEVEL_STRETCH,
            goal_profile=goal_profile,
        )

    builder.add_reason("RULE_DEFAULT_READY")
    return _finalize_evaluated(
        builder,
        readiness_level=LEVEL_READY,
        goal_profile=goal_profile,
    )
