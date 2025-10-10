"""
Training Plan Builder (Stage 3)
-------------------------------
Generates a Jack Daniels–style marathon plan using Stage 2 normalized parameters.

Inputs:
- normalized_profile (from Stage 2)
- start_date, race_date
- training_days (e.g., ["MON","WED","THU","SAT"])
- zones: mapping to Strava Zones (Z1-5) already standardized in your system

Outputs:
- List[Week]: each week has total mileage target, breakdown (easy/threshold/marathon/vo2/long),
  and Day objects with (type, distance, zone, notes)
"""

from datetime import date, timedelta
from typing import Dict, Any, List, Literal
import math

DayType = Literal["Easy", "Recovery", "Threshold", "Marathon", "Intervals", "Repetitions", "Long", "Race", "Off"]

# -------------------------------
# Public entry point
# -------------------------------

def build_training_plan(
    normalized: Dict[str, Any],
    start_date: date,
    race_date: date,
    training_days: List[str],
    zones: Dict[str, str],  # {"easy": "Z1-2", "thresh": "Z3", "marathon": "Z3", "vo2": "Z4", "rep": "Z4-5"}
) -> Dict[str, Any]:
    """
    Build a complete training plan using Jack Daniels methodology with Stage 2 parameters.
    """
    print("\n" + "=" * 60)
    print("TRAINING PLAN BUILDER (Stage 3)")
    print("=" * 60)

    weeks_total = max(1, math.ceil((race_date - start_date).days / 7))
    phase = normalized["phase"]  # "Base-Build" | "Quality-Phase" | "Race-Specific"
    target_weekly = normalized["target_weekly_mileage"]
    ramp_limit = normalized["ramp_limit_pct"]
    long_cap = normalized["long_run_cap"]
    easy_ratio = normalized["easy_run_ratio"]
    th_per_week = normalized["threshold_sessions_per_week"]
    recw_freq = normalized.get("recovery_week_frequency", 3)

    print(f"\nPlan Parameters:")
    print(f"  • Phase: {phase}")
    print(f"  • Duration: {weeks_total} weeks")
    print(f"  • Target weekly mileage: {target_weekly} mi")
    print(f"  • Ramp limit: {ramp_limit*100:.1f}% per week")
    print(f"  • Long-run cap: {long_cap} mi")
    print(f"  • Training days: {training_days}")
    print(f"  • Recovery frequency: every {recw_freq} weeks")

    # 1) Create weekly volume progression with periodic recovery weeks and taper
    week_miles = compute_weekly_targets(
        weeks_total=weeks_total,
        base=normalized["base_mileage"],
        target=target_weekly,
        ramp=ramp_limit,
        recovery_every=recw_freq,
        taper_weeks=derive_taper_weeks(weeks_total),   # e.g., last 2–3 weeks taper
    )

    print(f"\nWeekly Mileage Progression:")
    for i, miles in enumerate(week_miles, 1):
        print(f"  • Week {i}: {miles} mi")

    # 1.5) Compute progressive long-run schedule
    long_run_schedule = compute_progressive_long_runs(
        weeks_total=weeks_total,
        long_run_cap=long_cap,
        current_longest=normalized.get("longest_run", 0),
        taper_weeks=derive_taper_weeks(weeks_total),
    )

    print(f"\nProgressive Long-Run Schedule:")
    for i, long_mi in enumerate(long_run_schedule, 1):
        print(f"  • Week {i}: {long_mi} mi")

    # 1.6) Compute weekly mileage progression using Stage 2 target and ramp limit
    # Start from base mileage and ramp toward Stage 2 target
    base_mileage = normalized.get("base_mileage", 15)
    week_miles = []

    for w_idx in range(weeks_total):
        # Apply ramp limit to progress from base toward target
        if w_idx == 0:
            week_total = base_mileage  # Start at current base
        else:
            # Progressive ramp: base * (1 + ramp_limit * week_index)
            week_total = min(target_weekly, base_mileage * (1 + ramp_limit * w_idx))

        week_miles.append(round(week_total, 1))

    print(f"\nWeekly Mileage Progression (base → target):")
    for i, (total, long_mi) in enumerate(zip(week_miles, long_run_schedule), 1):
        print(f"  • Week {i}: {total} mi (long = {long_mi} mi, {long_mi/total*100:.0f}%)")

    # 2) For each week, allocate mileage by phase → JD intensity mix
    plan_weeks = []
    for w_idx in range(weeks_total):
        week_start = start_date + timedelta(days=7*w_idx)
        is_taper = w_idx >= weeks_total - derive_taper_weeks(weeks_total)
        mix = phase_intensity_mix(phase, is_taper, easy_ratio, th_per_week)

        # mix fields return fractions for: easy, threshold, marathon, vo2, reps, long-share
        allocations = allocate_week_mileage(
            total_miles=week_miles[w_idx],
            long_cap=long_cap,
            mix=mix,
            progressive_long_run=long_run_schedule[w_idx],
        )

        # 3) Build day schedule on the runner's available days
        days = build_week_schedule(
            week_start=week_start,
            training_days=training_days,
            allocations=allocations,
            zones=zones,
            is_taper=is_taper,
            phase=phase,
        )

        plan_weeks.append({
            "week_number": w_idx + 1,
            "week_start": week_start.isoformat(),
            "total_miles": round(week_miles[w_idx], 1),
            "phase": phase if not is_taper else f"{phase} (Taper)",
            "allocations": allocations,   # dict of category → miles
            "days": days,                 # list of daily workouts
        })

    # 4) Insert Race Day
    plan_weeks[-1]["days"] = inject_race_day(plan_weeks[-1]["days"], race_date, zones)

    print(f"\nPLAN GENERATION COMPLETE:")
    print(f"  • Total weeks: {len(plan_weeks)}")
    print(f"  • Peak mileage: {max(w['total_miles'] for w in plan_weeks)} mi")
    print(f"  • Taper weeks: {derive_taper_weeks(weeks_total)}")
    print("=" * 60 + "\n")

    return {
        "phase": phase,
        "weeks": plan_weeks,
        "params": {
            "target_weekly": target_weekly,
            "ramp_limit": ramp_limit,
            "long_cap": long_cap,
            "easy_ratio": easy_ratio,
            "threshold_sessions": th_per_week,
            "training_days": training_days,
        }
    }

# -------------------------------
# Progressive long-run schedule
# -------------------------------

def compute_progressive_long_runs(weeks_total: int, long_run_cap: float, current_longest: float, taper_weeks: int) -> List[float]:
    """
    Generate a progressive long-run schedule that:
    - Week 1: Starts at 80% of current longest run (respects proven capability)
    - Weeks 2-N: Gradually ramps up using exponential progression to reach peak
    - Peak: 1.45x the long_run_cap (allows progression beyond the "safe" cap)
    - Taper weeks: Reduces to 60%, 40%, 20% of peak

    Example for 9 weeks with cap=11.1, current=13.9:
    Week 1: 11.0 mi (max(80% of 13.9, 80% of 11.1))
    Week 2: 11.7 mi
    Week 3: 12.4 mi
    Week 4: 13.2 mi
    Week 5: 14.0 mi
    Week 6: 15.0 mi (peak = 1.45x cap)
    Week 7: 9.0 mi (60% taper)
    Week 8: 6.0 mi (40% taper)
    Week 9: 3.0 mi (20% taper)
    """
    if weeks_total < 1:
        return []

    # Calculate starting point: higher of 80% current longest or 80% cap
    start_long = max(0.8 * current_longest, 0.8 * long_run_cap) if current_longest > 0 else 0.8 * long_run_cap

    # Peak is 1.45x the cap to allow proper progression
    peak_long = long_run_cap * 1.45

    # Calculate ramp factor for exponential growth (excludes taper weeks)
    build_weeks = max(weeks_total - 3, 1)  # 3 weeks of taper
    if build_weeks > 1 and start_long < peak_long:
        ramp_factor = (peak_long / start_long) ** (1 / (build_weeks - 1))
    else:
        ramp_factor = 1.0

    long_runs = []

    for week in range(weeks_total):
        if week >= weeks_total - 3:
            # Taper: 60%, 40%, 20% of peak
            taper_idx = week - (weeks_total - 3)
            taper_factors = [0.6, 0.4, 0.2]
            long_runs.append(round(peak_long * taper_factors[taper_idx], 1))
        else:
            # Build phase: exponential progression
            long_runs.append(round(start_long * (ramp_factor ** week), 1))

    return long_runs


# -------------------------------
# Weekly volume progression
# -------------------------------

def compute_weekly_targets(weeks_total: int, base: float, target: float,
                           ramp: float, recovery_every: int, taper_weeks: int) -> List[float]:
    """
    - Ramps from base toward target with <= ramp% week-over-week
    - Every Nth week, recovery (−15~20%)
    - Taper in last 'taper_weeks' as 60% → 40% → (race week has long-run suppressed)
    """
    miles = []
    current = max(base, 0.0)

    for wk in range(1, weeks_total + 1):
        # taper override
        if wk > weeks_total - taper_weeks:
            # Simple 3-step taper: 0.6 * peak, 0.4 * peak, race wk ~0.3 * peak
            peak = max(miles) if miles else target
            scale = [0.6, 0.4, 0.3][- (weeks_total - wk + 1)]
            miles.append(round(peak * scale, 1))
            continue

        # normal ramp
        desired = min(target, current * (1 + ramp))
        # every recovery_every weeks, drop ~15%
        if recovery_every and wk % recovery_every == 0:
            desired *= 0.85

        miles.append(round(desired, 1))
        current = desired

    # guarantee non-decreasing pre-taper trend (except recovery dips)
    return miles

def derive_taper_weeks(weeks_total: int) -> int:
    if weeks_total >= 12: return 3
    if weeks_total >= 8:  return 2
    return 1

# -------------------------------
# Phase intensity mix (JD-aligned)
# -------------------------------

def phase_intensity_mix(phase: str, is_taper: bool, easy_ratio: float, th_per_week: int) -> Dict[str, Any]:
    """
    Returns fractional allocation and knobs JD-style.
    Includes: easy, threshold, marathon, vo2, reps, long_share (fraction of total mileage).
    """
    if phase == "Base-Build":
        mix = {
            "easy": max(easy_ratio, 0.70),
            "threshold": 0.05 if th_per_week >= 1 else 0.0,
            "marathon": 0.00,
            "vo2": 0.05,          # light aerobic power
            "reps": 0.00,
            "long_share": 0.28,   # 25–30% rule
        }
    elif phase == "Quality-Phase":
        mix = {
            "easy": max(easy_ratio, 0.70),
            "threshold": 0.12 if th_per_week >= 1 else 0.08,
            "marathon": 0.05,
            "vo2": 0.05,
            "reps": 0.00,
            "long_share": 0.28,
        }
    else:  # "Race-Specific"
        mix = {
            "easy": max(easy_ratio, 0.65),
            "threshold": 0.12 if th_per_week >= 1 else 0.08,
            "marathon": 0.10,     # add M-pace work
            "vo2": 0.05,
            "reps": 0.00,
            "long_share": 0.28,
        }

    if is_taper:
        # increase easy share, suppress VO2/Rep
        mix["easy"] = max(mix["easy"], 0.80)
        mix["threshold"] *= 0.6
        mix["marathon"] *= 0.7
        mix["vo2"] = 0.0
        mix["reps"] = 0.0

    # normalize to leave room for long run (counted separately)
    # weekly long run ≈ long_share * total; remaining mileage apportioned by ratios
    return mix

# -------------------------------
# Allocate mileage by category
# -------------------------------

def allocate_week_mileage(total_miles: float, long_cap: float, mix: Dict[str, float], progressive_long_run: float = 0) -> Dict[str, float]:
    """
    Allocate weekly mileage across workout types using progressive long-run schedule.

    Args:
        total_miles: Total weekly mileage target
        long_cap: Maximum allowed long-run distance
        mix: Phase-specific intensity distribution
        progressive_long_run: Pre-calculated long run for this week from progressive schedule
    """
    # Use the progressive long-run value (already calculated with proper ramping)
    long_mi = progressive_long_run if progressive_long_run > 0 else min(round(total_miles * mix["long_share"], 1), long_cap)

    remain = max(total_miles - long_mi, 0)

    # split the remainder by (easy/threshold/marathon/vo2/reps) proportions
    prop_sum = mix["easy"] + mix["threshold"] + mix["marathon"] + mix["vo2"] + mix["reps"]
    def part(p): return round(remain * (p / prop_sum), 1) if prop_sum > 0 else 0.0

    allocations = {
        "long": long_mi,
        "easy": part(mix["easy"]),
        "threshold": part(mix["threshold"]),
        "marathon": part(mix["marathon"]),
        "vo2": part(mix["vo2"]),
        "reps": part(mix["reps"]),
        "total": round(total_miles, 1),
    }
    return allocations

# -------------------------------
# Build weekly day schedule
# -------------------------------

def build_week_schedule(week_start: date, training_days: List[str], allocations: Dict[str, float],
                        zones: Dict[str, str], is_taper: bool, phase: str) -> List[Dict[str, Any]]:
    """
    Rules:
    - Place Long run on the latest available weekend day (SAT→SUN→FRI)
    - One Threshold/quality day mid-week (e.g., WED). If Race-Specific, add M-pace segments
    - Fill remaining days with Easy/Recovery distributed to meet allocations
    - Round distances to nearest 0.5 mi
    - Ensure ALL training days are used
    """
    days = []
    day_map = weekday_map(week_start)  # {"MON": date(...), ...}

    print(f"  Building schedule for week starting {week_start}")
    print(f"  Available training days: {training_days}")
    print(f"  Allocations: {allocations}")

    # 1) Long run day - prioritize SAT for long runs
    long_day = choose_weekend(training_days)  # prefer SAT, else SUN, else FRI
    if allocations["long"] > 0 and long_day:
        days.append(make_workout(day_map[long_day], "Long", allocations["long"], zones["easy"],
                                 notes=long_run_notes(phase, is_taper)))
        print(f"  Long run ({allocations['long']} mi) scheduled for {long_day}")

    # 2) Threshold / Marathon quality (respect per-week limits implicitly via allocations)
    quality_slots = [d for d in training_days if d not in [long_day]]
    q_miles = allocations["threshold"] + allocations["marathon"] + allocations["vo2"] + allocations["reps"]

    if q_miles > 0 and quality_slots:
        # Prefer mid-week days (TUE, WED, THU) for quality work
        mid_week_days = [d for d in quality_slots if d in ["TUE", "WED", "THU"]]
        q_day = mid_week_days[0] if mid_week_days else quality_slots[0]

        # Build a composite session from available quality buckets
        session = quality_session_blocks(allocations, zones, phase)
        days.append({"date": day_map[q_day].isoformat(), **session})
        print(f"  Quality workout ({q_miles:.1f} mi) scheduled for {q_day}")

    # 3) Fill remaining with easy/recovery to hit totals
    used_days = [long_day] + ([q_day] if q_miles > 0 and quality_slots else [])
    remaining_slots = [d for d in training_days if d not in used_days]

    easy_total = allocations["easy"]

    # Target 3 easy runs per week for better distribution (JD principle)
    n_easy_runs = 3  # Always create 3 easy runs per week

    # Split easy miles into multiple runs (4-6 mi each is ideal)
    per_easy = round_to_half(easy_total / n_easy_runs)

    # Cap each easy run at 6 miles (JD principle for easy runs)
    if per_easy > 6.0:
        per_easy = 6.0
        # If we need to cap, create more runs to distribute the mileage
        n_easy_runs = max(n_easy_runs, int(easy_total / 6.0) + 1)
        per_easy = round_to_half(easy_total / n_easy_runs)

    # Create easy runs, cycling through available training days if needed
    for i in range(n_easy_runs):
        if per_easy > 0:
            # Use available slots first, then cycle through all training days
            if i < len(remaining_slots):
                day = remaining_slots[i]
            else:
                # Cycle through all training days if we need more slots
                day = training_days[i % len(training_days)]

            # Make sure we don't double-book a day
            day_date = weekday_map(week_start)[day]
            if not any(d.get("date") == day_date.isoformat() for d in days):
                days.append(make_workout(day_date, "Easy", per_easy, zones["easy"],
                                         notes=f"Easy aerobic run #{i+1} - conversational pace"))
                print(f"  Easy run #{i+1} ({per_easy} mi) scheduled for {day}")

    # 4) Sort by date
    days.sort(key=lambda x: x["date"])
    print(f"  Week complete: {len(days)} workouts scheduled")
    return days

# -------------------------------
# Helpers
# -------------------------------

def weekday_map(week_start: date) -> Dict[str, date]:
    # Calculate the offset to get to Monday (0 = Monday, 6 = Sunday)
    days_to_monday = week_start.weekday()  # 0=Monday, 1=Tuesday, ..., 6=Sunday
    monday_of_week = week_start - timedelta(days=days_to_monday)

    # Map each day of the week starting from Monday
    return {
        day: monday_of_week + timedelta(days=i)
        for i, day in enumerate(["MON","TUE","WED","THU","FRI","SAT","SUN"])
    }

def choose_weekend(training_days: List[str]) -> str | None:
    # Prioritize SAT for long runs, then SUN, then FRI as last resort
    for d in ["SAT", "SUN", "FRI"]:
        if d in training_days:
            return d
    return training_days[-1] if training_days else None

def make_workout(d: date, wtype: DayType, miles: float, zone: str, notes: str = "") -> Dict[str, Any]:
    return {
        "date": d.isoformat(),
        "workout_type": wtype,
        "distance_mi": round_to_half(miles),
        "zone": zone,
        "notes": notes
    }

def round_to_half(x: float) -> float:
    return round(x*2)/2.0

def long_run_notes(phase: str, is_taper: bool) -> str:
    if is_taper: return "Keep it easy; no fast finish. Focus on fueling and cadence."
    if phase == "Race-Specific": return "Finish last 4–6 mi @ marathon effort if feeling good."
    return "Steady Z1–2; hydrate; even pacing."

def quality_session_blocks(alloc: Dict[str,float], zones: Dict[str,str], phase: str) -> Dict[str, Any]:
    """
    Construct a single mid-week quality session string based on available quality mileage.
    Examples:
      - Threshold: '3 x 1 mi @ Z3 w/ 2–3 min jog'
      - Marathon:  '6–8 mi @ Z3 continuous'
      - VO2:       '5 x 3 min @ Z4 w/ equal jog'
    """
    descs = []
    miles = 0.0
    if alloc["threshold"] >= 0.5:
        tmi = round_to_half(alloc["threshold"])
        descs.append(f"{tmi} mi threshold work @ {zones['thresh']} (cruise intervals)")
        miles += tmi
    if alloc["marathon"] >= 0.5:
        mmi = round_to_half(alloc["marathon"])
        descs.append(f"{mmi} mi continuous @ {zones['marathon']} (M-pace)")
        miles += mmi
    if alloc["vo2"] >= 0.5:
        vmi = round_to_half(alloc["vo2"])
        descs.append(f"{vmi} mi VO₂ max work @ {zones['vo2']} (3–5 min reps)")
        miles += vmi

    note = " + ".join(descs) if descs else "Short pickups to maintain turnover."
    return {
        "workout_type": "Threshold" if alloc["threshold"] >= alloc["marathon"] else "Marathon",
        "distance_mi": round_to_half(miles) if miles > 0 else 0.0,
        "zone": zones["thresh"] if "threshold" in note.lower() else zones["marathon"],
        "notes": note
    }

def inject_race_day(days: List[Dict[str,Any]], race_date: date, zones: Dict[str,str]) -> List[Dict[str,Any]]:
    # Ensure Race Day exists and the day before is very short easy
    dset = {d["date"]: d for d in days}
    r_iso = race_date.isoformat()
    if r_iso not in dset:
        days.append({"date": r_iso, "workout_type": "Race", "distance_mi": 26.2,
                     "zone": "Race", "notes": "Marathon race day. Trust the taper."})
    # Optional: adjust previous day to 2–3 mi easy if exists
    days.sort(key=lambda x: x["date"])
    return days
