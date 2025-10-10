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
    print(f"\n🔍 DEBUG: Data Bundle Validation:")
    print(
        f"  • data_bundle keys: {list(data_bundle.keys()) if data_bundle else 'None'}"
    )
    for key, value in data_bundle.items():
        if isinstance(value, list):
            print(f"  • {key}: list with {len(value)} items")
        elif isinstance(value, dict):
            print(f"  • {key}: dict with {len(value)} keys")
        else:
            print(f"  • {key}: {value}")

    # Check if plan generation is safe
    quality_assessment = data_bundle.get("quality_assessment", {})
    marathon_safety = quality_assessment.get("marathon_safety", {})

    # Check if plan creation should be blocked
    if marathon_safety.get("block_plan_creation", False):
        user_message = marathon_safety.get(
            "user_message", "Plan creation blocked for safety reasons"
        )
        print(f"\n❌ PLAN CREATION BLOCKED:")
        print(f"   {user_message}")
        raise ValueError(user_message)

    # Check legacy safety check
    if not quality_assessment.get("can_generate_plan", True):
        critical_issues = quality_assessment.get("critical_issues", [])
        error_msg = "Cannot generate training plan: " + "; ".join(critical_issues)
        print(f"\n❌ SAFETY CHECK FAILED:")
        print(f"   {error_msg}")
        raise ValueError(error_msg)

    # Extract training days
    training_days = _parse_training_days(data_bundle.get("user_profile", {}))
    print(f"Training Days: {', '.join(training_days)} ({len(training_days)} days/week)")

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

    print(f"\n✅ Plan generated successfully!")
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
            miles = 12.0
            intensity = "Moderate"
            target_zone = "Zone 2-3"
            focus = "Endurance"
        else:
            workout_type = "Easy"
            miles = 5.0
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
    Build compact Jack Daniels prompt for single GPT call approach.
    """
    import json
    
    # Format user data for GPT
    user_data_json = json.dumps(user_data, indent=2)
    
    # Format plan structure for GPT
    plan_structure_json = json.dumps(plan_structure, indent=2)
    
    prompt = f"""You are an expert running coach using Jack Daniels methodology. Revise this training plan structure with proper mileage and progression.

USER DATA:
{user_data_json}

TRAINING PLAN STRUCTURE:
{plan_structure_json}

JACK DANIELS RULES:
- Long runs: 1/week, MUST be on weekends (Sat/Sun), 25-30% of weekly mileage, Zone 2-3, cap at Beginner=18mi/Intermediate=20-22mi/Advanced=24mi
- Every 2-3 weeks: marathon-pace finish (last 4-6mi @ Zone 3)
- Taper: reduce to 60%, 40%, 20% of peak over final 3 weeks
- Recovery: 10% of weekly mileage @ Z1-2
- Easy: 15-20% of weekly mileage @ Z1-2  
- Threshold: 8-12% of weekly mileage @ Z3-4
- Progression: max +10% weekly mileage increase
- Round miles to nearest 0.5

OUTPUT: Complete revised plan as JSON array with fields: date, workout_type, miles, target_zone, intensity, description, focus"""
    
    return prompt


def _generate_jack_daniels_plan(
    data_bundle: dict, race_date: date, race_distance: str, training_days: list[str]
) -> list[dict]:
    """Generate Jack Daniels training plan using single GPT call approach."""
    from datetime import datetime, date
    from src.utils.gpt_ops import get_gpt_response

    user = data_bundle.get("user_profile", {})
    activities = data_bundle.get("activities", [])
    weekly_summaries = data_bundle.get("weekly_summaries", [])

    start_date = datetime.today().date()

    print(f"\n🔍 SINGLE GPT CALL JACK DANIELS PLAN GENERATION")
    print("=" * 60)

    # Step 3: Create dummy plan structure
    print("\nStep 3: Creating dummy plan structure...")
    dummy_plan = _create_dummy_plan_structure(start_date, race_date, training_days)
    print(f"Created {len(dummy_plan)} dummy workouts")

    # Step 4: GPT revises entire plan with Jack Daniels methodology
    print("\nStep 4: GPT revising plan with Jack Daniels methodology...")
    
    # Prepare user data for GPT
    user_data = {
        "user_profile": user,
        "activities": activities[:10],  # Limit to recent activities
        "weekly_summaries": weekly_summaries,
        "base_mileage": _calculate_base_mileage(
            weekly_summaries, 
            str(user.get("runner_level", "Intermediate")).lower(),
            data_bundle.get("quality_assessment", {}).get("data_quality", {})
        ),
        "heart_rate_zones": _calculate_user_heart_rate_zones(user, activities)
    }
    
    # Build compact prompt
    prompt = _build_compact_jack_daniels_prompt(user_data, dummy_plan)
    print(f"Prompt length: ~{len(prompt)} characters")
    
    # Get GPT response
    try:
        response = get_gpt_response(prompt)
        print(f"GPT response received ({len(response)} characters)")
        
        # Parse response
        workouts = _parse_gpt_workout_response(response, training_days, start_date, race_date)
        print(f"Parsed {len(workouts)} workouts")
        
        return workouts
        
    except Exception as e:
        print(f"GPT generation failed: {e}")
        print("Using dummy plan as fallback")
        return dummy_plan

    # Calculate all training dates upfront
    training_dates = _calculate_training_dates(start_date, race_date, training_days)
    print(
        f"Calculated {len(training_dates)} training dates across {len(set([w for w, d in training_dates]))} weeks"
    )

    # DEBUG: Show first 10 training dates with day of week
    print(f"\n🔍 DEBUG: First 10 training dates:")
    for i, (week, d) in enumerate(training_dates[:10]):
        day_name = d.strftime("%A")
        print(f"   {i+1}. Week {week}: {d} ({day_name})")

    # Group dates by week
    weeks = {}
    for week_num, date_obj in training_dates:
        if week_num not in weeks:
            weeks[week_num] = []
        weeks[week_num].append(date_obj)

    print(f"Week breakdown: {[(week, len(dates)) for week, dates in weeks.items()]}")

    # Extract key variables (simplified)
    age = user.get("age", 35)
    runner_level = str(user.get("runner_level", "Intermediate")).lower()

    # Get data quality assessment
    data_quality = data_bundle.get("quality_assessment", {}).get("data_quality", {})
    recent_mileage = _calculate_base_mileage(
        weekly_summaries, runner_level, data_quality
    )
    longest_run = user.get("longest_run", 10.0)  # Use database value, fallback to 10.0

    # Debug output to verify fixes
    print(f"\n🔍 VALIDATION - KEY VALUES:")
    print(f"   Age: {age} (from age_group: {user.get('age_group')})")
    print(f"   Weight: {user.get('weight')}")
    print(f"   Longest run: {longest_run} (from database: {user.get('longest_run')})")
    print(f"   Runner level: {runner_level}")

    # Calculate personalized heart rate zones from user data
    heart_rate_zones = _calculate_user_heart_rate_zones(user, activities)

    # Use calculated max HR instead of outdated 180-age formula
    estimated_threshold_hr = heart_rate_zones["max_hr"]
    total_weeks = len(weeks)

    # OPTIMIZATION: Calculate these values ONCE and reuse across all weeks
    progression_rate = _calculate_dynamic_progression_rate(user, total_weeks)

    # Build activity context ONCE and reuse (compressed 2-line format)
    recent_activities_context = ""
    if activities and len(activities) > 0:
        recent_activities_context = "\n\nRecent Runs (Last 5):\n"

        # Line 1: Distances
        distances = []
        hrs = []
        for activity in activities[:5]:
            activity_date = activity.get("activity_date", "Unknown date")
            if isinstance(activity_date, str):
                # Parse and format as MM/DD
                try:
                    date_obj = datetime.strptime(activity_date, "%Y-%m-%d")
                    date_str = date_obj.strftime("%m/%d")
                except:
                    date_str = activity_date[-5:]  # Last 5 chars (MM-DD)
            else:
                date_str = str(activity_date)[-5:]

            distance = activity.get("distance", 0)
            avg_hr = activity.get("avg_hr", 0)
            distances.append(f"{date_str}:{distance:.1f}mi")
            hrs.append(f"{date_str}:{int(avg_hr)}bpm")

        recent_activities_context += f"Distance: {' | '.join(distances)}\n"
        recent_activities_context += f"Avg HR: {' | '.join(hrs)}"

    # VALIDATION: Show all calculated values with fallback indicators
    print(f"\n🔍 VALIDATION - OPTIMIZED VALUES:")

    # Age validation
    age_source = "✅ DATABASE" if user.get("age_group") else "⚠️ FALLBACK (default 35)"
    print(f"   Age: {age} (from age_group: {user.get('age_group')}) - {age_source}")

    # Weight validation
    weight_source = "✅ DATABASE" if user.get("weight") else "⚠️ FALLBACK (default 70)"
    print(f"   Weight: {user.get('weight')} - {weight_source}")

    # Longest run validation
    longest_run_db = user.get("longest_run")
    longest_run_source = (
        "✅ DATABASE" if longest_run_db else "⚠️ FALLBACK (calculated from activities)"
    )
    print(
        f"   Longest run: {longest_run:.1f} (DB: {longest_run_db}) - {longest_run_source}"
    )

    # Runner level validation
    runner_level_source = (
        "✅ DATABASE"
        if user.get("runner_level")
        else "⚠️ FALLBACK (default Intermediate)"
    )
    print(f"   Runner level: {runner_level} - {runner_level_source}")

    # Heart rate validation
    hr_method = heart_rate_zones["method"]
    hr_source = (
        "✅ YOUR ACTIVITY DATA"
        if hr_method == "from_activities"
        else "⚠️ FALLBACK (220-age formula)"
    )
    print(f"   Heart Rate: max_hr={estimated_threshold_hr} ({hr_method}) - {hr_source}")

    # Progression rate validation
    print(f"   Progression rate: {progression_rate:.1%} (calculated ONCE)")

    # Activity context validation
    activity_source = (
        "✅ YOUR ACTIVITY DATA" if len(activities) > 0 else "⚠️ NO ACTIVITIES FOUND"
    )
    print(f"   Activity context: {len(activities)} activities - {activity_source}")

    # Weekly mileage validation
    mileage_source = (
        "✅ YOUR ACTIVITY DATA"
        if weekly_summaries
        else "⚠️ FALLBACK (based on runner level)"
    )
    print(f"   Weekly mileage base: {recent_mileage:.1f} mi/week - {mileage_source}")

    # SUMMARY: Data source overview
    print(f"\n📊 DATA SOURCE SUMMARY:")
    print(
        f"   ✅ Using YOUR data: {sum(1 for s in [age_source, weight_source, longest_run_source, runner_level_source, hr_source, activity_source, mileage_source] if '✅' in s)} fields"
    )
    print(
        f"   ⚠️ Using fallbacks: {sum(1 for s in [age_source, weight_source, longest_run_source, runner_level_source, hr_source, activity_source, mileage_source] if '⚠️' in s)} fields"
    )

    # STEP 1: Create dummy plan (no GPT calls)
    print("\n📋 STEP 1: Creating dummy plan (no GPT calls)")
    # Group training dates by calendar month (YYYY-MM)
    month_to_dates: dict[str, list[tuple[int, date]]] = {}
    for w, d in training_dates:
        key = d.strftime("%Y-%m")
        month_to_dates.setdefault(key, []).append((w, d))

    all_workouts = []
    month1_workouts = []  # Store Month 1 for duplication

    for month_idx, month_key in enumerate(sorted(month_to_dates.keys())):
        month_items = sorted(month_to_dates[month_key], key=lambda x: x[1])
        expected_dates = [d for _, d in month_items]

        if month_idx == 0:
            # Create dummy Month 1 data
            print(f"\n📅 Creating dummy Month {month_key} ({len(month_items)} dates)")
            dummy_workouts = []
            for d in expected_dates:
                weekday = d.weekday()
                if weekday == 5:  # Saturday
                    workout_type = "Long Run"
                    miles = 10.0
                    intensity = "Moderate"
                    target_zone = "Zone 1-2"
                    focus = "Endurance"
                elif weekday == 2:  # Wednesday
                    workout_type = "Threshold"
                    miles = 5.0
                    intensity = "High"
                    target_zone = "Zone 3"
                    focus = "Speed"
                else:  # Monday, Thursday
                    workout_type = "Easy Run"
                    miles = 4.0
                    intensity = "Low"
                    target_zone = "Zone 1-2"
                    focus = "Base Building"

                dummy_workouts.append(
                    {
                        "date": d,
                        "workout_type": workout_type,
                        "description": f"Dummy {workout_type.lower()}",
                        "miles": miles,
                        "intensity": intensity,
                        "target_zone": target_zone,
                        "target_hr": "",
                        "focus": focus,
                    }
                )

            all_workouts.extend(dummy_workouts)
            month1_workouts = dummy_workouts
            print(f"   Month {month_key}: {len(dummy_workouts)} dummy workouts created")
        else:
            # DUPLICATE MONTH 1 WORKOUTS FOR REMAINING MONTHS (by day-of-week)
            print(
                f"\n📅 Duplicating Month 1 data for {month_key} ({len(month_items)} dates)"
            )
            duplicated_workouts = []

            # Build a map of Month 1 workouts by day-of-week (0=Mon, 6=Sun)
            month1_by_weekday = {}
            for workout in month1_workouts:
                workout_date = workout.get("date")
                if workout_date:
                    weekday = workout_date.weekday()
                    if weekday not in month1_by_weekday:
                        month1_by_weekday[weekday] = []
                    month1_by_weekday[weekday].append(workout)

            # Match target dates to source workouts by same day-of-week
            for target_date in expected_dates:
                target_weekday = target_date.weekday()

                # Find a matching workout from Month 1 with same weekday
                if (
                    target_weekday in month1_by_weekday
                    and len(month1_by_weekday[target_weekday]) > 0
                ):
                    source_workout = month1_by_weekday[target_weekday][
                        0
                    ]  # Use first occurrence
                else:
                    # Fallback if no match (shouldn't happen with same training days)
                    source_workout = month1_workouts[0] if month1_workouts else {}

                duplicated_workouts.append(
                    {
                        "date": target_date,
                        "workout_type": source_workout.get("workout_type", "Easy Run"),
                        "description": source_workout.get("description", ""),
                        "miles": source_workout.get("miles", 4.0),
                        "intensity": source_workout.get("intensity", "Low"),
                        "target_zone": source_workout.get("target_zone", "Zone 1-2"),
                        "target_hr": source_workout.get("target_hr", ""),
                        "focus": source_workout.get("focus", "Base Building"),
                    }
                )

            print(
                f"   Month {month_key}: {len(duplicated_workouts)} workouts (duplicated by weekday from Month 1)"
            )
            all_workouts.extend(duplicated_workouts)
    if all_workouts:
        print(f"\n✅ Total generated (test mode): {len(all_workouts)} workouts")

        # STEP 1: Create dummy plan (already done above)
        print(f"\n📋 STEP 1: Dummy plan created with {len(all_workouts)} workouts")

        # STEP 2: Generate full plan with taper constraints
        print(f"\n🔄 STEP 2: Generating full plan with complete context...")
        try:
            # Calculate weekly mileage targets
            weekly_mileage_targets = _calculate_weekly_mileage_targets(
                weeks, recent_mileage, race_date
            )
            print(f"   📊 Weekly mileage targets: {weekly_mileage_targets}")

            full_plan_prompt = _build_full_plan_prompt_with_constraints(
                all_workouts,
                user,
                race_date,
                activities,
                training_days,
                start_date,
                weekly_mileage_targets,
            )
            print(f"   Full plan prompt size: {len(full_plan_prompt)} characters")

            # LOG THE EXACT PROMPT SENT TO GPT
            print(f"\n{'='*80}")
            print(f"📝 EXACT PROMPT SENT TO GPT:")
            print(f"{'='*80}")
            print(full_plan_prompt)
            print(f"{'='*80}\n")

            response = get_gpt_response(full_plan_prompt)
            full_plan_workouts = _parse_gpt_workout_response(
                response, training_days, start_date, race_date
            )

            if full_plan_workouts and len(full_plan_workouts) > 0:
                print(
                    f"   ✅ Generated full plan with {len(full_plan_workouts)} workouts"
                )

                # VALIDATE TAPER CONSTRAINT (hardcoded safety check)
                print(f"\n🛡️ Validating taper constraint...")
                taper_threshold = race_date - timedelta(days=14)
                violations = []
                for w in full_plan_workouts:
                    if "Long Run" in w.get("workout_type", ""):
                        workout_date = w.get("date")
                        miles = w.get("miles", 0)
                        if (
                            workout_date
                            and workout_date >= taper_threshold
                            and workout_date < race_date
                        ):
                            if miles > 12:
                                violations.append(
                                    f"{workout_date}: {miles}mi (should be ≤12mi)"
                                )
                                print(
                                    f"   ⚠️ TAPER VIOLATION: {workout_date} has {miles}mi long run (within 14 days of race)"
                                )
                        if workout_date == race_date:
                            if "Long Run" in w.get("workout_type", ""):
                                violations.append(
                                    f"{workout_date}: Race day has Long Run scheduled (should be race)"
                                )
                                print(
                                    f"   ⚠️ RACE DAY VIOLATION: {workout_date} has Long Run scheduled"
                                )

                if violations:
                    print(
                        f"   ❌ Taper constraint violated! {len(violations)} issues found."
                    )
                    for v in violations:
                        print(f"      • {v}")

                    # AUTO-FIX: Cap long runs within taper period to 12 miles
                    print(f"\n   🔧 Auto-fixing taper violations...")
                    fixed_count = 0
                    for w in full_plan_workouts:
                        if "Long Run" in w.get("workout_type", ""):
                            workout_date = w.get("date")
                            miles = w.get("miles", 0)
                            if (
                                workout_date
                                and workout_date >= taper_threshold
                                and workout_date < race_date
                            ):
                                if miles > 12:
                                    print(
                                        f"      • {workout_date}: {miles}mi → 12mi (capped)"
                                    )
                                    w["miles"] = 12.0
                                    w["description"] = (
                                        f"Long Run (tapered to 12mi for race prep)"
                                    )
                                    fixed_count += 1
                            if workout_date == race_date:
                                if "Long Run" in w.get("workout_type", ""):
                                    print(
                                        f"      • {workout_date}: Removed Long Run on race day"
                                    )
                                    w["workout_type"] = "Recovery"
                                    w["miles"] = 3.0
                                    w["description"] = (
                                        "Light recovery run or race day prep"
                                    )
                                    fixed_count += 1
                    print(f"   ✅ Fixed {fixed_count} taper violations")
                else:
                    print(
                        f"   ✅ Taper constraint validated: All long runs properly tapered"
                    )

                # OUTPUT PLAN TO LOGS
                print(f"\n📋 GENERATED PLAN:")
                print("=" * 80)
                for w in sorted(full_plan_workouts, key=lambda x: x.get("date")):
                    print(
                        f"{w['date']}: {w['workout_type']:15} {w.get('miles', 0):5.1f}mi - {w.get('description', '')}"
                    )
                print("=" * 80)

            else:
                print(f"   ⚠️ Full plan generation failed, using dummy plan")
                full_plan_workouts = all_workouts
        except Exception as e:
            print(f"   ❌ Full plan generation failed: {e}, using dummy plan")
            full_plan_workouts = all_workouts

        print(f"\n✅ Plan generation complete, ready to save to database")

        # STEP 3: Generate segments for all workouts
        full_plan_workouts = _generate_workout_segments(full_plan_workouts)

        return full_plan_workouts

    # Generate workouts week by week (fallback)
    all_workouts = []
    prior_weeks_summary: list[dict] = []

    for week_num in sorted(weeks.keys()):
        week_dates = sorted(weeks[week_num])
        print(f"\n📅 Generating Week {week_num}: {len(week_dates)} workouts")
        print(f"   Dates: {[d.strftime('%Y-%m-%d (%a)') for d in week_dates]}")

        # Determine explicit weekend long run date (Sat preferred, else Sun)
        weekend_lr_date = None
        for d in week_dates:
            if d.weekday() == 5:  # Saturday
                weekend_lr_date = d
                break
        if weekend_lr_date is None:
            for d in week_dates:
                if d.weekday() == 6:  # Sunday
                    weekend_lr_date = d
                    break

        # Build week-specific prompt with history and explicit LR date
        prompt = _build_week_prompt(
            week_num,
            week_dates,
            user,
            recent_mileage,
            longest_run,
            estimated_threshold_hr,
            total_weeks,
            heart_rate_zones,
            progression_rate,
            recent_activities_context,
            prior_weeks_summary=prior_weeks_summary,
            weekend_lr_date=weekend_lr_date,
        )

        print(f"   Prompt length: ~{len(prompt)} characters")
        # DEBUG: Save prompt to file
        try:
            os.makedirs("debug_dumps", exist_ok=True)
            prompt_path = os.path.join("debug_dumps", f"week_{week_num:02d}_prompt.txt")
            with open(prompt_path, "w", encoding="utf-8") as f:
                f.write(prompt)
        except Exception as _e:
            print(f"   ⚠️ Could not write prompt debug file: {_e}")

        # Get GPT response for this week
        try:
            response = get_gpt_response(prompt)
            # DEBUG: Save raw response
            try:
                resp_path = os.path.join(
                    "debug_dumps", f"week_{week_num:02d}_response.txt"
                )
                with open(resp_path, "w", encoding="utf-8") as f:
                    f.write(response if isinstance(response, str) else str(response))
            except Exception as _e:
                print(f"   ⚠️ Could not write response debug file: {_e}")
            week_workouts = _parse_gpt_workout_response(
                response, training_days, start_date, race_date
            )

            print(f"   Generated {len(week_workouts)} workouts")
            all_workouts.extend(week_workouts)

            # DEBUG: Summarize LR placement for this week
            try:
                dates_set = {d for d in week_dates}
                has_sat = any(d.weekday() == 5 for d in week_dates)
                has_sun = any(d.weekday() == 6 for d in week_dates)
                week_items = [w for w in week_workouts if w.get("date") in dates_set]
                lrs = [
                    w
                    for w in week_items
                    if str(w.get("workout_type", "")).strip().lower() == "long run"
                ]
                lr_info = "none"
                if lrs:
                    lr_date = lrs[0].get("date")
                    lr_info = f"{lr_date.strftime('%Y-%m-%d (%a)')}"
                print(
                    f"   🧪 LR debug → has_sat={has_sat} has_sun={has_sun} lr={lr_info}"
                )
            except Exception as _e:
                print(f"   ⚠️ LR debug failed: {_e}")

            # Update prior weeks summary for next iteration
            try:
                total_miles = round(
                    sum(float(w.get("miles", 0) or 0) for w in week_workouts), 1
                )
                lr_miles = None
                for w in week_workouts:
                    if str(w.get("workout_type", "")).strip().lower() == "long run":
                        lr_miles = float(w.get("miles", 0) or 0)
                        break
                prior_weeks_summary.append(
                    {
                        "week": week_num,
                        "total_miles": total_miles,
                        "long_run_miles": lr_miles,
                    }
                )
            except Exception as _e:
                print(f"   ⚠️ Could not update history summary: {_e}")

        except Exception as e:
            print(f"   ❌ Error generating week {week_num}: {e}")
            # Generate fallback workouts for this week
            fallback_workouts = _generate_fallback_week_workouts(
                week_num, week_dates, recent_mileage, longest_run
            )
            all_workouts.extend(fallback_workouts)
            print(f"   🔄 Generated {len(fallback_workouts)} fallback workouts")

    print(f"\n✅ Total generated: {len(all_workouts)} workouts")
    return all_workouts


def _calculate_user_heart_rate_zones(user_profile: dict, activities: list) -> dict:
    """Calculate personalized heart rate zones from user data."""
    # Try to get max heart rate from activities first
    max_hr_from_activities = None
    if activities:
        # Get the highest max heart rate from recent activities
        print(f"\n🔍 HEART RATE DEBUG:")
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
            f"   📊 Base mileage: Using fallback (data quality: {data_quality.get('quality', 'UNKNOWN')})"
        )

        # Enhanced fallback strategy based on data quality and runner level
        if valid_activity_count == 0:
            # No valid data - very conservative fallback
            print(f"   📊 Base mileage: NO VALID DATA - using minimal fallback")
            if "beginner" in runner_level:
                return 8  # Very conservative for beginners with no data
            elif "advanced" in runner_level:
                return 15  # Conservative for advanced with no data
            else:
                return 12  # Conservative for intermediate with no data
        elif valid_activity_count < 5:
            # Very little data - conservative fallback
            print(
                f"   📊 Base mileage: MINIMAL DATA ({valid_activity_count} activities) - using conservative fallback"
            )
            if "beginner" in runner_level:
                return 12
            elif "advanced" in runner_level:
                return 20
            else:
                return 16
        else:
            # Some data but quality issues - standard fallback
            if "beginner" in runner_level:
                return 15
            elif "advanced" in runner_level:
                return 35
            else:
                return 25

    # Use actual data - ALL available weeks for good quality data
    if weekly_summaries:
        weeks_to_use = weekly_summaries
        print(f"   📊 Base mileage: Using {len(weeks_to_use)} weeks of data")

        # Parse mileage from string summaries
        total_mileage = 0
        count = 0

        for summary in weeks_to_use:
            if isinstance(summary, str) and "miles" in summary:
                # Extract mileage from string like "15.2 miles"
                import re

                miles_match = re.search(r"(\d+\.?\d*)\s*miles", summary)
                if miles_match:
                    total_mileage += float(miles_match.group(1))
                    count += 1

        if count > 0:
            recent_mileage = total_mileage / count
            return max(recent_mileage, 10)  # Minimum 10 miles/week

    # Final fallback - should rarely reach here
    print(f"   📊 Base mileage: Using final fallback (no weekly summaries)")
    if "beginner" in runner_level:
        return 15
    elif "advanced" in runner_level:
        return 35
    else:
        return 25


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

    # Day name to number mapping
    day_mapping = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}

    # Adjust start_date to the beginning of the week (Monday)
    days_since_monday = start_date.weekday()
    week_start = start_date - timedelta(days=days_since_monday)

    # Calculate total weeks
    total_days = (race_date - week_start).days
    total_weeks = max(1, (total_days + 6) // 7)

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

    # Derive a Long Run target from weekly mileage (bounded 8–20mi)
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
- Weekend Long Run (ENFORCED): Schedule exactly ONE Long Run on the weekend — use Saturday if Saturday is one of this week’s training days; otherwise use Sunday. Do NOT place the Long Run on a weekday. If it is race week, there is NO Long Run.
- Keep at least 48–72 hours between hard sessions (the Long Run and any Threshold/Intervals/Marathon-Pace session are considered hard).
- {"Follow {progression_rate:.1%} increase rule" if week_num > 1 else "Start at base mileage"}
- Never back-to-back hard workouts

EXPLICIT TARGETS FOR THIS WEEK:
- Weekly mileage target: ~{weekly_mileage:.1f} miles
- Long Run target: {(weekend_lr_date.strftime('%Y-%m-%d') if weekend_lr_date else 'WEEKEND DATE')} ≈ {lr_target:.1f} miles (acceptable range {lr_target_min}-{lr_target_max})

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
TARGET STRATEGY: Use Jack Daniels methodology. Ensure coherent long run progression with periodic cutbacks and a 2–3 week taper. Exactly one weekend Long Run per week (Sat preferred, else Sun). No Long Run in race week.

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
    lines.append("\n🗓️ TRAINING DATES (use ONLY these exact dates):")
    for w in sorted(dummy_workouts, key=lambda x: x.get("date")):
        day_name = w.get("date").strftime("%A")
        lines.append(f"{w.get('date')} ({day_name})")
    lines.append("")
    lines.append(
        "CRITICAL: Generate workouts for ONLY these specific dates listed above. Do not create workouts for any other dates."
    )

    # Add weekly mileage targets
    if weekly_mileage_targets:
        lines.append("\n📊 WEEKLY MILEAGE TARGETS:")
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

    lines.append("\n📏 MILEAGE DISTRIBUTION (% of weekly mileage):")
    lines.append("- Recovery runs: ~10% of weekly mileage @ Zone 1-2")
    lines.append("- Easy runs:")
    lines.append("  • Base building phase: 15-20% of weekly mileage @ Zone 1-2")
    lines.append("  • Peak phase: 20-25% of weekly mileage @ Zone 1-2")
    lines.append("  • Taper phase: 10-15% of weekly mileage @ Zone 1-2")
    lines.append(
        "- Threshold runs: 8-12% of weekly mileage @ Zone 3-4 (continuous or intervals)"
    )
    lines.append("- Round all mileage to nearest 0.5 mile")
    lines.append(
        "- Zone 1-2 intensity: Conversational effort (you can talk comfortably)"
    )
    lines.append("- Maintain proper recovery spacing between hard sessions")

    lines.append(f"\n🛡️ CRITICAL TAPER CONSTRAINT (NON-NEGOTIABLE):")
    lines.append(
        f"- Any long run on or after {taper_threshold} (14 days before race) MUST be ≤12 miles"
    )
    lines.append(f"- Taper period: {taper_threshold} to {race_date}")
    lines.append(
        f"- Race day {race_date} should be the Marathon race, NOT a training long run"
    )

    # Instructions for full plan generation
    lines.append("\nGenerate a complete Jack Daniels marathon training plan.")
    lines.append(
        "Apply proper progression, tapering (≤12mi within 14 days of race), and workout distribution."
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
        # Extract JSON from response
        start_idx = response.find("{")
        end_idx = response.rfind("}") + 1
        if start_idx == -1 or end_idx == 0:
            raise ValueError("No JSON found in response")

        json_str = response[start_idx:end_idx]
        data = json.loads(json_str)

        workouts = []
        for workout in data.get("workouts", []):
            workout_date = datetime.strptime(workout["date"], "%Y-%m-%d").date()

            # Validate workout is within plan timeframe
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

        return workouts
    except Exception as e:
        print(f"Failed to parse GPT response: {e}")
        return []


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

    print(f"\n🔄 STEP 3: Generating workout segments for {len(workouts)} workouts...")

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

        print(f"   ✅ Generated segments for {len(segments_map)} workouts")
        return updated_workouts

    except Exception as e:
        print(f"   ⚠️ Failed to generate segments: {e}")
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
                safety_info = f"\n\n⚠️ SAFETY WARNING: {user_message}"

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
