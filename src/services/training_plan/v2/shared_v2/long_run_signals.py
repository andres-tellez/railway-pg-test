from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from datetime import date, datetime, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.training_plan.calculations.week_utils import get_complete_weeks
from src.services.training_plan.v2.race_configs.base_config import RaceDistanceConfig
from src.services.training_plan.v2.shared_v2.rounding_utils import round_to_half_mile


def _median_of(values: List[float]) -> float:
    if not values:
        raise ValueError("_median_of requires a non-empty list")
    s = sorted(float(x) for x in values)
    n = len(s)
    m = n // 2
    if n % 2 == 1:
        return float(s[m])
    return (s[m - 1] + s[m]) / 2.0


def _last_three_weekly_long_runs(series: List[float]) -> List[float]:
    return [float(x) for x in series[: min(3, len(series))]]


def _consistent_recent_long_runs(
    most_recent: float, last_three: List[float], *, spread_mi: float = 1.0
) -> bool:
    """Most-recent and prior week are long-run–stable; third week cannot cliff from week-2.

    This week and last week are within ``spread_mi`` of each other and of
    ``most_recent``.     If a third week exists, it must not sit far below this week (``w2 < w0 - 1.15``),
    which flags a low week behind an otherwise stable pair (e.g. …, 16–18 vs 10–12).
    """
    if len(last_three) < 2:
        return False
    tol = spread_mi + 1e-6
    w0, w1 = float(last_three[0]), float(last_three[1])
    if abs(w0 - w1) > tol:
        return False
    if abs(w0 - most_recent) > tol or abs(w1 - most_recent) > tol:
        return False
    if len(last_three) >= 3:
        w2 = float(last_three[2])
        if w2 + 1e-6 < w0 - 1.15:
            return False
    return True


def _clear_downward_long_run_trend(series: List[float]) -> bool:
    """Most recent week materially below the lowest of the prior 1–2 long-run weeks."""
    if len(series) < 2:
        return False
    prior = [float(x) for x in series[1 : min(3, len(series))]]
    if not prior:
        return False
    tail_min = min(prior)
    return float(series[0]) + 0.25 < tail_min


def recent_longest_3w(activities: List[Dict[str, Any]], *, days: int = 21) -> float:
    """Return the longest single run within the last `days` days."""
    if not activities:
        return 0.0

    now = datetime.utcnow()
    cutoff = now - timedelta(days=days)
    longest = 0.0

    for activity in activities:
        date_str = (
            activity.get("date")
            or activity.get("start_date")
            or activity.get("startTime")
        )
        if not date_str:
            continue
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            continue
        if dt < cutoff:
            continue

        miles = _extract_miles(activity)
        if miles > longest:
            longest = miles

    return round(longest, 2)


def detect_consecutive_long_runs(
    activities: List[Dict[str, Any]], *, min_consecutive_weeks: int = 3
) -> Dict[str, Any]:
    """
    Detect whether the athlete has accumulated consecutive long runs that should
    trigger a recovery week.

    Also detects if the athlete has already self-regulated (recent reduction from peak)
    to avoid forcing a double recovery.
    """
    if not activities:
        return {
            "has_consecutive_runs": False,
            "consecutive_count": 0,
            "weekly_long_runs": [],
            "longest_recent": 0.0,
            "has_recent_reduction": False,
            "most_recent_long_run": 0.0,
        }

    weekly_data = get_complete_weeks(activities, max_weeks=4)
    if len(weekly_data) < min_consecutive_weeks:
        return {
            "has_consecutive_runs": False,
            "consecutive_count": 0,
            "weekly_long_runs": [],
            "longest_recent": 0.0,
            "has_recent_reduction": False,
            "most_recent_long_run": 0.0,
        }

    weekly_long_runs: List[float] = []
    for _, week_activities in list(weekly_data.items())[:4]:
        longest_in_week = 0.0
        has_any_runs = False

        for activity in week_activities:
            miles = _extract_miles(activity)
            if miles > 0:
                has_any_runs = True
            if miles > longest_in_week:
                longest_in_week = miles

        if has_any_runs or longest_in_week > 0:
            weekly_long_runs.append(round(longest_in_week, 2))

    if len(weekly_long_runs) < min_consecutive_weeks:
        most_recent = weekly_long_runs[0] if weekly_long_runs else 0.0
        return {
            "has_consecutive_runs": False,
            "consecutive_count": len(weekly_long_runs),
            "weekly_long_runs": weekly_long_runs,
            "longest_recent": max(weekly_long_runs) if weekly_long_runs else 0.0,
            "has_recent_reduction": False,
            "most_recent_long_run": most_recent,
        }

    consecutive_count = 0
    for lr in weekly_long_runs:
        if lr >= 8.0:
            consecutive_count += 1
        else:
            break

    has_consecutive = consecutive_count >= min_consecutive_weeks
    longest_recent = (
        max(weekly_long_runs[:consecutive_count]) if consecutive_count > 0 else 0.0
    )

    # Detect if user has already self-regulated (recent reduction from peak)
    # Pattern: [most_recent, ...previous weeks]
    # If most_recent < peak, user may have already reduced
    most_recent_long_run = weekly_long_runs[0] if weekly_long_runs else 0.0
    has_recent_reduction = False

    if len(weekly_long_runs) >= 2 and most_recent_long_run > 0 and longest_recent > 0:
        # Check if most recent week is lower than peak
        # Any reduction suggests user may have intentionally self-regulated
        # This avoids forcing double recovery when user already pulled back

        # If most recent is at least 5% lower than peak, it's likely intentional
        reduction_threshold = 0.05  # 5% reduction suggests intentional adjustment
        reduction_pct = (longest_recent - most_recent_long_run) / longest_recent

        if reduction_pct >= reduction_threshold:
            # Check if it's part of a downward trend (most recent < previous)
            # Pattern [14, 15, 15, 14] means most recent (14) < previous week (15)
            if (
                len(weekly_long_runs) >= 2
                and most_recent_long_run < weekly_long_runs[1]
            ):
                has_recent_reduction = True
            # Or if reduction is substantial (15%+), definitely intentional
            elif reduction_pct >= 0.15:
                has_recent_reduction = True

    return {
        "has_consecutive_runs": has_consecutive,
        "consecutive_count": consecutive_count,
        "weekly_long_runs": weekly_long_runs,
        "longest_recent": longest_recent,
        "has_recent_reduction": has_recent_reduction,
        "most_recent_long_run": most_recent_long_run,
    }


def calculate_recovery_week_long_run(
    longest_recent: float, *, config: RaceDistanceConfig, unit_system: str = "imperial"
) -> float:
    """Compute a safe recovery-week long run using config guardrails."""
    min_reduction = max(3.0, config.long_run_increment * 3)
    max_reduction = max(5.0, config.long_run_increment * 5)
    reduction_miles = min(
        max_reduction,
        max(min_reduction, longest_recent * 0.30),
    )
    recovery_by_reduction = longest_recent - reduction_miles

    recovery_by_percent = longest_recent * config.recovery_reduction_ratio

    recovery = min(recovery_by_reduction, recovery_by_percent)
    recovery = max(config.recovery_long_run_floor, recovery)

    return round_to_half_mile(recovery)


def _extract_miles(activity: Dict[str, Any]) -> float:
    """Best-effort extraction of miles from a Strava activity payload."""
    for key in ("miles", "distance_miles", "distance"):
        value = activity.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)

    meters = activity.get("distance_meters") or activity.get("meters")
    if isinstance(meters, (int, float)) and meters > 0:
        return float(meters) / 1609.34

    return 0.0


def get_athlete_id_for_user(session: Session, user_id: str) -> Optional[int]:
    """Helper function to get athlete_id from user_id."""
    result = session.execute(
        text(
            """
            SELECT athlete_id
            FROM public.user_athletes
            WHERE user_id = :uid
            LIMIT 1
            """
        ),
        {"uid": user_id},
    ).fetchone()

    return result.athlete_id if result else None


def _mv_weekly_runs_rows(session: Session, user_id: str) -> List[Dict[str, Any]]:
    """Return ``weekly_runs`` JSON rows from ``mv_longest_runs`` (most recent week first)."""
    athlete_id = get_athlete_id_for_user(session, user_id)
    if not athlete_id:
        return []
    result = session.execute(
        text("SELECT * FROM mv_longest_runs WHERE athlete_id = :athlete_id"),
        {"athlete_id": athlete_id},
    ).first()
    if not result or not result.weekly_runs:
        return []
    return list(result.weekly_runs)


def fetch_recent_weekly_long_run_distances(
    session: Session, user_id: str, *, max_weeks: int = 6
) -> List[float]:
    """Longest run distance per week for the last ``max_weeks`` weeks (most recent first).

    Only weeks with a positive ``distance`` are included (same convention as
    consecutive-long-run detection).
    """
    out: List[float] = []
    for run in _mv_weekly_runs_rows(session, user_id)[:max_weeks]:
        distance = float(run.get("distance", 0) or 0)
        if distance > 0:
            out.append(round(distance, 2))
    return out


def compute_stable_week1_long_run_start(
    weekly_longest_miles: List[float],
    *,
    long_run_increment: float = 1.0,
    min_long_run_mi: float = 5.0,
    max_increase_vs_median_pct: float = 0.10,
) -> Tuple[float, Dict[str, Any]]:
    """Derive Week 1 long run from weekly longest-run anchors.

    Rules:
    - If the last two weekly long runs are within ~1 mi of each other and of the most
      recent week, soft caps use **most recent** as the anchor (not the full-window median).
    - Baseline floor ``max(most_recent, full_window_median)`` unless a clear downward
      trend allows starting below most recent, or the most recent week is a lone spike
      above ``median × (1 + cap_pct)`` (then legacy outlier dampening still applies).
    - Otherwise preserves sustained-peak (+increment) vs single-peak behavior and the
      recent-window ceiling when older weeks are much higher than recent.

    Returns:
        ``(rounded_start_miles, metadata_dict)``
    """
    series = [
        float(x) for x in weekly_longest_miles if x is not None and float(x) > 0.0
    ][:6]
    if not series:
        raise ValueError(
            "weekly_longest_miles must contain at least one positive distance"
        )

    most_recent_long_run = float(series[0])
    n = len(series)
    recent_window = series[: min(3, n)]
    full_anchor = _median_of(series)
    recent_anchor = _median_of(recent_window)
    last_three = _last_three_weekly_long_runs(series)
    consistent_recent_lr = _consistent_recent_long_runs(
        most_recent_long_run, last_three
    )
    clear_downward_trend = _clear_downward_long_run_trend(series)
    week1_floor_baseline = max(most_recent_long_run, float(full_anchor))
    soft_median_cap = float(full_anchor) * (1.0 + max_increase_vs_median_pct)
    lone_high_spike = most_recent_long_run > soft_median_cap + 1e-6

    max_lr = max(series)
    ties_at_global_max = sum(1 for x in series if abs(x - max_lr) <= 1e-3)
    count_within_1mi_of_max = sum(1 for x in series if x >= max_lr - 1.0 - 1e-6)

    # Single-week hit at the global max → treat as outlier; sustained max weeks → allow max + inc.
    if ties_at_global_max <= 1:
        candidate = float(week1_floor_baseline)
        rule = "median_single_peak_week_anchor"
        anchor_for_soft_cap = (
            most_recent_long_run if consistent_recent_lr else float(full_anchor)
        )
        full_ceiling = anchor_for_soft_cap * (1.0 + max_increase_vs_median_pct)
        capped = min(candidate, full_ceiling)
    else:
        inc = min(float(long_run_increment), 1.0)
        candidate = max_lr + inc
        rule = "max_plus_increment_repeated_peak_anchor"
        anchor_for_soft_cap = float(full_anchor)
        full_ceiling = anchor_for_soft_cap * (1.0 + max_increase_vs_median_pct)
        capped = min(candidate, full_ceiling)

    recent_ceiling_base = (
        most_recent_long_run if consistent_recent_lr else float(recent_anchor)
    )
    recent_ceiling = recent_ceiling_base * (1.0 + max_increase_vs_median_pct)
    recent_max = max(recent_window)
    recent_supports_higher = (ties_at_global_max >= 2) or (
        abs(recent_max - max_lr) <= 1e-3
    )
    recent_weighting_applied = False
    if not recent_supports_higher:
        before_recent = capped
        capped = min(capped, recent_ceiling)
        recent_weighting_applied = capped + 1e-9 < before_recent

    if ties_at_global_max >= 2:
        explanation_reason_key = "sustained_peak"
    elif recent_supports_higher:
        explanation_reason_key = "recent_peak_supported"
    elif recent_weighting_applied:
        explanation_reason_key = "recent_median_cap"
    elif consistent_recent_lr:
        explanation_reason_key = "consistent_recent_baseline"
    else:
        explanation_reason_key = "consistency_anchor"

    if not clear_downward_trend:
        if lone_high_spike and not consistent_recent_lr:
            capped = max(float(min_long_run_mi), capped)
        elif ties_at_global_max >= 2:
            if not clear_downward_trend:
                capped = max(float(min_long_run_mi), capped, most_recent_long_run)
            else:
                capped = max(float(min_long_run_mi), capped)
        else:
            capped = max(
                float(min_long_run_mi),
                capped,
                week1_floor_baseline,
                most_recent_long_run,
            )
    else:
        capped = max(float(min_long_run_mi), capped)

    final = round_to_half_mile(capped)
    meta: Dict[str, Any] = {
        "median_long_run": float(full_anchor),
        "full_anchor_median": float(full_anchor),
        "recent_anchor_median": float(recent_anchor),
        "most_recent_long_run": most_recent_long_run,
        "max_long_run": max_lr,
        "ties_at_global_max": ties_at_global_max,
        "count_within_1mi_of_max": count_within_1mi_of_max,
        "consistent_recent_lr": consistent_recent_lr,
        "clear_downward_trend": clear_downward_trend,
        "week1_floor_baseline": float(week1_floor_baseline),
        "lone_high_spike": lone_high_spike,
        "anchor_for_soft_cap": float(anchor_for_soft_cap),
        "rule": rule,
        "raw_candidate": candidate,
        "cap_ceiling_vs_median_pct": max_increase_vs_median_pct,
        "cap_ceiling_miles": full_ceiling,
        "recent_ceiling_miles": recent_ceiling,
        "recent_supports_higher": recent_supports_higher,
        "recent_weighting_applied": recent_weighting_applied,
        "after_median_cap_miles": capped,
        "explanation_reason_key": explanation_reason_key,
    }
    return final, meta


def build_week1_long_run_explanation(
    *,
    weekly_series: List[float],
    start_lr_miles: float,
    start_meta: Dict[str, Any],
    start_rule: str,
) -> str:
    """Short coach-style copy for ``pass1_rationale`` (Week 1 long-run decision)."""
    sr = (start_rule or "").lower()
    if "recovery_week_after_consecutive" in sr:
        peak = start_meta.get("longest_recent")
        peak_txt = f"{float(peak):.1f}" if isinstance(peak, (int, float)) else str(peak)
        return (
            f"Week 1 long run {start_lr_miles:.1f} mi — recovery week after several long-run "
            f"weeks in a row (recent block peaked near {peak_txt} mi). Starting easier so "
            "volume can absorb before building again."
        )

    if not weekly_series:
        return (
            f"Week 1 long run {start_lr_miles:.1f} mi — anchored from your recent longest-run "
            "baseline (limited weekly history in view)."
        )

    lo = min(weekly_series)
    hi = max(weekly_series)
    nw = len(weekly_series)
    fa = float(
        start_meta.get("full_anchor_median") or start_meta.get("median_long_run") or 0.0
    )
    ra = float(start_meta.get("recent_anchor_median") or fa)
    rk = str(start_meta.get("explanation_reason_key") or "consistency_anchor")

    reason_clauses = {
        "sustained_peak": (
            "your last several weeks repeatedly hit similar long-run peaks, "
            "so a modest step from that level is appropriate"
        ),
        "recent_peak_supported": (
            "your most recent weeks include that peak long run, so the usual full-window "
            "consistency cap applies without pulling the start down to only the short window"
        ),
        "recent_median_cap": (
            "we weighted the last three weeks so week 1 stays close to what you have "
            "actually held lately, not older higher weeks alone"
        ),
        "consistent_recent_baseline": (
            "your last two long-run weeks match your current level, so week 1 starts from "
            "that recent baseline rather than an older median"
        ),
        "consistency_anchor": (
            "week 1 follows a stable blend of your recent weekly longest runs without "
            "chasing a single older outlier"
        ),
    }
    tail = reason_clauses.get(rk, reason_clauses["consistency_anchor"])

    return (
        f"Longest-run weeks in view span {lo:.0f}-{hi:.0f} mi ({nw} week(s)). "
        f"Recent 3-week median ~{ra:.1f} mi; full {nw}-week lookback median ~{fa:.1f} mi. "
        f"Week 1 long run: {start_lr_miles:.1f} mi — {tail}."
    )


def recent_longest_3w_from_materialized_view(
    session: Session, user_id: str, *, days: int = 21
) -> float:
    """
    Return the longest single run within the last `days` days using materialized view.
    Uses mv_longest_runs for fast, consistent data (same as metrics page).
    """
    try:
        athlete_id = get_athlete_id_for_user(session, user_id)
        if not athlete_id:
            return 0.0

        # Query materialized view
        result = session.execute(
            text("SELECT * FROM mv_longest_runs WHERE athlete_id = :athlete_id"),
            {"athlete_id": athlete_id},
        ).first()

        if not result or not result.weekly_runs:
            return 0.0

        # Get weekly runs from materialized view
        weekly_runs = result.weekly_runs

        # Filter to last 21 days (approximately 3 weeks)
        now = datetime.utcnow()
        cutoff = now - timedelta(days=days)
        longest = 0.0

        for run in weekly_runs:
            date_str = run.get("date")
            if not date_str:
                continue
            try:
                # Parse date (could be string or date object)
                if isinstance(date_str, str):
                    # Try ISO format first
                    try:
                        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    except ValueError:
                        # Try other common formats
                        dt = datetime.strptime(date_str, "%Y-%m-%d")
                elif hasattr(date_str, "date"):
                    # If it's already a date/datetime object
                    dt = (
                        datetime.combine(date_str, datetime.min.time())
                        if isinstance(date_str, date)
                        else date_str
                    )
                else:
                    continue

                if dt < cutoff:
                    continue

                distance = float(run.get("distance", 0) or 0)
                if distance > longest:
                    longest = distance
            except Exception:
                continue

        return round(longest, 2)
    except Exception:
        return 0.0


def detect_consecutive_long_runs_from_materialized_view(
    session: Session, user_id: str, *, min_consecutive_weeks: int = 3
) -> Dict[str, Any]:
    """
    Detect consecutive long runs using materialized view.
    Uses mv_longest_runs for fast, consistent data (same as metrics page).

    Returns same structure as detect_consecutive_long_runs() for compatibility.
    """
    try:
        weekly_runs = _mv_weekly_runs_rows(session, user_id)
        if not weekly_runs:
            return {
                "has_consecutive_runs": False,
                "consecutive_count": 0,
                "weekly_long_runs": [],
                "longest_recent": 0.0,
                "has_recent_reduction": False,
                "most_recent_long_run": 0.0,
            }

        # Extract distances for last 6 weeks (most recent first)
        weekly_long_runs: List[float] = []
        for run in weekly_runs[:6]:
            distance = float(run.get("distance", 0) or 0)
            if distance > 0:
                weekly_long_runs.append(round(distance, 2))

        if len(weekly_long_runs) < min_consecutive_weeks:
            most_recent = weekly_long_runs[0] if weekly_long_runs else 0.0
            return {
                "has_consecutive_runs": False,
                "consecutive_count": len(weekly_long_runs),
                "weekly_long_runs": weekly_long_runs,
                "longest_recent": max(weekly_long_runs) if weekly_long_runs else 0.0,
                "has_recent_reduction": False,
                "most_recent_long_run": most_recent,
            }

        # Check for consecutive weeks with long runs >= 8.0 miles
        consecutive_count = 0
        for lr in weekly_long_runs:
            if lr >= 8.0:
                consecutive_count += 1
            else:
                break

        has_consecutive = consecutive_count >= min_consecutive_weeks
        longest_recent = (
            max(weekly_long_runs[:consecutive_count]) if consecutive_count > 0 else 0.0
        )

        # Detect if user has already self-regulated (recent reduction from peak)
        most_recent_long_run = weekly_long_runs[0] if weekly_long_runs else 0.0
        has_recent_reduction = False

        if (
            len(weekly_long_runs) >= 2
            and most_recent_long_run > 0
            and longest_recent > 0
        ):
            # Check if most recent week is lower than peak
            reduction_threshold = 0.05  # 5% reduction suggests intentional adjustment
            reduction_pct = (longest_recent - most_recent_long_run) / longest_recent

            if reduction_pct >= reduction_threshold:
                # Check if it's part of a downward trend (most recent < previous)
                if (
                    len(weekly_long_runs) >= 2
                    and most_recent_long_run < weekly_long_runs[1]
                ):
                    has_recent_reduction = True
                # Or if reduction is substantial (15%+), definitely intentional
                elif reduction_pct >= 0.15:
                    has_recent_reduction = True

        return {
            "has_consecutive_runs": has_consecutive,
            "consecutive_count": consecutive_count,
            "weekly_long_runs": weekly_long_runs,
            "longest_recent": longest_recent,
            "has_recent_reduction": has_recent_reduction,
            "most_recent_long_run": most_recent_long_run,
        }
    except Exception:
        return {
            "has_consecutive_runs": False,
            "consecutive_count": 0,
            "weekly_long_runs": [],
            "longest_recent": 0.0,
            "has_recent_reduction": False,
            "most_recent_long_run": 0.0,
        }
