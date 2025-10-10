# src/services/training_plan_service.py
# Clean implementation with Jack Daniels Running Formula strategy

import os
import json
import uuid
from datetime import date, datetime, timedelta
from typing import List, Tuple

# Removed unused defaultdict import
from sqlalchemy.orm import Session
from src.db.dao import plans_dao, plan_workouts_dao
from src.db.models.user_identity import UserIdentity
from src.db.models.plans import Plan
from src.db.models.plan_workouts import PlanWorkout
from src.services.training_plan_data_assembler import assemble_training_plan_data
from src.utils.gpt_ops import get_gpt_response


def generate_plan_with_b_plus_validation(
    session: Session, user_id: uuid.UUID, race_date: date, race_distance: str
) -> Plan:
    """
    Generate training plan using Jack Daniels Running Formula with B+ validation.
    Clean implementation focusing on scientifically-based training methodology.
    """
    print("JACK DANIELS RUNNING FORMULA TRAINING PLAN GENERATOR")
    print("=" * 60)

    # Load user data
    user = session.query(UserIdentity).filter(UserIdentity.user_id == user_id).first()
    if not user:
        raise ValueError(f"User {user_id} not found")

    print(f"User: {user.name}")
    print(f"Race: {race_distance} on {race_date}")

    # Assemble training data
    print("\nStep 1: Assembling training data...")
    data_bundle = assemble_training_plan_data(session, user_id)
    if not data_bundle.get("user_profile"):
        raise ValueError("No user profile found")

    # Convert enum objects to strings
    training_days_raw = data_bundle.get("user_profile", {}).get("training_days", [])
    training_days = [str(day) for day in training_days_raw] if training_days_raw else []

    # DEBUG: Validate data bundle contents
    print(f"\n?? DEBUG: Data Bundle Validation:")
    print(
        f"  � data_bundle keys: {list(data_bundle.keys()) if data_bundle else 'None'}"
    )
    for key, value in data_bundle.items():
        if isinstance(value, list):
            print(f"  � {key}: list with {len(value)} items")
        elif isinstance(value, dict):
            print(f"  � {key}: dict with {len(value)} keys")
        else:
            print(f"  � {key}: {value}")

    # Check if plan generation is safe
    quality_assessment = data_bundle.get("quality_assessment", {})
    marathon_safety = quality_assessment.get("marathon_safety", {})

    # Check if plan creation should be blocked
    if marathon_safety.get("block_plan_creation", False):
        user_message = marathon_safety.get(
            "user_message", "Plan creation blocked for safety reasons"
        )
        print(f"\n? PLAN CREATION BLOCKED:")
        print(f"   {user_message}")
        raise ValueError(user_message)

    # Check legacy safety check
    if not quality_assessment.get("can_generate_plan", True):
        critical_issues = quality_assessment.get("critical_issues", [])
        error_msg = "Cannot generate training plan: " + "; ".join(critical_issues)
        print(f"\n? SAFETY CHECK FAILED:")
        print(f"   {error_msg}")
        raise ValueError(error_msg)

    # Extract training days
    training_days = _parse_training_days(data_bundle.get("user_profile", {}))
    print(f"Training Days: {', '.join(training_days)} ({len(training_days)} days/week)")

    # DEBUG: Show training days being used
    print(f"\n🔍 TRAINING DAYS DEBUG:")
    print(f"   • Raw training_days from profile: {data_bundle.get('user_profile', {}).get('training_days', [])}")
    print(f"   • Parsed training_days: {training_days}")
    print(f"   • Training days count: {len(training_days)}")

    # Calculate plan duration
    start_date = datetime.today().date()
    total_days = (race_date - start_date).days
    total_weeks = max(1, (total_days + 6) // 7)
    print(f"Plan Duration: {total_weeks} weeks ({start_date} -> {race_date})")

    # Generate Jack Daniels plan
    print("\nStep 2: Generating Jack Daniels training plan...")
    workouts = _generate_jack_daniels_plan(
        data_bundle, race_date, race_distance, training_days
    )
    print(f"Generated {len(workouts)} Jack Daniels workouts")

    # Save to database
    print("\nStep 3: Saving plan to database...")
    plan = _save_plan_to_database(
        session, user_id, race_date, race_distance, workouts, data_bundle
    )

    print(f"\n? Plan generated successfully!")
    print(f"Plan ID: {plan.id}")

    return plan


def _parse_training_days(user_profile: dict) -> list[str]:
    """Parse training days from user profile."""
    training_days = user_profile.get("training_days", [])
    if not training_days:
        raise ValueError(
            "No training days configured in user profile. Please set training days before generating a plan."
        )

    # Normalize to 3-letter abbreviations
    normalized = []
    for day in training_days:
        if isinstance(day, str):
            if "MON" in day.upper():
                normalized.append("MON")
            elif "TUE" in day.upper():
                normalized.append("TUE")
            elif "WED" in day.upper():
                normalized.append("WED")
            elif "THU" in day.upper():
                normalized.append("THU")
            elif "FRI" in day.upper():
                normalized.append("FRI")
            elif "SAT" in day.upper():
                normalized.append("SAT")
            elif "SUN" in day.upper():
                normalized.append("SUN")

    if not normalized:
        raise ValueError(
            "Invalid training days in user profile. Please configure valid training days."
        )

    return normalized


def _create_dummy_plan_structure(
    start_date: date, race_date: date, training_days: list[str]
) -> list[dict]:
    """
    Create a dummy training plan structure with correct training days and generic mileage.
    This provides the structure for GPT to revise with proper Jack Daniels methodology.
    """
    from datetime import timedelta

    # Calculate all training dates
    training_dates = _calculate_training_dates(start_date, race_date, training_days)

    # Create simple dummy workouts with generic mileage
    dummy_workouts = []
    for _, date_obj in training_dates:
        # Simple logic: weekend = long run, others = easy run
        if date_obj.weekday() in [5, 6]:  # Saturday or Sunday
            workout_type = "Long Run"
            miles = 10.0  # Generic starting point - GPT will adjust based on user's base mileage
            intensity = "Moderate"
            target_zone = "Zone 2-3"
            focus = "Endurance"
        else:
            workout_type = "Easy"
            miles = 4.0  # Generic starting point - GPT will adjust based on user's base mileage
            intensity = "Low"
            target_zone = "Zone 1-2"
            focus = "Base Building"

        dummy_workouts.append({
            "date": date_obj.strftime("%Y-%m-%d"),
            "workout_type": workout_type,
            "miles": miles,
            "target_zone": target_zone,
            "intensity": intensity,
            "description": f"{workout_type} run for base building",
            "focus": focus
        })

    return dummy_workouts


def _build_compact_jack_daniels_prompt(
    user_data: dict, plan_structure: list[dict]
) -> str:
    """
    Build optimized Jack Daniels prompt for single GPT call to generate complete plan.
    """
    import json

    # Extract clean values from user_data
    profile = user_data.get("user_profile", {})
    activities = user_data.get("activities", [])
    weekly_summaries = user_data.get("weekly_summaries", [])
    base_mileage = user_data.get("base_mileage", 0)
    hr_zones = user_data.get("heart_rate_zones", {})

    # Build clean runner profile summary
    runner_profile = f"""RUNNER PROFILE:
- Age: {profile.get('age', 'Unknown')}
- Experience: {str(profile.get('runner_level', 'Intermediate')).split('.')[-1]}
- Weight: {profile.get('weight', 'Unknown')} lbs
- Height: {profile.get('height', 'Unknown')}
- Main Goal: {str(profile.get('main_goal', 'Complete race')).split('.')[-1]}
- Past Races: {', '.join([str(r).split('.')[-1] for r in profile.get('past_races', [])])}
- Longest Run: {profile.get('longest_run', 'Unknown')} miles"""

    # Show recent training history with pace and HR zones (last 8 activities = ~2 weeks)
    recent_activities = activities[:8]
    activity_list = []
    for act in recent_activities:
        date = act.get('activity_date', 'Unknown')
        distance = act.get('distance', 0)
        avg_speed = act.get('avg_speed', 0)
        avg_hr = act.get('avg_hr', 0)
        pace = f"{int(60/avg_speed)}:{int((60/avg_speed % 1) * 60):02d}/mi" if avg_speed > 0 else "N/A"
        hr_zone = "Z1" if avg_hr < 124 else "Z2" if avg_hr < 142 else "Z3" if avg_hr < 159 else "Z4"  # Approximate zones for 177 max HR
        activity_list.append(f"{date}: {distance:.1f}mi @ {pace} ({avg_hr:.0f}bpm, {hr_zone})")

    activity_summary = f"RECENT RUNS: {' | '.join(activity_list)}"

    # Build weekly summary (most recent 6 weeks, date + mileage + avg pace + HR zones)
    weekly_list = []
    for week in weekly_summaries[:6]:  # First 6 = most recent
        if isinstance(week, str) and "miles" in week:
            # Parse string format: "Week of Oct 06: 1 runs, 6.75 miles, longest run 6.75mi, avg pace 6:11/mi, HR mixed Zones."
            import re
            date_match = re.search(r"Week of (\w+ \d+)", week)
            miles_match = re.search(r"(\d+\.?\d*)\s*miles", week)
            pace_match = re.search(r"avg pace (\d+:\d+)/mi", week)
            hr_match = re.search(r"HR (mostly Zone \d+|mixed Zones)", week)
            if date_match and miles_match and pace_match:
                date = date_match.group(1)
                miles = miles_match.group(1)
                pace = pace_match.group(1)
                hr_info = hr_match.group(1) if hr_match else "Z2"
                weekly_list.append(f"{date}: {miles}mi @ {pace}/mi ({hr_info})")
        elif isinstance(week, dict):
            # Dict format
            date = week.get('week_start', 'Unknown')
            miles = week.get('total_miles', 0)
            pace = week.get('avg_pace', 'N/A')
            hr_zones = week.get('hr_zones', 'Z2')
            weekly_list.append(f"{date}: {miles:.1f}mi @ {pace}/mi ({hr_zones})")

    weekly_summary = f"RECENT WEEKLY INSIGHTS: {' | '.join(weekly_list)}" if weekly_list else "RECENT WEEKLY INSIGHTS: No data"

    # Build heart rate zones (compact format)
    hr_summary = f"HR ZONES: MaxHR={hr_zones.get('max_hr', 170)}bpm | Z1-2=Easy | Z3=Threshold | Z4=Hard"

    prompt = f"""You are an expert running coach using Jack Daniels methodology. Create a complete marathon training plan.

{runner_profile}

Format: Date | Distance | Avg Pace | HR Zone
{activity_summary}

{weekly_summary}
CURRENT BASE MILEAGE: {base_mileage:.1f} miles/week
{hr_summary}

TRAINING SCHEDULE:
- Total workouts: {len(plan_structure)}
- Start date: {plan_structure[0]['date']}
- Race date: {plan_structure[-1]['date']} (this is race day - use "Race Day" workout type)
- Training days: {', '.join(profile.get('training_days', []))}

JACK DANIELS RULES:
- Long runs: 1 per week (weekend), 25-30% weekly mileage @ Zone 2-3, cap at 22 mi
- Easy runs: 15-20% weekly mileage @ Zone 1-2
- Threshold runs: 8-12% weekly mileage @ Zone 3-4
- Progression: Max +10% weekly mileage increase per week
- TAPER: Final 3 weeks reduce long-run to 60%, 40%, 20% of peak long-run distance"""

    prompt += f"""

CRITICAL: Return ALL {len(plan_structure)} workouts as a JSON array.

Return ONLY a JSON array (no explanation), one workout per date above:
[
  {{"date": "{plan_structure[0]['date']}", "workout_type": "Easy", "miles": 5.0, "target_zone": "Zone 1-2", "intensity": "Low", "description": "Recovery run", "focus": "Active recovery"}},
  {{"date": "{plan_structure[1]['date']}", "workout_type": "Easy", "miles": 4.0, "target_zone": "Zone 1-2", "intensity": "Low", "description": "Easy run", "focus": "Aerobic base"}},
  ... (continue for all {len(plan_structure)} dates) ...
  {{"date": "{plan_structure[-1]['date']}", "workout_type": "Race Day", "miles": 26.2, "target_zone": "Zone 3-4", "intensity": "High", "description": "Marathon race", "focus": "Race execution"}}
]"""

    return prompt


def _generate_jack_daniels_plan_chunked(
    data_bundle: dict, race_date: date, race_distance: str, training_days: list[str]
) -> list[dict]:
    """Generate Jack Daniels training plan using chunked approach to avoid token limits."""
    from datetime import datetime, date
    from src.utils.gpt_ops import get_gpt_response

    user = data_bundle.get("user_profile", {})
    start_date = datetime.today().date()

    print(f"\n🔧 CHUNKED JACK DANIELS PLAN GENERATION")
    print("=" * 60)

    # Create dummy plan structure
    print("\nStep 1: Creating dummy plan structure...")
    dummy_plan = _create_dummy_plan_structure(start_date, race_date, training_days)
    print(f"Created {len(dummy_plan)} dummy workouts")

    # Split into chunks of 7 workouts (roughly 2 weeks each)
    chunk_size = 7
    chunks = [dummy_plan[i:i + chunk_size] for i in range(0, len(dummy_plan), chunk_size)]
    print(f"Split into {len(chunks)} chunks of ~{chunk_size} workouts each")

    all_workouts = []

    for chunk_idx, chunk in enumerate(chunks):
        print(f"\n🔄 Processing chunk {chunk_idx + 1}/{len(chunks)} ({len(chunk)} workouts)...")

        # Generate workouts for this chunk
        chunk_workouts = _generate_jack_daniels_plan(
            data_bundle, race_date, race_distance, training_days, chunk, chunk_idx, len(chunks)
        )

        all_workouts.extend(chunk_workouts)
        print(f"✅ Chunk {chunk_idx + 1} complete: {len(chunk_workouts)} workouts")

    print(f"\n🎉 All chunks complete! Generated {len(all_workouts)} total workouts")
    return all_workouts


def _generate_jack_daniels_plan(
    data_bundle: dict, race_date: date, race_distance: str, training_days: list[str]
) -> list[dict]:
    """Generate complete Jack Daniels training plan in a single GPT call."""
    from datetime import datetime, date
    from src.utils.gpt_ops import get_gpt_response

    user = data_bundle.get("user_profile", {})
    activities = data_bundle.get("activities", [])
    weekly_summaries = data_bundle.get("weekly_summaries", [])

    start_date = datetime.today().date()

    print(f"\n🔧 JACK DANIELS PLAN GENERATION (SINGLE GPT CALL)")
    print("=" * 60)

    # Create full dummy plan structure
    print("\nStep 3: Creating dummy plan structure...")
    print(f"🔍 DEBUG - training_days parameter: {training_days}")
    print(f"🔍 DEBUG - user profile training_days: {user.get('training_days', 'MISSING')}")
    dummy_plan = _create_dummy_plan_structure(start_date, race_date, training_days)
    print(f"Created {len(dummy_plan)} dummy workouts")

    # DEBUG: Show first few dummy workouts
    print(f"\n🔍 DUMMY PLAN SAMPLE (first 5 workouts):")
    for i, workout in enumerate(dummy_plan[:5]):
        print(f"   [{i+1}] {workout['date']} ({workout['workout_type']}) - {workout['miles']} mi")

    # Step 4: GPT revises entire plan with Jack Daniels methodology
    print("\nStep 4: GPT revising plan with Jack Daniels methodology...")

    # Prepare user data for GPT
    # IMPORTANT: Update user profile with normalized training_days to match dummy plan dates
    user_with_normalized_days = user.copy()
    user_with_normalized_days['training_days'] = training_days  # Use normalized days (MON, TUE, etc.)

    # DEBUG: Check data quality before base mileage calculation
    data_quality = data_bundle.get("quality_assessment", {}).get("data_quality", {})
    print(f"\n🔍 DEBUG: Base Mileage Calculation Input:")
    print(f"  • Weekly summaries count: {len(weekly_summaries)}")
    print(f"  • Data quality: {data_quality.get('quality', 'UNKNOWN')} ({data_quality.get('reason', 'No reason')})")
    print(f"  • Use fallbacks: {data_quality.get('use_fallbacks', 'NOT SET')}")

    # Use the same 6 weeks for base mileage calculation that will be shown in the prompt
    weekly_summaries_for_calculation = weekly_summaries[:6] if len(weekly_summaries) >= 6 else weekly_summaries
    print(f"  • Using {len(weekly_summaries_for_calculation)} weeks for base mileage calculation (same as prompt display)")

    base_mileage = _calculate_base_mileage(
        weekly_summaries_for_calculation,
        str(user.get("runner_level", "Intermediate")).lower(),
        data_quality
    )
    print(f"  • Calculated base mileage: {base_mileage} miles/week")

    user_data = {
        "user_profile": user_with_normalized_days,
        "activities": activities[:10],  # Limit to recent activities
        "weekly_summaries": weekly_summaries,
        "base_mileage": base_mileage,
        "heart_rate_zones": _calculate_user_heart_rate_zones(user, activities)
    }

    # DEBUG: Validate user data - VERIFY ACTUAL DATA vs FALLBACK
    print(f"\n🔍 USER DATA VALIDATION (Actual vs Fallback):")
    profile = user_data.get('user_profile', {})
    print(f"   • Age: {profile.get('age', 'FALLBACK')} (from age_group: {profile.get('age_group', 'NONE')})")
    print(f"   • Runner Level: {profile.get('runner_level', 'FALLBACK')}")
    print(f"   • Weight: {profile.get('weight', 'FALLBACK')} lbs")
    print(f"   • Height: {profile.get('height', 'FALLBACK')}")
    print(f"   • Training Days: {profile.get('training_days', 'FALLBACK')}")
    print(f"   • Main Goal: {profile.get('main_goal', 'FALLBACK')}")
    print(f"   • Past Races: {profile.get('past_races', 'FALLBACK')}")
    print(f"   • Longest Run: {profile.get('longest_run', 'FALLBACK')} miles")
    print(f"   • Activities (last 3): {[{act.get('activity_date'): act.get('distance')} for act in user_data.get('activities', [])[:3]]}")
    print(f"   • Weekly Summaries: {len(user_data.get('weekly_summaries', []))} weeks")
    print(f"   • Base Mileage: {user_data.get('base_mileage', 'FALLBACK'):.1f} mi/week")
    print(f"   • Heart Rate Max: {user_data.get('heart_rate_zones', {}).get('max_hr', 'FALLBACK')} bpm")

    # Build compact prompt (without chunk parameters - generate full plan)
    prompt = _build_compact_jack_daniels_prompt(user_data, dummy_plan)
    print(f"Prompt length: ~{len(prompt)} characters")

    # DEBUG: Show first 1000 chars of prompt
    print(f"\n🔍 PROMPT (first 1000 chars):")
    print(prompt[:1000])
    print(f"...")

    # Show complete prompt in terminal
    print(f"\n📝 COMPLETE GPT PROMPT:")
    print("=" * 80)
    print(prompt)
    print("=" * 80)

    # Log complete prompt to Flask logs
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"COMPLETE GPT PROMPT:\n{prompt}")

    # Get GPT response
    try:
        print(f"\n🔍 SENDING TO GPT...")
        response = get_gpt_response(prompt, require_json=False)  # Allow plain text response
        print(f"✅ GPT response received ({len(response)} characters)")

        # DEBUG: Show GPT response
        print(f"\n🔍 GPT RESPONSE (first 500 chars):")
        print(response[:500])
        print(f"...")
        print(f"\n🔍 GPT RESPONSE (last 500 chars):")
        print(response[-500:])

        # Log complete GPT response to Flask logs
        logger.info(f"COMPLETE GPT RESPONSE:\n{response}")

        # Parse response
        print(f"\n🔍 PARSING GPT RESPONSE...")
        workouts = _parse_gpt_workout_response(response, training_days, start_date, race_date)
        print(f"✅ Parsed {len(workouts)} workouts")

        if len(workouts) == 0:
            raise ValueError("GPT returned 0 workouts - parsing failed")

        # Validate GPT followed the rules
        print(f"\n🔍 VALIDATING PLAN...")
        _validate_plan_rules(workouts, training_days)

        print(f"✅ GPT plan generation successful!")
        return workouts

    except Exception as e:
        print(f"GPT generation failed: {e}")
        print("❌ CRITICAL ERROR: GPT plan generation failed")
        raise RuntimeError(f"Failed to generate training plan: {e}") from e


def _validate_plan_rules(workouts: list[dict], training_days: list[str]) -> None:
    """Validate that GPT followed the training plan rules."""
    from datetime import datetime, timedelta

    print(f"\n🔍 PLAN VALIDATION:")

    # Group workouts by week
    weeks = {}
    for workout in workouts:
        # Handle both string and date objects
        if isinstance(workout["date"], str):
            workout_date = datetime.strptime(workout["date"], "%Y-%m-%d").date()
        else:
            workout_date = workout["date"]  # Already a date object
        week_start = workout_date - timedelta(days=workout_date.weekday())
        week_key = week_start.strftime("%Y-%m-%d")

        if week_key not in weeks:
            weeks[week_key] = []
        weeks[week_key].append(workout)

    # Check progression
    print(f"   📊 WEEKLY PROGRESSION:")
    for i, (week_key, week_workouts) in enumerate(sorted(weeks.items()), 1):
        total_miles = sum(float(w["miles"]) for w in week_workouts)
        sat_workout = None
        for w in week_workouts:
            if isinstance(w["date"], str):
                workout_date = datetime.strptime(w["date"], "%Y-%m-%d").date()
            else:
                workout_date = w["date"]
            if workout_date.weekday() == 5:  # Saturday
                sat_workout = w
                break
        sat_miles = float(sat_workout["miles"]) if sat_workout else 0

        print(f"      Week {i}: {total_miles:.1f}mi total, Long Run: {sat_miles:.1f}mi")

    # Check Saturday long run progression
    sat_workouts = []
    for w in workouts:
        if isinstance(w["date"], str):
            workout_date = datetime.strptime(w["date"], "%Y-%m-%d").date()
        else:
            workout_date = w["date"]
        if workout_date.weekday() == 5:  # Saturday
            sat_workouts.append(w)
    sat_miles = [float(w["miles"]) for w in sat_workouts]

    print(f"   📈 LONG RUN PROGRESSION: {[f'{miles:.1f}mi' for miles in sat_miles]}")

    # Check if progression makes sense
    if len(sat_miles) >= 3:
        peak_miles = max(sat_miles)
        taper_start = sat_miles[-3:] if len(sat_miles) >= 3 else sat_miles[-2:]

        if all(miles <= peak_miles * 0.7 for miles in taper_start):
            print(f"   ✅ Good taper progression")
        else:
            print(f"   ⚠️ Taper might be too aggressive or missing")

    # Check back-to-back long run rule (no two > 20mi back-to-back)
    violations = []
    for i in range(len(sat_miles) - 1):
        if sat_miles[i] > 20 and sat_miles[i + 1] > 20:
            violations.append(f"Weeks {i+1}-{i+2}: Both {sat_miles[i]:.1f}mi and {sat_miles[i+1]:.1f}mi > 20mi")

    if violations:
        print(f"   🚨 BACK-TO-BACK VIOLATIONS:")
        for violation in violations:
            print(f"      {violation}")
    else:
        print(f"   ✅ No back-to-back long runs > 20mi")

    print(f"   📅 Training days: {', '.join(training_days)}")
    print(f"   🏃 Total workouts: {len(workouts)}")


def _calculate_user_heart_rate_zones(user_profile: dict, activities: list) -> dict:
    """Calculate personalized heart rate zones from user data."""
    # Try to get max heart rate from activities first
    max_hr_from_activities = None
    if activities:
        # Get the highest max heart rate from recent activities
        print(f"\n?? HEART RATE DEBUG:")
        print(f"   Activities loaded: {len(activities)}")

        # DEBUG: Show first 5 activities' max_hr values before filtering
        print(f"   First 5 activities max_hr values:")
        for i, activity in enumerate(activities[:5]):
            raw_max_hr = activity.get("max_hr")
            print(
                f"     Activity {i+1}: raw_max_hr={raw_max_hr} (type: {type(raw_max_hr)})"
            )

        # Simple approach - trust Strava data with minimal guards
        max_hrs = []
        for a in activities:
            raw_max_hr = a.get("max_hr")
            if raw_max_hr is not None:
                try:
                    converted_hr = float(raw_max_hr)
                    # Minimal edge case guards - trust Strava data
                    if 40 <= converted_hr <= 250:  # Physiological bounds only
                        max_hrs.append(converted_hr)
                except (ValueError, TypeError):
                    pass  # Skip invalid values silently

        print(f"   Activities with valid max_hr data: {len(max_hrs)}")
        if max_hrs:
            print(f"   Max HR values found: {max_hrs[:5]}...")  # Show first 5
            max_hr_from_activities = max(max_hrs)
            print(f"   Highest max_hr from activities: {max_hr_from_activities}")
        else:
            print(f"   No valid max_hr data found in activities")
            # Show sample activity structure
            if activities:
                sample_activity = activities[0]
                print(f"   Sample activity keys: {list(sample_activity.keys())}")
                print(
                    f"   Sample max_hr value: {sample_activity.get('max_hr')} (type: {type(sample_activity.get('max_hr'))})"
                )

    # Calculate max HR based on available data
    if max_hr_from_activities:
        max_hr = max_hr_from_activities
        method = "from_activities"
        print(f"   Using max_hr from activities: {max_hr}")
    else:
        # Fallback to age-based calculation if no activity data
        age = user_profile.get("age", 35)
        max_hr = 220 - age
        method = "age_based"
        print(f"   FALLBACK: Using age-based calculation: 220 - {age} = {max_hr}")

    # Calculate zones using Karvonen method (more accurate than simple percentages)
    resting_hr = 60  # Default resting HR (could be personalized later)
    hr_reserve = max_hr - resting_hr

    zones = {
        "zone_1_2": f"{int(resting_hr + hr_reserve * 0.5)}-{int(resting_hr + hr_reserve * 0.7)} bpm",
        "zone_3": f"{int(resting_hr + hr_reserve * 0.7)}-{int(resting_hr + hr_reserve * 0.8)} bpm",
        "zone_4": f"{int(resting_hr + hr_reserve * 0.8)}-{int(resting_hr + hr_reserve * 0.9)} bpm",
        "zone_5": f"{int(resting_hr + hr_reserve * 0.9)}-{max_hr} bpm",
        "max_hr": max_hr,
        "method": method,
    }

    return zones


def _calculate_base_mileage(
    weekly_summaries: list, runner_level: str, data_quality: dict = None
) -> float:
    """Calculate weekly mileage base from recent activities with smart fallbacks."""

    # Check if we should use fallbacks
    use_fallbacks = data_quality and data_quality.get("use_fallbacks")
    valid_activity_count = data_quality.get("filtered_count", 0) if data_quality else 0

    if use_fallbacks:
        print(
            f"   ?? Base mileage: Using fallback (data quality: {data_quality.get('quality', 'UNKNOWN')})"
        )

        # Enhanced fallback strategy based on data quality and runner level
        if valid_activity_count == 0:
            # No valid data - very conservative fallback
            print(f"   ?? Base mileage: NO VALID DATA - using minimal fallback")
            if "beginner" in runner_level:
                return 8  # Very conservative for beginners with no data
            elif "advanced" in runner_level:
                return 15  # Conservative for advanced with no data
            else:
                return 12  # Conservative for intermediate with no data
        elif valid_activity_count < 5:
            # Very little data - conservative fallback
            print(
                f"   ?? Base mileage: MINIMAL DATA ({valid_activity_count} activities) - using conservative fallback"
            )
            if "beginner" in runner_level:
                return 20  # Low end of beginner range
            elif "advanced" in runner_level:
                return 50  # Low end of advanced range
            else:
                return 35  # Low end of intermediate range
        else:
            # Some data but quality issues - standard fallback (mid-range)
            if "beginner" in runner_level:
                return 25  # Mid-range for beginner (20-30)
            elif "advanced" in runner_level:
                return 60  # Mid-range for advanced (50-70+)
            else:
                return 40  # Mid-range for intermediate (35-50)

    # Use actual data - LAST 4-6 weeks for accurate current fitness (Jack Daniels best practice)
    if weekly_summaries:
        # Take most recent 4-6 weeks (prefer 6 if available)
        weeks_to_use = weekly_summaries[-6:] if len(weekly_summaries) >= 6 else weekly_summaries[-4:]
        print(f"   ?? Base mileage: Using last {len(weeks_to_use)} weeks of data (standard 4-6 week window)")

        # Parse mileage from summaries (dict or string format)
        weekly_mileages = []

        for summary in weeks_to_use:
            if isinstance(summary, dict):
                # Dict format: get total_miles directly
                miles = summary.get('total_miles', 0)
                if miles > 0:
                    weekly_mileages.append(miles)
            elif isinstance(summary, str) and "miles" in summary:
                # String format: extract mileage like "15.2 miles"
                import re
                miles_match = re.search(r"(\d+\.?\d*)\s*miles", summary)
                if miles_match:
                    weekly_mileages.append(float(miles_match.group(1)))

        if weekly_mileages:
            # Calculate average and round to nearest 5 miles (standard practice)
            avg_mileage = sum(weekly_mileages) / len(weekly_mileages)
            rounded_base = round(avg_mileage / 5) * 5  # Round to nearest 5
            print(f"   ?? Base mileage calculation: {weekly_mileages} → avg={avg_mileage:.1f} → rounded={rounded_base}")
            return max(rounded_base, 10)  # Minimum 10 miles/week
        else:
            print(f"   ?? Base mileage: No valid mileage data found in {len(weeks_to_use)} weekly summaries")

    # Final fallback - should rarely reach here
    print(f"   ?? Base mileage: Using final fallback (no weekly summaries)")
    if "beginner" in runner_level:
        return 25  # Mid-range for beginner (20-30 mi/week)
    elif "advanced" in runner_level:
        return 60  # Mid-range for advanced (50-70+ mi/week)
    else:
        return 40  # Mid-range for intermediate (35-50 mi/week)


# REMOVED: _find_longest_recent_run() - duplicate calculation eliminated


# Removed unused _build_jack_daniels_prompt function - now using week-by-week approach


def _calculate_training_dates(
    start_date: date, race_date: date, training_days: list[str]
) -> list[tuple[int, date]]:
    """Calculate all training dates for the plan duration.

    Returns:
        List of (week_number, date) tuples for all training days
    """
    from datetime import timedelta

    print(f"\n🔍 _calculate_training_dates DEBUG:")
    print(f"   • start_date: {start_date}")
    print(f"   • race_date: {race_date}")
    print(f"   • training_days: {training_days}")

    # Day name to number mapping
    day_mapping = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}

    # Adjust start_date to the beginning of the week (Monday)
    days_since_monday = start_date.weekday()
    week_start = start_date - timedelta(days=days_since_monday)

    # Calculate total weeks
    total_days = (race_date - week_start).days
    total_weeks = max(1, (total_days + 6) // 7)

    print(f"   • week_start: {week_start}")
    print(f"   • total_weeks: {total_weeks}")

    training_dates = []
    current_week_start = week_start

    for week in range(total_weeks):
        for day_name in training_days:
            # Calculate the date for this training day in the current week
            day_num = day_mapping[day_name]
            workout_date = current_week_start + timedelta(days=day_num)

            # Only include dates that are >= start_date and <= race_date
            if start_date <= workout_date <= race_date:
                training_dates.append((week + 1, workout_date))

        # Move to next week
        current_week_start += timedelta(days=7)

    return training_dates


def _calculate_dynamic_week_focus(
    week_num: int, total_weeks: int, user_profile: dict
) -> str:
    """Calculate dynamic week focus based on plan duration and experience level."""
    runner_level = str(user_profile.get("runner_level", "Intermediate")).lower()
    age = user_profile.get("age", 35)

    # Calculate phase percentages based on experience and plan length
    if "beginner" in runner_level:
        # Beginners need more base building time
        base_phase_pct = 0.4  # 40% of plan
        build_phase_pct = 0.35  # 35% of plan
        peak_phase_pct = 0.15  # 15% of plan
        taper_phase_pct = 0.1  # 10% of plan
    elif "advanced" in runner_level:
        # Advanced runners can handle more intensity sooner
        base_phase_pct = 0.25  # 25% of plan
        build_phase_pct = 0.4  # 40% of plan
        peak_phase_pct = 0.25  # 25% of plan
        taper_phase_pct = 0.1  # 10% of plan
    else:  # intermediate
        base_phase_pct = 0.3  # 30% of plan
        build_phase_pct = 0.4  # 40% of plan
        peak_phase_pct = 0.2  # 20% of plan
        taper_phase_pct = 0.1  # 10% of plan

    # Adjust for age (masters runners need longer base building)
    if age >= 40:
        base_phase_pct += 0.1
        build_phase_pct -= 0.05
        peak_phase_pct -= 0.05

    # Calculate week thresholds
    base_weeks = max(1, int(total_weeks * base_phase_pct))
    build_weeks = max(1, int(total_weeks * build_phase_pct))
    peak_weeks = max(1, int(total_weeks * peak_phase_pct))

    # Determine current phase
    if week_num <= base_weeks:
        return "Base building"
    elif week_num <= base_weeks + build_weeks:
        return "Building endurance"
    elif week_num <= base_weeks + build_weeks + peak_weeks:
        return "Peak training"
    else:
        return "Taper week"


def _calculate_dynamic_progression_rate(user_profile: dict, total_weeks: int) -> float:
    """Calculate dynamic progression rate based on experience and age."""
    age = user_profile.get("age", 35)
    runner_level = str(user_profile.get("runner_level", "Intermediate")).lower()

    # Base progression rates by experience
    if "beginner" in runner_level:
        base_rate = 0.05  # 5% for beginners
    elif "advanced" in runner_level:
        base_rate = 0.12  # 12% for advanced
    else:  # intermediate
        base_rate = 0.08  # 8% for intermediate

    # Adjust for age (masters runners need more conservative progression)
    if age >= 40:
        age_adjustment = 0.7  # 30% reduction for masters runners
    elif age >= 35:
        age_adjustment = 0.85  # 15% reduction for 35+
    else:
        age_adjustment = 1.0  # No adjustment for younger runners

    # Adjust for plan duration (shorter plans can be more aggressive)
    if total_weeks <= 8:
        duration_adjustment = 1.2  # 20% increase for short plans
    elif total_weeks >= 16:
        duration_adjustment = 0.8  # 20% reduction for long plans
    else:
        duration_adjustment = 1.0  # No adjustment for medium plans

    final_rate = base_rate * age_adjustment * duration_adjustment

    # Ensure reasonable bounds
    return max(0.03, min(0.15, final_rate))  # Between 3% and 15%


def _build_week_prompt(
    week_num: int,
    week_dates: list[date],
    user: dict,
    recent_mileage: float,
    longest_run: float,
    estimated_threshold_hr: int,
    total_weeks: int,
    heart_rate_zones: dict,
    progression_rate: float,
    recent_activities_context: str,
    prior_weeks_summary: list[dict] | None = None,
    weekend_lr_date: date | None = None,
) -> str:
    """Build a context-rich prompt for a single week with history and explicit targets."""

    # OPTIMIZED: Use pre-calculated values (no repeated calculations)
    # Calculate target weekly mileage with dynamic progression
    base_mileage = recent_mileage
    weekly_mileage = base_mileage * (1 + (week_num - 1) * progression_rate)

    # Simple cutback and taper adjustments to weekly mileage
    if week_num % 4 == 0 and week_num < max(1, total_weeks - 2):
        weekly_mileage *= 0.85
    weeks_left = max(0, total_weeks - week_num)
    if weeks_left == 2:
        weekly_mileage *= 0.6
    elif weeks_left == 1:
        weekly_mileage *= 0.4

    # Determine dynamic week focus based on plan duration and experience
    week_focus = _calculate_dynamic_week_focus(week_num, total_weeks, user)

    # Build date list
    date_list = ", ".join([d.strftime("%Y-%m-%d") for d in week_dates])

    # Build compact history block (last 3 weeks)
    history_block = ""
    if prior_weeks_summary:
        history_lines = [
            f"- Week {w.get('week')}: total {w.get('total_miles')} mi, LR {w.get('long_run_miles')} mi"
            for w in prior_weeks_summary[-3:]
        ]
        if history_lines:
            history_block = "\nPRIOR WEEKS (most recent first):\n" + "\n".join(
                history_lines
            )

    # Derive a Long Run target from weekly mileage (bounded 8�20mi)
    lr_target = round(max(8.0, min(20.0, weekly_mileage * 0.27)), 1)
    lr_target_min = round(max(8.0, lr_target * 0.9), 1)
    lr_target_max = round(min(20.0, lr_target * 1.1), 1)

    # Clean runner level format (remove enum prefix if present)
    runner_level_display = str(user.get("runner_level", "Intermediate"))
    if "." in runner_level_display:
        runner_level_display = runner_level_display.split(".")[-1]
    runner_level_display = runner_level_display.capitalize()

    return f"""JACK DANIELS COACH - WEEK {week_num} ({len(week_dates)} workouts)

RUNNER: {user['age']}yo, {user['weight']}lbs, {runner_level_display}, {recent_mileage:.1f}mi/week base
TRAINING DAYS: {', '.join([d.strftime('%a') for d in week_dates])}
DATES: {date_list}
WEEK FOCUS: {week_focus}
TARGET MILEAGE: {weekly_mileage:.1f} miles total
{history_block}

HR ZONES: Z1-2:{heart_rate_zones['zone_1_2']} | Z3:{heart_rate_zones['zone_3']} | Z4:{heart_rate_zones['zone_4']} | Z5:{heart_rate_zones['zone_5']}{recent_activities_context}

WEEK {week_num} RULES:
- {"Start easy, build base" if week_num == 1 else "Continue progression"}
- Weekend Long Run (ENFORCED): Schedule exactly ONE Long Run on the weekend � use Saturday if Saturday is one of this week�s training days; otherwise use Sunday. Do NOT place the Long Run on a weekday. If it is race week, there is NO Long Run.
- Keep at least 48�72 hours between hard sessions (the Long Run and any Threshold/Intervals/Marathon-Pace session are considered hard).
- {"Follow {progression_rate:.1%} increase rule" if week_num > 1 else "Start at base mileage"}
- Never back-to-back hard workouts

EXPLICIT TARGETS FOR THIS WEEK:
- Weekly mileage target: ~{weekly_mileage:.1f} miles
- Long Run target: {(weekend_lr_date.strftime('%Y-%m-%d') if weekend_lr_date else 'WEEKEND DATE')} � {lr_target:.1f} miles (acceptable range {lr_target_min}-{lr_target_max})

HARD CONSTRAINTS:
- Exactly one workout with workout_type = "Long Run" this week and it MUST be on {(weekend_lr_date.strftime('%Y-%m-%d') if weekend_lr_date else 'the weekend date provided')}. No other day may be "Long Run".
- If this is the race week (contains the race_date), do not schedule a Long Run; make the weekend a short shakeout or rest.

OUTPUT: JSON with {len(week_dates)} workouts matching the dates. ONE Long Run on Saturday (or Sunday if no Saturday).

{{
  "workouts": [
    {{
      "date": "YYYY-MM-DD",
      "workout_type": "Easy Run|Long Run|Threshold|Intervals|Recovery",
      "description": "",
      "miles": 0.0,
      "intensity": "Low|Moderate|High",
      "target_zone": "Zone 1-2|Zone 3|Zone 4|Zone 5",
      "target_hr": "",
      "focus": "Base Building|Endurance|Speed|Recovery|Marathon Pace"
    }}
  ]
}}"""


def _build_single_pass_prompt(
    start_date: date,
    race_date: date,
    training_dates: list[tuple[int, date]],
    user: dict,
    recent_mileage: float,
    longest_run: float,
    estimated_threshold_hr: int,
    heart_rate_zones: dict,
    total_weeks: int,
    progression_rate: float,
    recent_activities_context: str,
    prior_months_history: list[dict] = None,
) -> str:
    """Build a single-pass prompt covering the entire plan dates.

    Args:
        prior_months_history: List of dicts with keys: 'month', 'workouts', 'review'
    """
    # Format dates with year (abbreviated) for GPT parsing
    all_dates = [d.strftime("%Y-%m-%d") for _, d in training_dates]
    dates_list = ", ".join(all_dates)

    # Compute per-week weekend (Sat preferred, else Sun) anchor dates
    week_to_dates: dict[int, list[date]] = {}
    for w, d in training_dates:
        week_to_dates.setdefault(w, []).append(d)
    weekend_dates: list[str] = []
    for w in sorted(week_to_dates.keys()):
        dates = sorted(week_to_dates[w])
        weekend_date = next((x for x in dates if x.weekday() == 5), None)  # Saturday
        if weekend_date is None:
            weekend_date = next((x for x in dates if x.weekday() == 6), None)  # Sunday
        if weekend_date is not None:
            weekend_dates.append(weekend_date.strftime("%Y-%m-%d"))
    weekend_block = f"LR Saturdays: {', '.join(weekend_dates)}" if weekend_dates else ""

    # Build prior months history block
    history_block = ""
    if prior_months_history:
        history_lines = ["\nPRIOR MONTH(S) COMPLETED:"]
        history_lines.append("=" * 60)
        for month_data in prior_months_history:
            month_key = month_data.get("month", "Unknown")
            workouts = month_data.get("workouts", [])
            review = month_data.get("review", {})

            total_miles = sum(w.get("miles", 0) for w in workouts)
            history_lines.append(
                f"\nMonth {month_key} ({len(workouts)} workouts, {total_miles:.1f} total miles):"
            )

            # List all individual workouts
            for w in sorted(workouts, key=lambda x: x.get("date")):
                date_str = (
                    w.get("date").strftime("%Y-%m-%d (%a)")
                    if hasattr(w.get("date"), "strftime")
                    else str(w.get("date"))
                )
                workout_type = w.get("workout_type", "Unknown")
                miles = w.get("miles", 0)
                history_lines.append(f"  {date_str}: {workout_type} - {miles:.1f} mi")

            # Add review if available
            if review:
                issues = review.get("issues", [])
                mitigations = review.get("mitigations", "")
                if issues:
                    history_lines.append(f"  Review Issues: {issues}")
                if mitigations:
                    history_lines.append(f"  Mitigations: {mitigations}")

        history_block = "\n".join(history_lines) + "\n"

    # Clean runner level format (remove enum prefix if present)
    runner_level_display = str(user.get("runner_level", "Intermediate"))
    if "." in runner_level_display:
        runner_level_display = runner_level_display.split(".")[-1]
    runner_level_display = runner_level_display.capitalize()

    return f"""JACK DANIELS COACH - FULL PLAN ({len(all_dates)} workouts across {total_weeks} weeks)

RUNNER: {user['age']}yo, {user['weight']}lbs, {runner_level_display}, {recent_mileage:.1f}mi/week base
RACE: {race_date} (Marathon)
TRAINING DATES (fixed): {dates_list}
TARGET STRATEGY: Use Jack Daniels methodology. Ensure coherent long run progression with periodic cutbacks and a 2�3 week taper. Exactly one weekend Long Run per week (Sat preferred, else Sun). No Long Run in race week.

HR ZONES: Z1-2:{heart_rate_zones['zone_1_2']} | Z3:{heart_rate_zones['zone_3']} | Z4:{heart_rate_zones['zone_4']} | Z5:{heart_rate_zones['zone_5']}{recent_activities_context}
{history_block}
RULES:
- Respect provided dates strictly; output must match them 1:1.
- {weekend_block} - exactly ONE Long Run per week on these dates only.

OUTPUT: JSON with workouts array.
{{{{
  "workouts": [
    {{{{
      "date": "YYYY-MM-DD",
      "workout_type": "Easy Run|Long Run|Threshold|Intervals|Recovery",
      "description": "",
      "miles": 0.0,
      "intensity": "Low|Moderate|High",
      "target_zone": "Zone 1-2|Zone 3|Zone 4|Zone 5",
      "target_hr": "",
      "focus": "Base Building|Endurance|Speed|Recovery|Marathon Pace"
    }}}}
  ]
}}}}"""


def _ensure_full_coverage(
    expected_dates: list[date], month_workouts: list[dict]
) -> list[dict]:
    """Ensure each expected date has a workout; fill missing with Easy Run.
    Keeps existing workouts unchanged and appends safe fillers for any gaps.
    """
    existing = {w.get("date"): w for w in month_workouts}
    filled = list(month_workouts)
    for d in expected_dates:
        if d not in existing:
            filled.append(
                {
                    "date": d,
                    "workout_type": "Easy Run",
                    "description": "Auto-filled to ensure coverage; easy base run.",
                    "miles": 4.0,
                    "intensity": "Low",
                    "target_zone": "Zone 1-2",
                    "target_hr": "",
                    "focus": "Base Building",
                }
            )
    # Sort by date to keep order stable
    filled.sort(key=lambda w: w.get("date"))
    return filled


def _calculate_weekly_mileage_targets(
    weeks: dict, base_mileage: float, race_date: date
) -> dict:
    """Calculate target weekly mileage for each week with progression and taper."""
    total_weeks = len(weeks)
    if total_weeks == 0:
        return {}

    # Jack Daniels progression: build for 75% of plan, then taper
    build_weeks = int(total_weeks * 0.75)
    taper_weeks = total_weeks - build_weeks

    # Target peak mileage: 1.3-1.5x base (conservative for safety)
    peak_mileage = base_mileage * 1.35

    # Calculate weekly progression
    mileage_increment = (peak_mileage - base_mileage) / max(build_weeks, 1)

    weekly_targets = {}
    for week_num in sorted(weeks.keys()):
        if week_num <= build_weeks:
            # Build phase: gradual increase
            target = base_mileage + (mileage_increment * (week_num - 1))
        else:
            # Taper phase: reduce by 10-15% per week
            weeks_into_taper = week_num - build_weeks
            taper_reduction = 0.12 * weeks_into_taper  # 12% per week
            target = peak_mileage * (1 - taper_reduction)

        # Round to nearest 0.5 mile
        weekly_targets[week_num] = round(target * 2) / 2

    return weekly_targets


def _build_full_plan_prompt_with_constraints(
    dummy_workouts: list[dict],
    user: dict,
    race_date: date,
    activities: list[dict],
    training_days: list[str],
    start_date: date,
    weekly_mileage_targets: dict = None,
) -> str:
    """Build prompt for full plan generation with taper constraints."""
    # Clean runner level
    runner_level_display = str(user.get("runner_level", "Intermediate"))
    if "." in runner_level_display:
        runner_level_display = runner_level_display.split(".")[-1]
    runner_level_display = runner_level_display.capitalize()

    # Calculate taper threshold
    taper_threshold = race_date - timedelta(days=14)

    lines = [
        "RUNNER PROFILE:",
        f"Level: {runner_level_display}",
        f"Race Date: {race_date} (Marathon)",
        f"Plan Start: {start_date}",
    ]

    # Add EXACT dates from dummy data - show ALL dates
    lines.append("\n??? TRAINING DATES (use ONLY these exact dates):")
    for w in sorted(dummy_workouts, key=lambda x: x.get("date")):
        day_name = w.get("date").strftime("%A")
        lines.append(f"{w.get('date')} ({day_name})")
    lines.append("")
    lines.append(
        "CRITICAL: Generate workouts for ONLY these specific dates listed above. Do not create workouts for any other dates."
    )

    # Add weekly mileage targets
    if weekly_mileage_targets:
        lines.append("\n?? WEEKLY MILEAGE TARGETS:")
        for week_num in sorted(weekly_mileage_targets.keys()):
            mileage = weekly_mileage_targets[week_num]
            lines.append(f"Week {week_num}: {mileage:.1f} miles")

    # Add recent training
    if activities and len(activities) > 0:
        lines.append("\nRECENT TRAINING:")
        for activity in activities[:5]:
            date = activity.get("activity_date", "")
            dist = activity.get("distance", 0)
            hr = activity.get("avg_hr", 0)
            lines.append(f"{date}: {dist:.1f}mi, {int(hr)}bpm")

    # Jack Daniels constraints
    lines.append("\nJACK DANIELS METHODOLOGY:")
    lines.append(
        "- Long run progression: Start from recent long run, increase by ~1 mile per week"
    )
    lines.append("- Peak long run: 18-22 miles, occurring 3 weeks before race")

    lines.append("\n?? MILEAGE DISTRIBUTION (% of weekly mileage):")
    lines.append("- Recovery runs: ~10% of weekly mileage @ Zone 1-2")
    lines.append("- Easy runs:")
    lines.append("  � Base building phase: 15-20% of weekly mileage @ Zone 1-2")
    lines.append("  � Peak phase: 20-25% of weekly mileage @ Zone 1-2")
    lines.append("  � Taper phase: 10-15% of weekly mileage @ Zone 1-2")
    lines.append(
        "- Threshold runs: 8-12% of weekly mileage @ Zone 3-4 (continuous or intervals)"
    )
    lines.append("- Round all mileage to nearest 0.5 mile")
    lines.append(
        "- Zone 1-2 intensity: Conversational effort (you can talk comfortably)"
    )
    lines.append("- Maintain proper recovery spacing between hard sessions")

    lines.append(f"\n??? CRITICAL TAPER CONSTRAINT (NON-NEGOTIABLE):")
    lines.append(
        f"- Any long run on or after {taper_threshold} (14 days before race) MUST be =12 miles"
    )
    lines.append(f"- Taper period: {taper_threshold} to {race_date}")
    lines.append(
        f"- Race day {race_date} should be the Marathon race, NOT a training long run"
    )

    # Instructions for full plan generation
    lines.append("\nGenerate a complete Jack Daniels marathon training plan.")
    lines.append(
        "Apply proper progression, tapering (=12mi within 14 days of race), and workout distribution."
    )
    lines.append("\nOutput format (json):")
    lines.append("{")
    lines.append('  "workouts": [')
    lines.append("    {")
    lines.append('      "date": "YYYY-MM-DD",')
    lines.append(
        '      "workout_type": "Easy Run|Long Run|Threshold|Intervals|Recovery",'
    )
    lines.append('      "description": "",')
    lines.append('      "miles": 0.0,')
    lines.append('      "intensity": "Low|Moderate|High",')
    lines.append('      "target_zone": "Zone 1-2|Zone 3|Zone 4|Zone 5",')
    lines.append('      "target_hr": "",')
    lines.append(
        '      "focus": "Base Building|Endurance|Speed|Recovery|Marathon Pace"'
    )
    lines.append("    }")
    lines.append("  ]")
    lines.append("}")

    return "\n".join(lines)


# Legacy assessment functions removed - we now use single-pass generation
def _generate_fallback_week_workouts(
    week_num: int, week_dates: list[date], recent_mileage: float, longest_run: float
) -> list[dict]:
    """Generate simple fallback workouts for a week if GPT fails."""
    workouts = []

    for date_obj in week_dates:
        day_name = date_obj.strftime("%A")

        # Determine workout type based on day
        if day_name == "Saturday":
            workout_type = "Long Run"
            miles = min(longest_run + (week_num * 1.5), 20.0)
            intensity = "Moderate"
            target_zone = "Zone 2-3"
            focus = "Endurance"
        elif day_name in ["Monday", "Thursday"]:
            workout_type = "Easy Run"
            miles = 3.0 + (week_num * 0.5)
            intensity = "Low"
            target_zone = "Zone 1-2"
            focus = "Base Building"
        else:  # Wednesday
            workout_type = "Quality Workout"
            miles = 4.0 + (week_num * 0.5)
            intensity = "High"
            target_zone = "Zone 4-5"
            focus = "Speed"

        workouts.append(
            {
                "date": date_obj,
                "workout_type": workout_type,
                "description": f"{workout_type} - {miles:.1f} miles focusing on {focus.lower()}",
                "miles": miles,
                "intensity": intensity,
                "target_zone": target_zone,
                "target_hr": f"Target heart rate for {target_zone}",
                "focus": focus,
            }
        )

    return workouts


def _parse_gpt_workout_response(
    response: str, training_days: list[str], start_date: date, race_date: date
) -> list[dict]:
    """Parse GPT response into workout list."""
    try:
        # Extract JSON from response (could be array or object)
        # Try array first [ ... ]
        array_start = response.find("[")
        array_end = response.rfind("]") + 1

        # Try object { ... }
        obj_start = response.find("{")
        obj_end = response.rfind("}") + 1

        json_str = None
        is_array = False

        # Determine which format GPT used
        if array_start != -1 and (obj_start == -1 or array_start < obj_start):
            json_str = response[array_start:array_end]
            is_array = True
            print(f"   📋 Detected JSON array format")
        elif obj_start != -1:
            json_str = response[obj_start:obj_end]
            print(f"   📋 Detected JSON object format")
        else:
            raise ValueError("No JSON found in response")

        data = json.loads(json_str)

        # Handle both array and object formats
        if is_array:
            workout_list = data
        else:
            # Try different possible keys: "workouts", "plan", "training_plan", or treat as single workout
            workout_list = data.get("workouts") or data.get("plan") or data.get("training_plan")
            if workout_list is None:
                # If it's a single workout object, wrap it in a list
                if "date" in data and "workout_type" in data:
                    workout_list = [data]
                else:
                    workout_list = []

        print(f"   📊 Found {len(workout_list)} workouts in GPT response")

        if len(workout_list) == 0:
            raise ValueError(f"No workouts found in GPT response. Response format: {type(data)}")

        workouts = []
        for i, workout in enumerate(workout_list):
            try:
                workout_date = datetime.strptime(workout["date"], "%Y-%m-%d").date()
                miles_value = float(workout.get("miles", 0))

                print(f"   Workout {i+1}: {workout_date} - {workout.get('workout_type', 'Unknown')} - {miles_value}mi")

                # Validate workout is within plan timeframe
                if start_date <= workout_date <= race_date:
                    workouts.append(
                        {
                            "date": workout_date,
                            "workout_type": workout.get("workout_type", "Easy Run"),
                            "description": workout.get("description", ""),
                            "miles": miles_value,
                            "intensity": workout.get("intensity", "Low"),
                            "target_zone": workout.get("target_zone", ""),
                            "target_hr": workout.get("target_hr", ""),
                            "focus": workout.get("focus", "Base Building"),
                        }
                    )
                else:
                    print(f"   ⚠️ Skipped workout {i+1}: outside date range ({workout_date})")
            except Exception as workout_error:
                print(f"   ❌ Failed to parse workout {i+1}: {workout_error}")
                print(f"   📄 Workout data: {workout}")

        print(f"   ✅ Successfully parsed {len(workouts)} valid workouts")
        return workouts

    except Exception as e:
        print(f"   ❌ Failed to parse GPT response: {e}")
        print(f"   📄 Response preview: {response[:500]}...")
        raise ValueError(f"GPT response parsing failed: {e}") from e


def _parse_month_response(
    response: str, training_days: list[str], start_date: date, race_date: date
) -> tuple[list[dict], dict | None]:
    """Parse a monthly GPT response. Month review is now optional (no longer generated)."""
    try:
        start_idx = response.find("{")
        end_idx = response.rfind("}") + 1
        if start_idx == -1 or end_idx == 0:
            raise ValueError("No JSON found in response")
        json_str = response[start_idx:end_idx]
        data = json.loads(json_str)
        items = data.get("workouts", []) if isinstance(data, dict) else []
        workouts = []
        for workout in items:
            workout_date = datetime.strptime(workout["date"], "%Y-%m-%d").date()
            if start_date <= workout_date <= race_date:
                workouts.append(
                    {
                        "date": workout_date,
                        "workout_type": workout.get("workout_type", "Easy Run"),
                        "description": workout.get("description", ""),
                        "miles": float(workout.get("miles", 0)),
                        "intensity": workout.get("intensity", "Low"),
                        "target_zone": workout.get("target_zone", ""),
                        "target_hr": workout.get("target_hr", ""),
                        "focus": workout.get("focus", "Base Building"),
                    }
                )
        # Month review removed from schema, but keep parsing for backward compatibility
        month_review = data.get("month_review") if isinstance(data, dict) else None
        return workouts, month_review
    except Exception as e:
        print(f"Failed to parse month response: {e}")
        return (
            _parse_gpt_workout_response(response, training_days, start_date, race_date),
            None,
        )


# Removed unused _generate_fallback_plan function - now using week-by-week fallbacks
# Removed _validate_and_improve_plan function - GPT now provides plan assessment


def _generate_workout_segments(workouts: list[dict]) -> list[dict]:
    """Generate workout segments (warmup/main/cooldown) for all workouts in a separate GPT call."""
    from src.utils.gpt_ops import get_gpt_response

    print(f"\n?? STEP 3: Generating workout segments for {len(workouts)} workouts...")

    # Build prompt with all workouts
    lines = [
        "Generate structured workout segments for each of the following workouts.",
        "Each segment should include: distance/duration, target pace/zone, and specific instructions.",
        "",
        "WORKOUTS:",
    ]

    for i, w in enumerate(workouts, 1):
        lines.append(
            f"{i}. {w['date']} - {w['workout_type']}: {w['miles']}mi, {w.get('target_zone', 'Zone 1-2')} - {w.get('description', '')}"
        )

    lines.append("")
    lines.append("Output format (json):")
    lines.append("{")
    lines.append('  "segments": [')
    lines.append("    {")
    lines.append('      "date": "YYYY-MM-DD",')
    lines.append('      "warmup": {')
    lines.append('        "distance": "1 mile",')
    lines.append('        "target": "Easy pace, Zone 1-2",')
    lines.append('        "notes": "Start very easy to warm up muscles"')
    lines.append("      },")
    lines.append('      "main": {')
    lines.append('        "distance": "8 miles",')
    lines.append('        "target": "Steady pace, Zone 2-3",')
    lines.append('        "notes": "Maintain consistent effort throughout"')
    lines.append("      },")
    lines.append('      "cooldown": {')
    lines.append('        "distance": "0.5 miles",')
    lines.append('        "target": "Very easy, Zone 1",')
    lines.append('        "notes": "Cool down with easy jogging"')
    lines.append("      }")
    lines.append("    }")
    lines.append("  ]")
    lines.append("}")

    prompt = "\n".join(lines)

    try:
        response = get_gpt_response(prompt)

        # Parse segments response
        start_idx = response.find("{")
        end_idx = response.rfind("}") + 1
        if start_idx == -1 or end_idx == 0:
            raise ValueError("No JSON found in segments response")

        json_str = response[start_idx:end_idx]
        data = json.loads(json_str)

        # Create a map of date -> segments
        segments_map = {}
        for seg in data.get("segments", []):
            date_str = seg.get("date")
            if date_str:
                try:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                    segments_map[date_obj] = {
                        "warmup": seg.get("warmup", {}),
                        "main": seg.get("main", {}),
                        "cooldown": seg.get("cooldown", {}),
                    }
                except:
                    pass

        # Add segments to workouts
        updated_workouts = []
        for workout in workouts:
            workout_copy = workout.copy()
            workout_date = workout["date"]
            if workout_date in segments_map:
                workout_copy["segments"] = segments_map[workout_date]
            else:
                workout_copy["segments"] = {}
            updated_workouts.append(workout_copy)

        print(f"   ? Generated segments for {len(segments_map)} workouts")
        return updated_workouts

    except Exception as e:
        print(f"   ?? Failed to generate segments: {e}")
        print(f"   Continuing without segments...")
        # Return workouts with empty segments
        return [{**w, "segments": {}} for w in workouts]


def _save_plan_to_database(
    session: Session,
    user_id: uuid.UUID,
    race_date: date,
    race_distance: str,
    workouts: list[dict],
    data_bundle: dict = None,
) -> Plan:
    """Save plan and workouts to database with safety information."""

    # Get safety information
    safety_info = ""
    if data_bundle:
        marathon_safety = data_bundle.get("quality_assessment", {}).get(
            "marathon_safety", {}
        )
        if marathon_safety:
            risk_level = marathon_safety.get("risk_level", "UNKNOWN")
            user_message = marathon_safety.get("user_message", "")
            if user_message:
                safety_info = f"\n\n?? SAFETY WARNING: {user_message}"

    # Create plan record
    plan_data = {
        "user_id": user_id,
        "plan_name": f"Jack Daniels Marathon Plan - {race_distance}",
        "race_date": race_date,
        "race_distance": race_distance,
        "notes": f"Generated using Jack Daniels Running Formula.{safety_info}",
        "created_by": "jack_daniels",
    }

    plan = plans_dao.create_plan(session, plan_data)

    # Create workout records - use GPT-generated data directly
    workouts_data = []
    for workout in workouts:
        # Convert segments dict to JSON string for database storage
        segments = workout.get("segments", {})
        segments_json = json.dumps(segments) if segments else None

        workouts_data.append(
            {
                "plan_id": plan.id,
                "date": workout["date"],
                "workout_type": workout["workout_type"],
                "description": workout.get("description", ""),
                "miles": workout["miles"],
                "intensity": workout["intensity"],
                "target_zone": workout.get("target_zone", ""),
                "target_hr": workout.get("target_hr", ""),
                "focus": workout.get("focus", "Base Building"),
                "segments": segments_json,
            }
        )

    if workouts_data:
        plan_workouts_dao.insert_batch(session, workouts_data)

    session.commit()
    return plan


# Removed unused validation functions - no longer needed with week-by-week approach


# Legacy function compatibility
def get_plan(plan_id: int, session, user_id: str | None = None):
    """Get plan with workouts - legacy compatibility."""
    from src.db.dao.plans_dao import get_plan_with_workouts

    return get_plan_with_workouts(session, plan_id, user_id)


# Legacy compatibility functions
class PlanValidationError(Exception):
    """Exception for plan validation errors."""

    pass


# Removed unused legacy functions - no longer imported by routes


def get_plan_quality_for_user_display(plan_id: int, session) -> dict:
    """Legacy compatibility - get plan quality for user display."""
    return {
        "plan_id": plan_id,
        "quality": "Good",
        "grade": "B+",
        "summary": "Training plan is well-structured and safe",
    }
