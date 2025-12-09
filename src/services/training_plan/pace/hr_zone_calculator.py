"""
HR Zone to Pace Calculator

For paid Strava users: Calculate paces directly from HR zone data.
Simple, direct correlation - no complex derivation.
"""

from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime, timedelta
import statistics

from src.db.models.activities import Activity
from .models import PaceSeed


def calculate_paces_from_hr_zones(
    session: Session,
    user_id: str,
    lookback_days: int = 90,
) -> Optional[PaceSeed]:
    """
    Calculate pace zones from HR zone data.

    Simple approach:
    1. Find activities where user spent >30% time in each HR zone
    2. Get pace from those activities
    3. Use median pace per zone

    Returns None if insufficient data.
    """
    cutoff = datetime.now() - timedelta(days=lookback_days)

    # Get activities with HR zone data
    activities = (
        session.query(Activity)
        .filter(
            Activity.user_id == user_id,
            Activity.type == "Run",
            Activity.start_date >= cutoff,
            Activity.average_speed.isnot(None),
            Activity.average_speed > 0,
            or_(
                Activity.hr_zone_1 > 30,
                Activity.hr_zone_2 > 30,
                Activity.hr_zone_3 > 30,
                Activity.hr_zone_4 > 30,
                Activity.hr_zone_5 > 30,
            ),
        )
        .all()
    )

    # Collect paces for each zone
    zone_paces = _collect_zone_paces(activities)

    # Calculate median pace for each zone
    paces = _calculate_median_paces(zone_paces)

    # Need at least Easy and Marathon to be valid
    if not paces.get("E") or not paces.get("M"):
        return None

    # Calculate week1_long_cap
    week1_long_cap = _calculate_week1_long_cap(session, user_id, cutoff)

    return PaceSeed(
        E_min=paces["E"] - 15,
        E_max=paces["E"] + 45,
        S_min=paces.get("S", paces["E"]) - 15,
        S_max=paces.get("S", paces["E"]) + 15,
        M=paces["M"],
        T_min=paces.get("T", paces["M"] - 25) - 5,
        T_max=paces.get("T", paces["M"] - 25) + 5,
        week1_long_cap=week1_long_cap,
    )


def _collect_zone_paces(activities: List[Activity]) -> Dict[int, List[float]]:
    """
    Collect paces for each HR zone.

    Uses dominant zone approach: Each activity contributes to only one zone
    (the zone where the user spent the most time). This prevents mixed-intensity
    runs from contaminating multiple zones.
    """
    zone_paces = {1: [], 2: [], 3: [], 4: [], 5: []}

    for activity in activities:
        # Convert speed (m/s) to pace (seconds per mile)
        # 1 mile = 1609.34 meters
        # Time = distance / speed = 1609.34 / average_speed (seconds)
        pace_sec_per_mile = 1609.34 / activity.average_speed

        # Find dominant zone (zone with highest percentage)
        zone_percentages = {
            1: activity.hr_zone_1 or 0,
            2: activity.hr_zone_2 or 0,
            3: activity.hr_zone_3 or 0,
            4: activity.hr_zone_4 or 0,
            5: activity.hr_zone_5 or 0,
        }

        # Only use activity if at least one zone has >30% time
        max_zone_pct = max(zone_percentages.values())
        if max_zone_pct < 30:
            continue  # Skip activities without significant zone time

        # Find the dominant zone (highest percentage)
        dominant_zone = max(zone_percentages.items(), key=lambda x: x[1])[0]

        # Assign pace to dominant zone only
        zone_paces[dominant_zone].append(pace_sec_per_mile)

    return zone_paces


def _calculate_median_paces(zone_paces: Dict[int, List[float]]) -> Dict[str, float]:
    """
    Calculate median pace for each zone (need at least 3 samples).

    HR Zone Mapping (Strava standard):
    - Zone 1 (50-60% max HR): Recovery/Easy
    - Zone 2 (60-75% max HR): Aerobic/Moderate/Steady
    - Zone 3 (75-85% max HR): Tempo/Marathon
    - Zone 4 (85-95% max HR): Threshold
    - Zone 5 (95-100% max HR): VO2 Max/Interval

    Training Pace Mapping (based on standard running training zones):
    - Easy: Zone 1 (Recovery) - slowest, conversational pace
    - Steady: Zone 2 (Aerobic) - moderate aerobic pace
    - Marathon: Zone 3 (Tempo) - marathon race pace (75-85% max HR)
    - Threshold: Zone 4 (Threshold) - lactate threshold pace (85-95% max HR)
    """
    MIN_SAMPLES = 3
    paces = {}

    # Easy: Zone 1 (Recovery) - slowest pace
    if len(zone_paces[1]) >= MIN_SAMPLES:
        paces["E"] = statistics.median(zone_paces[1])
    elif len(zone_paces[2]) >= MIN_SAMPLES:
        # Fallback: use Zone 2 but add 10s to make it slower than Marathon
        paces["E"] = statistics.median(zone_paces[2]) + 10

    # Steady: Zone 2 (Aerobic) - moderate aerobic pace
    if len(zone_paces[2]) >= MIN_SAMPLES:
        paces["S"] = statistics.median(zone_paces[2])

    # Marathon: Zone 3 (Tempo) - marathon race pace (75-85% max HR)
    # This is the key fix: Marathon pace is in the Tempo zone, not Aerobic zone
    if len(zone_paces[3]) >= MIN_SAMPLES:
        paces["M"] = statistics.median(zone_paces[3])
    elif len(zone_paces[2]) >= MIN_SAMPLES:
        # Fallback: if no Zone 3 data, use Zone 2 but subtract 10s (Zone 3 is faster)
        paces["M"] = statistics.median(zone_paces[2]) - 10

    # Threshold: Zone 4 (Threshold) - lactate threshold pace (85-95% max HR)
    if len(zone_paces[4]) >= MIN_SAMPLES:
        paces["T"] = statistics.median(zone_paces[4])

    # Ensure proper ordering: Threshold (fastest) < Marathon < Steady < Easy (slowest)
    # Safety check to prevent inverted paces
    if "E" in paces and "M" in paces and paces["M"] >= paces["E"]:
        # Marathon should be faster than Easy - adjust if needed
        paces["M"] = paces["E"] - 15  # Make Marathon 15s faster than Easy

    if "M" in paces and "T" in paces and paces["T"] >= paces["M"]:
        # Threshold should be faster than Marathon - adjust if needed
        paces["T"] = paces["M"] - 10  # Make Threshold 10s faster than Marathon

    return paces


def _calculate_week1_long_cap(
    session: Session,
    user_id: str,
    cutoff: datetime,
) -> float:
    """Calculate max long run for week 1 from recent longest run."""
    longest_run = (
        session.query(Activity)
        .filter(
            Activity.user_id == user_id,
            Activity.type == "Run",
            Activity.start_date >= cutoff,
            Activity.conv_distance >= 10.0,
        )
        .order_by(Activity.conv_distance.desc())
        .first()
    )

    if longest_run:
        return max(8.0, longest_run.conv_distance + 2.0)
    return 8.0
