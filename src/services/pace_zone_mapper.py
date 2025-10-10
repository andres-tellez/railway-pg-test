"""
Stage 4: VDOT + Strava Zone Mapper
----------------------------------
Purpose:
Map each workout (Threshold, Easy, Long) to pace and HR zone targets
using Daniels VDOT tables + user heart-rate data.
"""

from typing import Dict, Any, List

# Simple lookup table for common VDOT ranges → paces (min/mile)
VDOT_TO_PACE = {
    # Example: VDOT : { type : pace_range_in_min_per_mile }
    35: {"Easy": (10.30, 11.00), "Threshold": (9.00, 9.15), "Long": (10.00, 10.30), "Marathon": (9.45, 10.00)},
    40: {"Easy": (9.45, 10.15), "Threshold": (8.15, 8.30), "Long": (9.15, 9.45), "Marathon": (8.45, 9.15)},
    45: {"Easy": (9.00, 9.25), "Threshold": (7.45, 7.55), "Long": (8.45, 9.10), "Marathon": (8.15, 8.45)},
    50: {"Easy": (8.30, 8.55), "Threshold": (7.15, 7.30), "Long": (8.15, 8.35), "Marathon": (7.45, 8.15)},
    55: {"Easy": (7.55, 8.20), "Threshold": (6.45, 6.55), "Long": (7.45, 8.05), "Marathon": (7.15, 7.45)},
    60: {"Easy": (7.30, 7.50), "Threshold": (6.15, 6.25), "Long": (7.15, 7.35), "Marathon": (6.45, 7.15)},
    65: {"Easy": (7.05, 7.25), "Threshold": (5.50, 6.00), "Long": (6.50, 7.10), "Marathon": (6.20, 6.50)},
    70: {"Easy": (6.40, 7.00), "Threshold": (5.30, 5.40), "Long": (6.25, 6.45), "Marathon": (5.55, 6.25)},
}

def map_pace_zones(
    weekly_plan: List[Dict[str, Any]],
    user_profile: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Adds pace & HR zone targets to each workout.
    """
    print("\n" + "=" * 60)
    print("STAGE 4: PACE & ZONE MAPPING")
    print("=" * 60)

    # Extract user fitness data
    vdot = int(user_profile.get("vdot", 45))  # default mid-level
    max_hr = user_profile.get("max_hr", 177)
    age = user_profile.get("age", 35)

    # Use calculated max HR if not available
    if not max_hr or max_hr == 0:
        max_hr = 220 - age  # rough estimate

    print(f"\nUser Fitness Profile:")
    print(f"  • VDOT: {vdot}")
    print(f"  • Max HR: {max_hr} bpm")
    print(f"  • Age: {age}")

    # Standard Strava HR zones
    hr_zones = {
        "Z1": (0.50, 0.60),   # Recovery
        "Z2": (0.60, 0.75),   # Easy/Aerobic
        "Z3": (0.75, 0.85),   # Threshold
        "Z4": (0.85, 0.95),   # VO2 Max
        "Z5": (0.95, 1.00),   # Neuromuscular
    }

    # Get pace ranges for user's VDOT
    pace_dict = VDOT_TO_PACE.get(vdot, VDOT_TO_PACE[45])

    print(f"\nPace Targets (VDOT {vdot}):")
    print(f"  • Easy: {pace_dict['Easy'][0]:.2f}–{pace_dict['Easy'][1]:.2f} min/mi")
    print(f"  • Threshold: {pace_dict['Threshold'][0]:.2f}–{pace_dict['Threshold'][1]:.2f} min/mi")
    print(f"  • Long: {pace_dict['Long'][0]:.2f}–{pace_dict['Long'][1]:.2f} min/mi")

    enriched_plan = []

    for week in weekly_plan:
        print(f"\nWeek {week.get('week_number', week.get('week', 'Unknown'))}: {week.get('total_miles', 0)} mi")

        enriched_sessions = []

        # Process each day in the week
        days = week.get('days', [])
        print(f"  Processing {len(days)} workouts for this week")
        for day in days:
            print(f"    • {day.get('workout_type', 'Unknown')}: {day.get('distance_mi', 0)} mi")
            workout_type = day.get('workout_type', 'Easy')
            distance_mi = day.get('distance_mi', 0)

            if distance_mi <= 0:
                continue

            # Map workout type to pace and HR zones
            if workout_type in ["Threshold", "Tempo"]:
                pace_lo, pace_hi = pace_dict["Threshold"]
                hr_lo, hr_hi = hr_zones["Z3"]
                zone_desc = "Z3"
                description = "Threshold/tempo pace - comfortably hard effort"

            elif workout_type == "Marathon":
                pace_lo, pace_hi = pace_dict["Marathon"]
                hr_lo, hr_hi = hr_zones["Z3"]
                zone_desc = "Z3"
                description = "Marathon race pace - sustainable for 26.2 miles"

            elif workout_type in ["VO2", "Intervals", "Repetitions"]:
                pace_lo, pace_hi = pace_dict["Threshold"]  # Use threshold as base, will be adjusted
                hr_lo, hr_hi = hr_zones["Z4"]
                zone_desc = "Z4"
                description = "VO2 max intervals - hard but controlled effort"

            elif workout_type == "Long":
                pace_lo, pace_hi = pace_dict["Long"]
                hr_lo, hr_hi = hr_zones["Z2"]
                zone_desc = "Z2"
                description = "Long aerobic run - steady conversational pace"

            elif workout_type == "Race":
                pace_lo, pace_hi = pace_dict["Marathon"]
                hr_lo, hr_hi = hr_zones["Z4"]
                zone_desc = "Race"
                description = "Race day - trust your training and pacing"

            else:  # Easy, Recovery
                pace_lo, pace_hi = pace_dict["Easy"]
                hr_lo, hr_hi = hr_zones["Z2"]
                zone_desc = "Z2"
                description = "Easy aerobic run - comfortable conversational pace"

            # Calculate HR ranges
            hr_min = int(hr_lo * max_hr)
            hr_max = int(hr_hi * max_hr)

            # Format pace as MM:SS
            pace_min_lo = int(pace_lo)
            pace_sec_lo = int((pace_lo - pace_min_lo) * 60)
            pace_min_hi = int(pace_hi)
            pace_sec_hi = int((pace_hi - pace_min_hi) * 60)

            pace_range = f"{pace_min_lo}:{pace_sec_lo:02d}–{pace_min_hi}:{pace_sec_hi:02d}/mi"
            hr_range = f"{zone_desc} ({hr_min}–{hr_max} bpm)"

            enriched_session = {
                "date": day.get('date'),
                "workout_type": workout_type,
                "distance_mi": distance_mi,
                "target_pace": pace_range,
                "target_hr": hr_range,
                "description": description,
                "notes": day.get('notes', '')
            }

            enriched_sessions.append(enriched_session)
            print(f"  • {workout_type}: {distance_mi} mi @ {pace_range} ({hr_range})")

        enriched_plan.append({
            "week_number": week.get('week_number', week.get('week', 'Unknown')),
            "week_start": week.get('week_start'),
            "phase": week.get('phase'),
            "total_miles": week.get('total_miles'),
            "workouts": enriched_sessions
        })

    print(f"\nPace & zone mapping complete for {len(enriched_plan)} weeks")
    print("=" * 60 + "\n")

    return enriched_plan


def estimate_vdot_from_race_time(race_distance: str, race_time: str) -> int:
    """
    Estimate VDOT from recent race performance.
    This is a simplified version - in production you'd use full Daniels tables.
    """
    try:
        # Parse race time (format: "3:45:00" or "1:42:30")
        time_parts = race_time.split(':')
        if len(time_parts) == 3:
            hours, minutes, seconds = map(int, time_parts)
            total_minutes = hours * 60 + minutes + seconds / 60
        elif len(time_parts) == 2:
            minutes, seconds = map(int, time_parts)
            total_minutes = minutes + seconds / 60
        else:
            return 45  # default

        # Rough VDOT estimation based on race distance
        if race_distance.lower() in ['marathon', '26.2']:
            # Marathon VDOT estimation (simplified)
            if total_minutes < 150:  # sub-2:30
                return 70
            elif total_minutes < 180:  # sub-3:00
                return 60
            elif total_minutes < 210:  # sub-3:30
                return 50
            elif total_minutes < 240:  # sub-4:00
                return 45
            else:
                return 40
        elif race_distance.lower() in ['half', '13.1', 'half marathon']:
            # Half marathon VDOT estimation
            if total_minutes < 75:  # sub-1:15
                return 70
            elif total_minutes < 90:  # sub-1:30
                return 60
            elif total_minutes < 105:  # sub-1:45
                return 50
            elif total_minutes < 120:  # sub-2:00
                return 45
            else:
                return 40
        else:
            # Default for other distances
            return 45

    except:
        return 45  # default fallback
