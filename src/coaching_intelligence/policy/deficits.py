"""Compute axis deficits for readiness display (Wave 4)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional

from src.coaching_intelligence.contracts.deficits import DEFICITS_SCHEMA, Deficits
from src.coaching_intelligence.policy import policy_table as pt
from src.coaching_intelligence.policy.demand import interpolated_pace_gap_thresholds


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


def compute_deficits(
    activity: Dict[str, Any],
    plan_request: Dict[str, Any],
    *,
    demand_score: float,
    goal_marathon_pace_sec_per_mi: Optional[float],
    weeks_to_race: Optional[float] = None,
) -> Deficits:
    """
    Approximate shortfalls vs demand-scaled targets (diagnostics / UI — not a second policy engine).

    Pace deficit uses the same interpolated easy-pace warn band as alignment (fraction ``0.65``).
    """
    vol_def: Optional[float] = None
    lr_def: Optional[float] = None
    pace_def: Optional[float] = None
    freq_def: Optional[float] = None

    mpw = float(activity.get("avg_miles_per_week_approx") or 0.0)
    peak_target = 22.0 + float(demand_score) * 33.0
    if peak_target > mpw:
        vol_def = round(peak_target - mpw, 1)

    lr = float(activity.get("longest_run_miles") or 0.0)
    lr_tgt = 8.0 + float(demand_score) * 12.0
    if lr_tgt > lr:
        lr_def = round(lr_tgt - lr, 1)

    if goal_marathon_pace_sec_per_mi is not None:
        easy_raw = activity.get("typical_easy_pace_sec_per_mi")
        rel = str(activity.get("pace_reliability") or "none")
        try:
            easy = float(easy_raw) if easy_raw is not None else None
        except (TypeError, ValueError):
            easy = None
        if easy is not None and rel not in ("none", "low"):
            ew, _, _, _ = interpolated_pace_gap_thresholds(
                demand_score,
                moderate_easy_warn=pt.moderate_perf_easy_gap_warn_sec,
                moderate_sustained_warn=pt.moderate_perf_sustained_gap_warn_sec,
                competitive_easy_warn=pt.competitive_perf_easy_gap_warn_sec,
                competitive_easy_bad=pt.competitive_perf_easy_gap_bad_sec,
                competitive_sustained_warn=pt.competitive_perf_sustained_gap_warn_sec,
                competitive_sustained_bad=pt.competitive_perf_sustained_gap_bad_sec,
            )
            cushion = float(goal_marathon_pace_sec_per_mi) + ew * 0.65
            pd = easy - cushion
            if pd > 0:
                pace_def = round(pd, 1)

    days = plan_request.get("training_days")
    if isinstance(days, list):
        ntrain = len([d for d in days if str(d or "").strip()])
        day_tgt = 3 + int(round(2.0 * float(demand_score)))
        if day_tgt > ntrain > 0:
            freq_def = float(day_tgt - ntrain)

    time_def: Optional[float] = None
    wtr = weeks_to_race
    if wtr is None:
        wtr = _weeks_until_race(plan_request)
    if (
        wtr is not None
        and _is_marathon(plan_request)
        and _is_target_time_goal(plan_request)
    ):
        wk_need = float(pt.marathon_min_weeks_before_race_low_demand) + float(
            demand_score
        ) * (
            float(pt.marathon_min_weeks_before_race_high_demand)
            - float(pt.marathon_min_weeks_before_race_low_demand)
        )
        short = wk_need - float(wtr)
        if short > 0:
            time_def = round(short, 1)

    return Deficits(
        schema_version=DEFICITS_SCHEMA,
        pace_deficit_sec_per_mi=pace_def,
        volume_deficit_mpw=vol_def,
        long_run_deficit_mi=lr_def,
        time_deficit_weeks=time_def,
        frequency_deficit_days=freq_def,
    )
