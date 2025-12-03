from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import date, datetime, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.training_plan.calculations.week_utils import get_complete_weeks
from src.services.training_plan.v2.race_configs.base_config import RaceDistanceConfig
from src.services.training_plan.v2.shared_v2.rounding_utils import round_to_half_mile


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
        athlete_id = get_athlete_id_for_user(session, user_id)
        if not athlete_id:
            return {
                "has_consecutive_runs": False,
                "consecutive_count": 0,
                "weekly_long_runs": [],
                "longest_recent": 0.0,
                "has_recent_reduction": False,
                "most_recent_long_run": 0.0,
            }

        # Query materialized view
        result = session.execute(
            text("SELECT * FROM mv_longest_runs WHERE athlete_id = :athlete_id"),
            {"athlete_id": athlete_id},
        ).first()

        if not result or not result.weekly_runs:
            return {
                "has_consecutive_runs": False,
                "consecutive_count": 0,
                "weekly_long_runs": [],
                "longest_recent": 0.0,
                "has_recent_reduction": False,
                "most_recent_long_run": 0.0,
            }

        # Get weekly runs (already grouped by week, longest run per week)
        weekly_runs = result.weekly_runs

        # Extract distances for last 4 weeks (most recent first)
        weekly_long_runs: List[float] = []
        for run in weekly_runs[:4]:  # Only need last 4 weeks
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
