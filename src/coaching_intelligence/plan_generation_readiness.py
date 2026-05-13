"""
Plan generation readiness (v2.2).

Deterministic coaching recommendation layer for deciding whether the current
runner profile supports generating the requested plan. This module is pure:
no planner imports, no database access, no LLM calls.

v2 adds ``category_assessments`` (ok / warn / bad). v2.1 gates the strictest
**performance_alignment** rules by ``goal_profile`` (completion vs moderate vs competitive). v2.2 adds
**performance_alignment** (pace vs marathon goal pace, reliability-gated),
moderate marathon **developmental** pace warnings (distinct ``RULE_MODERATE_*``),
extends **long-run durability** with pattern signals from the activity snapshot,
and keeps **one** policy surface in this module.

``activities_found`` is a data-confidence signal only, never a fitness proxy.

**Goal profiles (policy defaults):**

- **completion** — finish / no target time / first marathon or just-finish wording.
- **moderate_performance** — PR, strong finish, or marathon target time **strictly slower than 3:30:00**.
- **competitive_performance** — marathon **<= 3:30:00**, sub-3 branch, BQ-style intent, or
  thin-baseline time-target tension (see ``STANCE_HIGH_TENSION_TIME_VS_THIN_BASELINE`` in
  ambition ``attributions``; ``ambition_gap.stance`` is legacy for snapshots only).
  Readiness gates on tension use attributions only — see ``docs/plan_cleanup_tracker.md``.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from src.coaching_intelligence.policy.deficits import compute_deficits
from src.coaching_intelligence.policy.demand import (
    compute_demand_score,
    interpolated_pace_gap_thresholds,
    pace_missing_triggers_thin_data,
)
from src.coaching_intelligence.policy.suggestions import derive_suggestions
from src.coaching_intelligence.contracts.runner_evidence import RunnerEvidenceSummary
from src.coaching_intelligence.contracts.readiness_verdict import (
    READINESS_SUMMARY_SCHEMA,
)
from src.coaching_intelligence.policy.policy_table import (
    POLICY_VERSION,
    competitive_marathon_max_seconds as _COMPETITIVE_MARATHON_MAX_SECONDS,
    competitive_perf_easy_gap_bad_sec,
    competitive_perf_easy_gap_warn_sec,
    competitive_perf_sustained_gap_bad_sec,
    competitive_perf_sustained_gap_warn_sec,
    completion_marathon_critical_weeks as _COMPLETION_MARATHON_CRITICAL_WEEKS,
    completion_marathon_short_ramp_long_run_mi,
    completion_marathon_short_ramp_mpw,
    consistency_active_week_ratio_warn as _CONSISTENCY_ACTIVE_WEEK_RATIO_WARN,
    consistency_lookback_min_weeks as _CONSISTENCY_LOOKBACK_MIN_WEEKS,
    consistency_min_completed_weeks_for_spread as _CONSISTENCY_MIN_COMPLETED_WEEKS_FOR_SPREAD,
    consistency_weekly_spread_mi_warn as _CONSISTENCY_WEEKLY_SPREAD_MI_WARN,
    effort_control_min_runs as _EFFORT_CONTROL_MIN_RUNS,
    longest_run_durability_floor_mi,
    marathon_distance_mi as _MARATHON_DISTANCE_MI,
    moderate_perf_easy_gap_warn_sec as _MODERATE_PERF_EASY_GAP_WARN_SEC,
    moderate_perf_sustained_gap_warn_sec as _MODERATE_PERF_SUSTAINED_GAP_WARN_SEC,
    required_plan_fields as _REQUIRED_PLAN_FIELDS,
    short_timeline_weeks as _SHORT_TIMELINE_WEEKS,
    sub3_adequate_long_run_miles as _SUB3_ADEQUATE_LONG_RUN_MILES,
    sub3_established_min_mpw as _SUB3_ESTABLISHED_MIN_MPW,
    sub3_seconds as _SUB3_SECONDS,
    sub3_short_long_run_miles as _SUB3_SHORT_LONG_RUN_MILES,
    sub3_very_low_mpw as _SUB3_VERY_LOW_MPW,
)

from src.coaching_intelligence.time_clock import (
    parse_clock_seconds as _parse_clock_seconds,
)

from src.coaching_intelligence.readiness_constants import (
    ACTION_ADD_RUNNING_DAY,
    ACTION_ADJUST_GOAL,
    ACTION_ADJUST_TIMELINE,
    ACTION_BUILD_BASE_FIRST,
    ACTION_CONTINUE_WITH_WARNING,
    ACTION_CREATE_PLAN,
    ACTION_INGEST_MORE_ACTIVITY,
    ACTION_PROVIDE_ALIGNMENT_ANSWERS,
    CATEGORY_CONSISTENCY,
    CATEGORY_DATA_CONFIDENCE,
    CATEGORY_EFFORT_CONTROL,
    CATEGORY_GOAL_DEMAND,
    CATEGORY_LONG_RUN_DURABILITY,
    CATEGORY_ORDER,
    CATEGORY_PERFORMANCE_ALIGNMENT,
    CATEGORY_TIMELINE,
    CATEGORY_TRAINING_AVAILABILITY,
    CATEGORY_VOLUME_BASELINE,
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    DECISION_ALLOW,
    DECISION_BLOCK,
    DECISION_DEFER,
    GOAL_PROFILE_COMPETITIVE_PERFORMANCE,
    GOAL_PROFILE_COMPLETION,
    GOAL_PROFILE_MODERATE_PERFORMANCE,
    LEVEL_CURRENTLY_UNREALISTIC,
    LEVEL_HIGH_RISK,
    LEVEL_INSUFFICIENT_DATA,
    LEVEL_READY,
    LEVEL_STRETCH,
    PATH_ADD_RUNNING_DAY,
    PATH_ADJUST_GOAL,
    PATH_ADJUST_TIMELINE,
    PATH_BUILD_BASE_FIRST,
    PATH_CREATE_PLAN,
    PATH_INGEST_MORE_ACTIVITY,
    PATH_PROVIDE_ALIGNMENT,
    RULE_MODERATE_PERFORMANCE_PACE_GAP,
    STATUS_BAD,
    STATUS_OK,
    STATUS_WARN,
    _DEVELOPMENTAL_MODERATE_MARATHON_RECOMMENDED_PATH,
    _DEVELOPMENTAL_MODERATE_MARATHON_PATH_MESSAGE,
)
from src.coaching_intelligence.readiness_json import _json_safe_facts, _json_safe_scalar
from src.coaching_intelligence.composers.display import (
    _is_sub3_marathon_digest,
    build_runner_analysis_display,
)

SCHEMA_VERSION = "plan_generation_readiness.v2.2"


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
    activity_raw = assessment_api.get("activity_summary")
    activity = dict(activity_raw) if isinstance(activity_raw, dict) else {}
    rev = assessment_api.get("runner_evidence")
    if isinstance(rev, dict):
        for k in (
            "weekly_mileage_history",
            "consistency_weeks_active_in_history",
            "history_lookback_weeks",
        ):
            if k in rev:
                activity[k] = rev[k]
    ambition = assessment_api.get("ambition_gap")
    alignment = assessment_api.get("intake_alignment_state")
    return (
        activity,
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
        rev_raw = assessment_api.get("runner_evidence")
        if isinstance(rev_raw, dict):
            self.evidence: RunnerEvidenceSummary = RunnerEvidenceSummary.from_api_dict(
                rev_raw
            )
        else:
            self.evidence = RunnerEvidenceSummary.from_activity_summary(
                dict(self.activity)
            )
        self.reason_codes: List[str] = []
        self.key_findings: List[str] = []
        self.limiting_factors: List[str] = []
        self.required_changes: List[str] = []

    def activity_signal(self, key: str, default: Any = None) -> Any:
        """Prefer ``runner_evidence`` payload; fall back to ``activity_summary`` merge."""
        if key in self.evidence.data:
            return self.evidence.data[key]
        return self.activity.get(key, default)

    @property
    def activity_signals(self) -> Dict[str, Any]:
        """Merged activity keys for dict-shaped consumers (deficits, facts)."""
        out = dict(self.activity)
        out.update(self.evidence.data)
        return out

    @property
    def avg_mpw(self) -> float:
        return _safe_float(self.activity_signal("avg_miles_per_week_approx")) or 0.0

    @property
    def longest_run_miles(self) -> float:
        return _safe_float(self.activity_signal("longest_run_miles")) or 0.0

    @property
    def activities_found(self) -> int:
        return _safe_int(self.activity_signal("activities_found")) or 0

    @property
    def baseline_band(self) -> str:
        return str(self.ambition.get("baseline_band") or "").strip()

    @property
    def goal_demand(self) -> str:
        return str(self.ambition.get("goal_demand") or "").strip()

    @property
    def ambition_stance(self) -> str:
        """Legacy snapshot field from ``ambition_gap`` — prefer ``ambition_attribution_codes`` for branching."""
        return str(self.ambition.get("stance") or "").strip()

    def ambition_attribution_codes(self) -> Set[str]:
        raw = self.ambition.get("attributions") or []
        return {str(x).strip() for x in raw if str(x).strip()}

    def ambition_insufficient_goal_context(self) -> bool:
        if self.goal_demand == "UNSPECIFIED":
            return True
        return "STANCE_INSUFFICIENT_GOAL_CONTEXT" in self.ambition_attribution_codes()

    def ambition_time_goal_tension(self) -> bool:
        s = self.ambition_attribution_codes()
        return (
            "STANCE_HIGH_TENSION_TIME_VS_THIN_BASELINE" in s
            or "STANCE_MANAGEABLE_TENSION_TIME_VS_MODERATE_BASELINE" in s
        )

    def ambition_high_tension_thin_baseline(self) -> bool:
        return (
            "STANCE_HIGH_TENSION_TIME_VS_THIN_BASELINE"
            in self.ambition_attribution_codes()
        )

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
    thin-baseline time-target tension (ambition attribution) → competitive; else marathon time slower than
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
            if builder.ambition_high_tension_thin_baseline():
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
        if goal_profile == GOAL_PROFILE_COMPLETION:
            return False
        return bool(
            _is_marathon(builder.plan_request)
            and _is_target_time_goal(builder.plan_request)
            and goal_profile
            in (
                GOAL_PROFILE_COMPETITIVE_PERFORMANCE,
                GOAL_PROFILE_MODERATE_PERFORMANCE,
            )
        )
    if category_id == CATEGORY_EFFORT_CONTROL:
        if goal_profile == GOAL_PROFILE_COMPLETION:
            return False
        return _effort_control_reliable(builder.activity_signals)
    return True


def _apply_marathon_pace_alignment(
    builder: _ReadinessBuilder,
    plan_request: Dict[str, Any],
    goal_pace: float,
    demand_score: float,
    goal_profile: str,
) -> None:
    """Interpolate competitive vs moderate pace gates using continuous ``demand_score`` (Wave 4)."""
    _ = plan_request
    rel = str(builder.activity_signal("pace_reliability") or "none")
    if rel in ("none", "low"):
        if pace_missing_triggers_thin_data(demand_score):
            builder.add_reason("RULE_PERFORMANCE_PACE_DATA_THIN")
            builder.add_limiting_factor("thin_pace_data_for_time_goal")
        return

    ew, eb, sw, sb = interpolated_pace_gap_thresholds(
        demand_score,
        moderate_easy_warn=_MODERATE_PERF_EASY_GAP_WARN_SEC,
        moderate_sustained_warn=_MODERATE_PERF_SUSTAINED_GAP_WARN_SEC,
        competitive_easy_warn=competitive_perf_easy_gap_warn_sec,
        competitive_easy_bad=competitive_perf_easy_gap_bad_sec,
        competitive_sustained_warn=competitive_perf_sustained_gap_warn_sec,
        competitive_sustained_bad=competitive_perf_sustained_gap_bad_sec,
    )
    easy = _safe_float(builder.activity_signal("typical_easy_pace_sec_per_mi"))
    sustained = _safe_float(
        builder.activity_signal("best_sustained_endurance_pace_sec_per_mi")
    )
    t = max(0.0, min(1.0, float(demand_score)))
    merge_moderate_style = goal_profile == GOAL_PROFILE_MODERATE_PERFORMANCE or t <= 0.5
    easy_bad_hit = False
    sus_bad_hit = False
    merged_dev = False

    if easy is not None:
        gap = easy - goal_pace
        if gap > eb:
            easy_bad_hit = True
            builder.add_reason("RULE_PERFORMANCE_LARGE_GAP_EASY_VS_GOAL_PACE")
            builder.add_limiting_factor(
                "observed_easy_pace_far_from_goal_marathon_pace"
            )
            builder.require("adjust_goal")
        elif gap > ew:
            if merge_moderate_style:
                merged_dev = True
            else:
                builder.add_reason("RULE_PERFORMANCE_MODERATE_GAP_EASY_VS_GOAL_PACE")

    if sustained is not None:
        gap_s = sustained - goal_pace
        if gap_s > sb:
            sus_bad_hit = True
            builder.add_reason("RULE_PERFORMANCE_NO_SUSTAINED_PACE_NEAR_GOAL")
            builder.add_limiting_factor(
                "sustained_run_pace_not_near_goal_marathon_pace"
            )
            builder.require("adjust_goal")
        elif gap_s > sw:
            if merge_moderate_style:
                merged_dev = True
            else:
                builder.add_reason("RULE_PERFORMANCE_STRETCH_SUSTAINED_VS_GOAL")

    if merged_dev and not easy_bad_hit and not sus_bad_hit:
        builder.add_reason(RULE_MODERATE_PERFORMANCE_PACE_GAP)
        builder.add_limiting_factor("moderate_time_goal_pace_still_developmental")


def _apply_marathon_performance_alignment_rules(
    builder: _ReadinessBuilder,
    goal_profile: str,
    plan_request: Dict[str, Any],
) -> None:
    """Marathon target-time pace vs goal — interpolated by goal demand (Wave 4)."""
    if goal_profile == GOAL_PROFILE_COMPLETION:
        return
    if not (_is_marathon(plan_request) and _is_target_time_goal(plan_request)):
        return
    goal_pace = _marathon_goal_pace_sec_per_mi(plan_request)
    if goal_pace is None:
        return
    rd = str(plan_request.get("race_distance") or "")
    demand = compute_demand_score(goal_pace, rd)
    _apply_marathon_pace_alignment(
        builder, plan_request, goal_pace, demand, goal_profile
    )


def _moderate_marathon_compound_stress_count(
    builder: _ReadinessBuilder,
    plan_request: Dict[str, Any],
) -> int:
    """Signals used only with moderate pace-gap — escalate only when several axes are weak."""
    n = 0
    if _training_day_count(plan_request) <= 3:
        n += 1
    wk = builder.weeks_to_race
    if wk is not None and wk < _SHORT_TIMELINE_WEEKS:
        n += 1
    if builder.baseline_band == "THIN":
        n += 1
    rc = set(builder.reason_codes)
    if rc & {
        "RULE_CONSISTENCY_SPARSE_ACTIVE_WEEKS",
        "RULE_CONSISTENCY_HIGH_WEEKLY_VARIANCE",
    }:
        n += 1
    if 0 < builder.longest_run_miles < longest_run_durability_floor_mi:
        n += 1
    if 0 < builder.activities_found < 5:
        n += 1
    if 0 < builder.avg_mpw < _SUB3_VERY_LOW_MPW:
        n += 1
    return n


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
    lookback = int(_safe_int(builder.activity_signal("lookback_weeks")) or 0)
    if lookback < 4 or builder.activities_found < 3:
        return
    n10 = int(_safe_int(builder.activity_signal("long_runs_ge_10_mi_count")) or 0)
    weeks_lr = int(
        _safe_int(builder.activity_signal("weeks_with_long_run_10plus")) or 0
    )
    trend = str(builder.activity_signal("long_run_progression_trend") or "")

    if (
        builder.longest_run_miles >= longest_run_durability_floor_mi
        or builder.is_sub3_marathon
    ):
        if n10 <= 1 and builder.activities_found >= 5:
            builder.add_reason("RULE_LONG_RUN_PATTERN_THIN")
        if weeks_lr <= 1 and lookback >= 6 and n10 >= 1:
            builder.add_reason("RULE_LONG_RUN_FREQUENCY_LOW")
    if trend == "down" and builder.longest_run_miles >= longest_run_durability_floor_mi:
        builder.add_reason("RULE_LONG_RUN_RECENT_REGRESSION")


def _escalate_readiness_for_performance_alignment(
    builder: _ReadinessBuilder,
    goal_profile: str,
    plan_request: Dict[str, Any],
    level: str,
) -> str:
    if not (_is_marathon(plan_request) and _is_target_time_goal(plan_request)):
        return level
    rc = set(builder.reason_codes)

    if goal_profile == GOAL_PROFILE_MODERATE_PERFORMANCE:
        if RULE_MODERATE_PERFORMANCE_PACE_GAP not in rc:
            return level
        rel = str(builder.activity_signal("pace_reliability") or "none")
        if rel in ("none", "low"):
            return level
        stress = _moderate_marathon_compound_stress_count(builder, plan_request)
        if stress >= 2 and level in (LEVEL_READY, LEVEL_STRETCH):
            return LEVEL_HIGH_RISK
        if level == LEVEL_READY:
            return LEVEL_STRETCH
        return level

    if goal_profile != GOAL_PROFILE_COMPETITIVE_PERFORMANCE:
        return level
    rel = str(builder.activity_signal("pace_reliability") or "none")
    if rel in ("none", "low"):
        return level
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
    trace_id: Optional[str] = None,
    evidence_snapshot_id: Optional[str] = None,
) -> Dict[str, Any]:
    final_level = _resolve_readiness_level_after_signals(
        builder, goal_profile, builder.plan_request, readiness_level
    )
    return _finalize(
        builder,
        readiness_level=final_level,
        goal_profile=goal_profile,
        decision=decision,
        trace_id=trace_id,
        evidence_snapshot_id=evidence_snapshot_id,
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
        goal_profile
        in (
            GOAL_PROFILE_COMPETITIVE_PERFORMANCE,
            GOAL_PROFILE_MODERATE_PERFORMANCE,
        )
        and _is_marathon(builder.plan_request)
        and _is_target_time_goal(builder.plan_request)
    ):
        pr = str(builder.activity_signal("pace_reliability") or "none")
        if pr in ("none", "low"):
            if out == CONFIDENCE_HIGH:
                out = CONFIDENCE_MEDIUM
            elif out == CONFIDENCE_MEDIUM:
                out = CONFIDENCE_LOW
        if "RULE_PERFORMANCE_PACE_DATA_THIN" in set(builder.reason_codes):
            out = CONFIDENCE_LOW
    return out


def _marathon_target_time_digest(digest: Dict[str, Any]) -> bool:
    """Marathon + explicit time-goal intent from intake digest (display/policy helper)."""
    rd = str(digest.get("race_distance") or "").lower()
    if "marathon" not in rd or "half" in rd:
        return False
    pg = str(digest.get("primary_goal") or "").lower()
    return "target" in pg


def _target_time_clock_seconds_leq_3h(digest: Dict[str, Any]) -> bool:
    secs = _parse_clock_seconds(digest.get("target_time"))
    if secs is None:
        return False
    return secs <= 3 * 3600


def _should_sub3_perf_large_gap_actions_adjust_goal_only(
    *,
    goal_profile: str,
    digest: Dict[str, Any],
    decision: str,
    readiness_level: str,
    reason_codes: Sequence[str],
) -> bool:
    """
    Suppress near-term ``add_running_day`` as a misleading remediation when the
    primary issue is **large** pace/capability gap on a **sub-3-class** marathon
    time goal — only ``adjust_goal`` remains in ``allowed_user_actions``.
    """
    if goal_profile != GOAL_PROFILE_COMPETITIVE_PERFORMANCE:
        return False
    if not _marathon_target_time_digest(digest):
        return False
    if not (
        _is_sub3_marathon_digest(digest) or _target_time_clock_seconds_leq_3h(digest)
    ):
        return False
    if not (
        decision != DECISION_ALLOW
        or readiness_level
        in (
            LEVEL_HIGH_RISK,
            LEVEL_CURRENTLY_UNREALISTIC,
        )
    ):
        return False
    rc = {str(c).strip() for c in reason_codes if str(c).strip()}
    if not (rc & _PERF_ALIGNMENT_BAD_REASON_CODES):
        return False
    return True


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
    goal_profile: str,
) -> Dict[str, str]:
    rc_set = {str(x) for x in reason_codes if str(x).strip()}
    if readiness_level == LEVEL_READY:
        return {
            "type": PATH_CREATE_PLAN,
            "message": "The requested plan is supported by the current profile.",
            "suggested_next_step": "Create the training plan.",
        }
    if readiness_level == LEVEL_STRETCH:
        if (
            goal_profile == GOAL_PROFILE_MODERATE_PERFORMANCE
            and RULE_MODERATE_PERFORMANCE_PACE_GAP in rc_set
        ):
            return _DEVELOPMENTAL_MODERATE_MARATHON_RECOMMENDED_PATH
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
    act = builder.activity_signals
    gp_pace = _marathon_goal_pace_sec_per_mi(builder.plan_request)
    demand_score = 0.0
    if (
        gp_pace is not None
        and _is_marathon(builder.plan_request)
        and _is_target_time_goal(builder.plan_request)
    ):
        demand_score = compute_demand_score(
            gp_pace, str(builder.plan_request.get("race_distance") or "")
        )
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
        "ambition_attributions": sorted(builder.ambition_attribution_codes()),
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
        "demand_score": round(demand_score, 4),
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
    (
        RULE_MODERATE_PERFORMANCE_PACE_GAP,
        CATEGORY_PERFORMANCE_ALIGNMENT,
        _SEV_WARN,
    ),
    ("RULE_PERFORMANCE_PACE_DATA_THIN", CATEGORY_PERFORMANCE_ALIGNMENT, _SEV_WARN),
    ("RULE_PERFORMANCE_PACE_DATA_THIN", CATEGORY_DATA_CONFIDENCE, _SEV_WARN),
    ("RULE_LONG_RUN_PATTERN_THIN", CATEGORY_LONG_RUN_DURABILITY, _SEV_WARN),
    ("RULE_LONG_RUN_FREQUENCY_LOW", CATEGORY_LONG_RUN_DURABILITY, _SEV_WARN),
    ("RULE_LONG_RUN_RECENT_REGRESSION", CATEGORY_LONG_RUN_DURABILITY, _SEV_WARN),
)

# Performance-alignment reasons filed as BAD (pace/capability gaps — not data-thin alone).
_PERF_ALIGNMENT_BAD_REASON_CODES: frozenset = frozenset(
    code
    for code, cat, sev in _REASON_CATEGORY_BUMPS
    if cat == CATEGORY_PERFORMANCE_ALIGNMENT and sev == _SEV_BAD
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
            RULE_MODERATE_PERFORMANCE_PACE_GAP,
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
        _safe_int(builder.activity_signal("completed_calendar_weeks_count")) or 0
    )
    lookback = int(_safe_int(builder.activity_signal("lookback_weeks")) or 0)
    active_wk = int(_safe_int(builder.activity_signal("active_weeks")) or 0)
    performance_profile = goal_profile != GOAL_PROFILE_COMPLETION

    if builder.activities_found <= 0:
        _bump_cat(severities, CATEGORY_DATA_CONFIDENCE, _SEV_BAD)
    elif builder.activities_found < 3:
        _bump_cat(severities, CATEGORY_DATA_CONFIDENCE, _SEV_WARN)
    elif builder.activities_found > 0 and completed_wk == 0:
        _bump_cat(severities, CATEGORY_DATA_CONFIDENCE, _SEV_WARN)

    if (
        builder.goal_demand == "UNSPECIFIED"
        or builder.ambition_insufficient_goal_context()
    ):
        _bump_cat(severities, CATEGORY_GOAL_DEMAND, _SEV_BAD)
    elif builder.ambition_time_goal_tension():
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
        and builder.longest_run_miles < longest_run_durability_floor_mi
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

    wmin_c = _safe_float(builder.activity_signal("weekly_miles_min_completed"))
    wmax_c = _safe_float(builder.activity_signal("weekly_miles_max_completed"))
    if (
        completed_wk >= _CONSISTENCY_MIN_COMPLETED_WEEKS_FOR_SPREAD
        and wmin_c is not None
        and wmax_c is not None
        and (wmax_c - wmin_c) >= _CONSISTENCY_WEEKLY_SPREAD_MI_WARN
    ):
        _bump_cat(severities, CATEGORY_CONSISTENCY, _SEV_WARN)
        builder.add_reason("RULE_CONSISTENCY_HIGH_WEEKLY_VARIANCE")

    if goal_profile != GOAL_PROFILE_COMPLETION and _effort_control_reliable(
        builder.activity_signals
    ):
        if builder.activity_signal("dominant_deviation_direction") == "too_hard":
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
    attrs = sorted(builder.ambition_attribution_codes())
    return {
        "goal_profile": goal_profile,
        "primary_goal": builder.plan_request.get("primary_goal"),
        "target_time": builder.plan_request.get("target_time"),
        "goal_demand": builder.goal_demand or None,
        "ambition_stance": builder.ambition_stance or None,
        "ambition_attributions": attrs,
    }


def _facts_performance_alignment(builder: _ReadinessBuilder) -> Dict[str, Any]:
    act = builder.activity_signals
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
        "active_weeks": builder.activity_signal("active_weeks"),
    }
    wmin = _safe_float(builder.activity_signal("weekly_miles_min_completed"))
    wmax = _safe_float(builder.activity_signal("weekly_miles_max_completed"))
    if wmin is not None:
        out["weekly_miles_min_completed"] = round(wmin, 1)
    if wmax is not None:
        out["weekly_miles_max_completed"] = round(wmax, 1)
    return out


def _facts_long_run(builder: _ReadinessBuilder) -> Dict[str, Any]:
    return {
        "longest_run_miles": round(builder.longest_run_miles, 1),
        "longest_run_date": builder.activity_signal("longest_run_date"),
        "long_runs_ge_10_mi_count": builder.activity_signal("long_runs_ge_10_mi_count"),
        "long_runs_ge_12_mi_count": builder.activity_signal("long_runs_ge_12_mi_count"),
        "weeks_with_long_run_10plus": builder.activity_signal(
            "weeks_with_long_run_10plus"
        ),
        "long_run_progression_trend": builder.activity_signal(
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
        "lookback_weeks": builder.activity_signal("lookback_weeks"),
        "completed_calendar_weeks_count": builder.activity_signal(
            "completed_calendar_weeks_count"
        ),
    }


def _facts_consistency(builder: _ReadinessBuilder) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "active_weeks": builder.activity_signal("active_weeks"),
        "completed_calendar_weeks_count": builder.activity_signal(
            "completed_calendar_weeks_count"
        ),
        "lookback_weeks": builder.activity_signal("lookback_weeks"),
        "runs_per_week_approx": builder.activity_signal("runs_per_week_approx"),
    }
    wmin = _safe_float(builder.activity_signal("weekly_miles_min_completed"))
    wmax = _safe_float(builder.activity_signal("weekly_miles_max_completed"))
    if wmin is not None:
        out["weekly_miles_min_completed"] = round(wmin, 1)
    if wmax is not None:
        out["weekly_miles_max_completed"] = round(wmax, 1)
    return out


def _facts_effort_control(builder: _ReadinessBuilder) -> Dict[str, Any]:
    return {
        "has_effort_control_signal": builder.activity_signal(
            "has_effort_control_signal"
        ),
        "effort_signal_runs": builder.activity_signal("effort_signal_runs"),
        "dominant_deviation_direction": builder.activity_signal(
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


def _build_readiness_summary(core: Dict[str, Any]) -> Dict[str, Any]:
    """Narrow wire shape for list views, push notifications, and thin clients.

    Omits category assessments, LLM coach blob, and full suggestions; use
    ``runner_analysis_display`` for chips, facts, and path copy.
    """
    disp = core.get("runner_analysis_display")
    coach_verdict = ""
    display_version: Optional[str] = None
    if isinstance(disp, dict) and not disp.get("error"):
        display_version = str(disp.get("schema_version") or "").strip() or None
        ver = disp.get("verdict")
        if isinstance(ver, dict):
            coach_verdict = str(ver.get("narrative") or "").strip()
        if not coach_verdict:
            coach_verdict = str(disp.get("coach_read") or "").strip()

    out: Dict[str, Any] = {
        "schema_version": READINESS_SUMMARY_SCHEMA,
        "decision": str(core.get("decision") or "").strip(),
        "readiness_level": str(core.get("readiness_level") or "").strip(),
        "goal_profile": str(core.get("goal_profile") or "").strip(),
        "confidence": core.get("confidence"),
        "demand_score": core.get("demand_score"),
        "reason_codes": [
            str(x).strip() for x in (core.get("reason_codes") or []) if str(x).strip()
        ],
        "allowed_user_actions": [
            str(x).strip()
            for x in (core.get("allowed_user_actions") or [])
            if str(x).strip()
        ],
        "required_changes": [
            str(x).strip()
            for x in (core.get("required_changes") or [])
            if str(x).strip()
        ],
        "policy_version": str(core.get("policy_version") or "").strip(),
    }
    if coach_verdict:
        out["coach_verdict"] = coach_verdict
    if display_version:
        out["runner_analysis_display_version"] = display_version
    tid = core.get("trace_id")
    if tid:
        out["trace_id"] = str(tid)
    eid = core.get("evidence_snapshot_id")
    if eid:
        out["evidence_snapshot_id"] = str(eid)
    return out


def _finalize(
    builder: _ReadinessBuilder,
    *,
    readiness_level: str,
    goal_profile: str,
    decision: Optional[str] = None,
    trace_id: Optional[str] = None,
    evidence_snapshot_id: Optional[str] = None,
) -> Dict[str, Any]:
    builder.add_standard_findings()
    category_assessments = _build_category_assessments(
        builder, goal_profile=goal_profile
    )
    reason_codes = _ordered_unique(builder.reason_codes)
    limiting_factors = _ordered_unique(builder.limiting_factors)
    required_changes = _ordered_unique(builder.required_changes)
    final_decision = decision or _decision_for_level(readiness_level)
    inputs_digest = _input_digest(builder, goal_profile=goal_profile)
    allowed_user_actions = _allowed_actions_for(
        decision=final_decision,
        readiness_level=readiness_level,
        required_changes=required_changes,
    )
    if _should_sub3_perf_large_gap_actions_adjust_goal_only(
        goal_profile=goal_profile,
        digest=inputs_digest,
        decision=final_decision,
        readiness_level=readiness_level,
        reason_codes=reason_codes,
    ):
        allowed_user_actions = [ACTION_ADJUST_GOAL]
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
            goal_profile=goal_profile,
        ),
        "allowed_user_actions": allowed_user_actions,
        "inputs_digest": inputs_digest,
    }
    ds = float(inputs_digest.get("demand_score") or 0.0)
    gp_eval = _marathon_goal_pace_sec_per_mi(builder.plan_request)
    act_d = builder.activity_signals
    deficits_obj = compute_deficits(
        act_d,
        builder.plan_request,
        demand_score=ds,
        goal_marathon_pace_sec_per_mi=gp_eval,
        weeks_to_race=builder.weeks_to_race,
    )
    suggestions_list = derive_suggestions(
        deficits_obj, builder.plan_request, allowed_user_actions
    )
    core["demand_score"] = round(ds, 4)
    core["deficits"] = deficits_obj.to_api_dict()
    core["suggestions"] = [s.to_api_dict() for s in suggestions_list]
    core["policy_version"] = str(POLICY_VERSION)
    if trace_id:
        core["trace_id"] = str(trace_id)
    if evidence_snapshot_id:
        core["evidence_snapshot_id"] = str(evidence_snapshot_id)
    core["runner_analysis_display"] = build_runner_analysis_display(core)
    core["readiness_summary"] = _build_readiness_summary(core)
    return core


def evaluate_plan_generation_readiness(
    *,
    plan_request: Dict[str, Any],
    assessment_api: Dict[str, Any],
    trace_id: Optional[str] = None,
    evidence_snapshot_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return the deterministic readiness decision for a requested plan.

    The LLM may explain this result, but callers must not let the LLM override
    ``decision`` or ``allowed_user_actions``.
    """
    param_eid = str(evidence_snapshot_id) if evidence_snapshot_id else None
    if not isinstance(plan_request, dict) or not isinstance(assessment_api, dict):
        plan = plan_request if isinstance(plan_request, dict) else {}
        assessment = assessment_api if isinstance(assessment_api, dict) else {}
        eid = param_eid
        if eid is None and isinstance(assessment, dict):
            xr = assessment.get("evidence_snapshot_id")
            if xr:
                eid = str(xr)
        builder = _ReadinessBuilder(plan, assessment)
        builder.add_reason("RULE_INVALID_READINESS_INPUT")
        builder.add_limiting_factor("invalid_state")
        builder.require("adjust_goal")
        return _finalize(
            builder,
            readiness_level=LEVEL_INSUFFICIENT_DATA,
            decision=DECISION_BLOCK,
            goal_profile=GOAL_PROFILE_MODERATE_PERFORMANCE,
            trace_id=trace_id,
            evidence_snapshot_id=eid,
        )

    resolved_evidence_snapshot_id = param_eid
    if resolved_evidence_snapshot_id is None:
        xr0 = assessment_api.get("evidence_snapshot_id")
        if xr0:
            resolved_evidence_snapshot_id = str(xr0)

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
            trace_id=trace_id,
            evidence_snapshot_id=resolved_evidence_snapshot_id,
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
            trace_id=trace_id,
            evidence_snapshot_id=resolved_evidence_snapshot_id,
        )

    if builder.ambition_insufficient_goal_context():
        builder.add_reason("RULE_INSUFFICIENT_GOAL_CONTEXT")
        builder.add_limiting_factor("insufficient_goal_context")
        builder.require("adjust_goal")
        return _finalize(
            builder,
            readiness_level=LEVEL_INSUFFICIENT_DATA,
            goal_profile=goal_profile,
            trace_id=trace_id,
            evidence_snapshot_id=resolved_evidence_snapshot_id,
        )

    if builder.activities_found == 0:
        builder.add_reason("RULE_ACTIVITIES_FOUND_ZERO")
        builder.add_limiting_factor("insufficient_activity_data")
        builder.require("collect_more_activity_data")
        return _finalize(
            builder,
            readiness_level=LEVEL_INSUFFICIENT_DATA,
            goal_profile=goal_profile,
            trace_id=trace_id,
            evidence_snapshot_id=resolved_evidence_snapshot_id,
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
                trace_id=trace_id,
                evidence_snapshot_id=resolved_evidence_snapshot_id,
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
                trace_id=trace_id,
                evidence_snapshot_id=resolved_evidence_snapshot_id,
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
                trace_id=trace_id,
                evidence_snapshot_id=resolved_evidence_snapshot_id,
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
                trace_id=trace_id,
                evidence_snapshot_id=resolved_evidence_snapshot_id,
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
                trace_id=trace_id,
                evidence_snapshot_id=resolved_evidence_snapshot_id,
            )

        builder.add_reason("RULE_SUB3_BASELINE_NOT_ESTABLISHED")
        builder.add_limiting_factor("baseline_not_established_for_sub3_marathon")
        builder.require("build_base_first")
        builder.require("adjust_goal")
        return _finalize_evaluated(
            builder,
            readiness_level=LEVEL_HIGH_RISK,
            goal_profile=goal_profile,
            trace_id=trace_id,
            evidence_snapshot_id=resolved_evidence_snapshot_id,
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
                trace_id=trace_id,
                evidence_snapshot_id=resolved_evidence_snapshot_id,
            )
        if (
            weeks is not None
            and weeks < _SHORT_TIMELINE_WEEKS
            and builder.longest_run_miles < completion_marathon_short_ramp_long_run_mi
            and builder.avg_mpw < completion_marathon_short_ramp_mpw
        ):
            builder.add_reason("RULE_COMPLETION_MARATHON_SHORT_RAMP")
            builder.add_limiting_factor("completion_marathon_short_training_ramp")
            builder.require("adjust_timeline")
            builder.require("build_base_first")
            return _finalize_evaluated(
                builder,
                readiness_level=LEVEL_STRETCH,
                goal_profile=goal_profile,
                trace_id=trace_id,
                evidence_snapshot_id=resolved_evidence_snapshot_id,
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
                trace_id=trace_id,
                evidence_snapshot_id=resolved_evidence_snapshot_id,
            )
        if short_timeline:
            builder.add_reason("RULE_MARATHON_TIME_TARGET_SHORT_TIMELINE")
            builder.add_limiting_factor("short_timeline_for_marathon_time_goal")
            builder.require("adjust_timeline")
            return _finalize_evaluated(
                builder,
                readiness_level=LEVEL_HIGH_RISK,
                goal_profile=goal_profile,
                trace_id=trace_id,
                evidence_snapshot_id=resolved_evidence_snapshot_id,
            )

    if builder.ambition_time_goal_tension():
        builder.add_reason("RULE_TENSION_AFTER_ALIGNMENT")
        builder.add_limiting_factor("goal_training_tension")
        return _finalize_evaluated(
            builder,
            readiness_level=LEVEL_STRETCH,
            goal_profile=goal_profile,
            trace_id=trace_id,
            evidence_snapshot_id=resolved_evidence_snapshot_id,
        )

    builder.add_reason("RULE_DEFAULT_READY")
    return _finalize_evaluated(
        builder,
        readiness_level=LEVEL_READY,
        goal_profile=goal_profile,
        trace_id=trace_id,
        evidence_snapshot_id=resolved_evidence_snapshot_id,
    )
