# @file training_plan_data_assembler.py
# @component TrainingSummaryBuilder
# @description Loads recent activity data from DB views and structures for GPT prompts.
# @features Loads activities, optionally with splits
# @integration-points SQLAlchemy, Postgres views
# @usage Called by training_plan_service to build summary JSON
# @prerequisites Views v_activities_running_plan and v_splits_running_plan must exist

from sqlalchemy import text
from sqlalchemy.orm import Session
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean
from typing import Optional
from src.db.models.user_profile import UserProfile


def assess_data_quality(activities: list[dict]) -> dict:
    """Assess data quality and filter activities at granular level."""

    if not activities:
        print("⚠️ DATA QUALITY: No activities found")
        return {
            "quality": "INSUFFICIENT",
            "reason": "No activities found",
            "use_fallbacks": True,
            "filtered_activities": [],
            "filtered_count": 0,
            "total_count": 0,
        }

    # Filter activities at granular level
    valid_activities = []
    invalid_reasons = []

    today = datetime.today().date()

    for activity in activities:
        activity_date_str = activity["activity_date"]
        # Convert string date to date object
        try:
            activity_date = datetime.strptime(activity_date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            invalid_reasons.append(
                f"Activity has invalid date format: {activity_date_str}"
            )
            continue

        days_old = (today - activity_date).days

        # Check if activity is too old (>90 days)
        if days_old > 90:
            invalid_reasons.append(f"Activity {activity_date} is {days_old} days old")
            continue

        # Check if activity has essential data
        if not activity.get("distance") or activity.get("distance", 0) == 0:
            invalid_reasons.append(f"Activity {activity_date} has no distance data")
            continue

        # Check if activity has reasonable data
        if activity.get("distance", 0) < 0.1:  # Less than 0.1 miles
            invalid_reasons.append(
                f"Activity {activity_date} distance too short ({activity.get('distance')} miles)"
            )
            continue

        valid_activities.append(activity)

    # Assess quality based on filtered data
    activity_count = len(valid_activities)
    total_count = len(activities)
    filtered_count = total_count - activity_count

    if activity_count == 0:
        print(f"\n🔍 DATA QUALITY ASSESSMENT:")
        print(f"   • Total activities: {total_count}")
        print(f"   • Valid activities: {activity_count}")
        print(f"   ⚠️ NO VALID DATA: All activities filtered out")
        return {
            "quality": "INSUFFICIENT",
            "reason": "All activities filtered out",
            "use_fallbacks": True,
            "filtered_activities": valid_activities,
            "filtered_count": filtered_count,
            "total_count": total_count,
        }

    # Check recency of valid activities
    most_recent_str = max(valid_activities, key=lambda x: x["activity_date"])[
        "activity_date"
    ]
    most_recent_date = datetime.strptime(most_recent_str, "%Y-%m-%d").date()
    days_since_last = (today - most_recent_date).days

    # Check time span of valid activities
    if len(valid_activities) > 1:
        max_date_str = max(valid_activities, key=lambda x: x["activity_date"])[
            "activity_date"
        ]
        min_date_str = min(valid_activities, key=lambda x: x["activity_date"])[
            "activity_date"
        ]
        max_date = datetime.strptime(max_date_str, "%Y-%m-%d").date()
        min_date = datetime.strptime(min_date_str, "%Y-%m-%d").date()
        date_range = (max_date - min_date).days
    else:
        date_range = 0

    print(f"\n🔍 DATA QUALITY ASSESSMENT:")
    print(f"   • Total activities: {total_count}")
    print(f"   • Valid activities: {activity_count}")
    print(f"   • Filtered out: {filtered_count}")
    print(f"   • Days since last activity: {days_since_last}")
    print(f"   • Data spans: {date_range} days")

    if filtered_count > 0:
        print(
            f"   • Filtered reasons: {invalid_reasons[:3]}..."
        )  # Show first 3 reasons

    # Determine quality level - prioritize using real data
    if days_since_last > 60:  # More lenient: 60 days instead of 30
        quality = "STALE"
        use_fallbacks = True
        print(f"   ⚠️ STALE DATA: Last valid activity was {days_since_last} days ago")
    elif activity_count < 3:  # More lenient: 3 activities instead of 5
        quality = "INSUFFICIENT"
        use_fallbacks = True
        print(f"   ⚠️ INSUFFICIENT DATA: Only {activity_count} valid activities")
    elif date_range < 7 and activity_count < 5:  # More lenient: 7 days instead of 14
        quality = "INSUFFICIENT"
        use_fallbacks = True
        print(
            f"   ⚠️ INSUFFICIENT TIMESPAN: Data spans only {date_range} days with {activity_count} activities"
        )
    else:
        quality = "GOOD"
        use_fallbacks = False
        print(
            f"   ✅ GOOD DATA: {activity_count} valid activities for accurate calculations"
        )

    return {
        "quality": quality,
        "reason": f"{activity_count} valid activities, {filtered_count} filtered",
        "use_fallbacks": use_fallbacks,
        "filtered_activities": valid_activities,
        "filtered_count": filtered_count,
        "total_count": total_count,
        "days_since_last": days_since_last,
        "date_range": date_range,
    }


def assess_marathon_safety(
    user_profile: dict, data_quality: dict, weekly_summaries: list
) -> dict:
    """
    Evidence-based marathon training safety assessment
    Based on established running science and injury prevention research

    Safety thresholds:
    - < 6 weeks: Never safe (injury risk too high)
    - 6-8 weeks: Requires 20+ miles/week base
    - 8-12 weeks: Requires 15+ miles/week base
    - 12-16 weeks: Requires 10+ miles/week base
    - 16+ weeks: Any base mileage acceptable
    """
    race_date = user_profile.get("race_date")
    race_distance = str(user_profile.get("race_distance", "")).lower()

    # Only assess marathon plans
    if "marathon" not in race_distance:
        return {"safe": True, "reason": "Not a marathon plan", "risk_level": "NONE"}

    if not race_date:
        return {
            "safe": False,
            "reason": "No race date specified",
            "risk_level": "CRITICAL",
            "user_message": "Please set your race date before generating a training plan.",
            "show_popup": True,
            "block_plan_creation": True,
        }

    # Calculate weeks until race
    try:
        race_date_obj = datetime.strptime(str(race_date), "%Y-%m-%d").date()
        weeks_until_race = (race_date_obj - datetime.today().date()).days / 7
    except (ValueError, TypeError):
        return {
            "safe": False,
            "reason": "Invalid race date format",
            "risk_level": "CRITICAL",
            "user_message": "Please check your race date format (YYYY-MM-DD).",
            "show_popup": True,
            "block_plan_creation": True,
        }

    # Calculate base mileage (last 4 weeks)
    base_mileage = 0
    if weekly_summaries:
        total_mileage = 0
        count = 0
        for summary in weekly_summaries[:4]:  # Last 4 weeks
            if isinstance(summary, str) and "miles" in summary:
                import re

                miles_match = re.search(r"(\d+\.?\d*)\s*miles", summary)
                if miles_match:
                    total_mileage += float(miles_match.group(1))
                    count += 1
        if count > 0:
            base_mileage = total_mileage / count

    # Training consistency
    training_weeks = len(weekly_summaries) if weekly_summaries else 0
    last_activity_days = data_quality.get("days_since_last", 999)

    print(f"\n🏃 EVIDENCE-BASED MARATHON SAFETY ASSESSMENT:")
    print(f"   • Weeks until race: {weeks_until_race:.1f}")
    print(f"   • Current base mileage: {base_mileage:.1f} miles/week")
    print(f"   • Training consistency: {training_weeks} weeks of data")
    print(f"   • Days since last activity: {last_activity_days}")
    print(f"   • Longest run: {user_profile.get('longest_run', 0)} miles")

    # EVIDENCE-BASED SAFETY LOGIC

    # 1. ABSOLUTE MINIMUM TIME REQUIREMENT (with exception for strong base)
    if weeks_until_race < 6:
        # CRITICAL: Even with strong base, < 2 weeks is never safe
        if weeks_until_race < 2:
            return {
                "safe": False,
                "reason": f"Only {weeks_until_race:.1f} weeks until marathon - absolutely insufficient time regardless of training base",
                "risk_level": "CRITICAL",
                "user_message": f"⚠️ CRITICAL RISK: Only {weeks_until_race:.1f} weeks until your marathon. This is absolutely insufficient time for any safe marathon training, regardless of your training base. Consider postponing your race or choosing a shorter distance.",
                "show_popup": True,
                "block_plan_creation": True,
            }

        # Check for strong base exception (only for 2-6 weeks)
        longest_run = user_profile.get("longest_run", 0)
        strong_base_exception = (
            base_mileage >= 15  # Strong weekly base
            and training_weeks >= 10  # Consistent training history
            and last_activity_days <= 7  # Recent activity
            and longest_run >= 20  # Marathon readiness indicator
        )

        print(f"\n🔍 STRONG BASE EXCEPTION CHECK:")
        print(
            f"   • Base mileage >= 15: {base_mileage:.1f} >= 15 = {base_mileage >= 15}"
        )
        print(
            f"   • Training weeks >= 10: {training_weeks} >= 10 = {training_weeks >= 10}"
        )
        print(
            f"   • Recent activity <= 7 days: {last_activity_days} <= 7 = {last_activity_days <= 7}"
        )
        print(f"   • Longest run >= 20: {longest_run} >= 20 = {longest_run >= 20}")
        print(f"   • Exception applies: {strong_base_exception}")

        if strong_base_exception:
            return {
                "safe": True,
                "reason": f"Only {weeks_until_race:.1f} weeks until marathon - high risk but strong base allows attempt",
                "risk_level": "HIGH",
                "user_message": f"⚠️ HIGH RISK: Only {weeks_until_race:.1f} weeks until your marathon. This is very challenging and high-risk. However, your strong training base ({base_mileage:.1f} mi/week, {longest_run:.1f} mi longest run, {training_weeks} weeks consistent training) makes this attempt possible. Proceed with extreme caution and listen to your body.",
                "show_popup": True,
                "block_plan_creation": False,
            }
        else:
            return {
                "safe": False,
                "reason": f"Only {weeks_until_race:.1f} weeks until marathon - insufficient time and base for safe training",
                "risk_level": "CRITICAL",
                "user_message": f"⚠️ CRITICAL RISK: Only {weeks_until_race:.1f} weeks until your marathon. This is insufficient time for safe training and significantly increases injury risk. Consider postponing your race or choosing a shorter distance.",
                "show_popup": True,
                "block_plan_creation": True,
            }

    # 2. RECENT ACTIVITY REQUIREMENT
    if last_activity_days > 14:
        return {
            "safe": False,
            "reason": f"Last activity was {last_activity_days} days ago - too inactive for marathon training",
            "risk_level": "HIGH",
            "user_message": f"⚠️ HIGH RISK: Your last run was {last_activity_days} days ago. You need to be actively running (within 14 days) before starting marathon training to prevent injury.",
            "show_popup": True,
            "block_plan_creation": True,
        }

    # 3. TRAINING CONSISTENCY REQUIREMENT
    if training_weeks < 8:
        return {
            "safe": False,
            "reason": f"Only {training_weeks} weeks of training data - insufficient training history",
            "risk_level": "HIGH",
            "user_message": f"⚠️ HIGH RISK: You only have {training_weeks} weeks of training history. Marathon training requires at least 8 weeks of consistent training data to ensure safe progression.",
            "show_popup": True,
            "block_plan_creation": True,
        }

    # 4. BASE MILEAGE REQUIREMENTS BY TIME FRAME
    if weeks_until_race < 8:
        if base_mileage < 20:
            return {
                "safe": False,
                "reason": f"Only {weeks_until_race:.1f} weeks left with {base_mileage:.1f} miles/week base - requires 20+ miles/week",
                "risk_level": "HIGH",
                "user_message": f"⚠️ HIGH RISK: With only {weeks_until_race:.1f} weeks until your marathon, you need at least 20 miles/week base mileage. Your current base is {base_mileage:.1f} miles/week. This timeframe is very challenging and increases injury risk significantly.",
                "show_popup": True,
                "block_plan_creation": True,
            }
        else:
            return {
                "safe": True,
                "reason": f"{weeks_until_race:.1f} weeks with {base_mileage:.1f} miles/week base - challenging but possible",
                "risk_level": "MODERATE",
                "user_message": f"⚠️ MODERATE RISK: You have {weeks_until_race:.1f} weeks until your marathon with {base_mileage:.1f} miles/week base. This is challenging but possible. Proceed with extreme caution and listen to your body.",
                "show_popup": False,
                "block_plan_creation": False,
            }

    elif weeks_until_race < 12:
        if base_mileage < 15:
            return {
                "safe": False,
                "reason": f"Only {weeks_until_race:.1f} weeks left with {base_mileage:.1f} miles/week base - requires 15+ miles/week",
                "risk_level": "HIGH",
                "user_message": f"⚠️ HIGH RISK: With {weeks_until_race:.1f} weeks until your marathon, you need at least 15 miles/week base mileage. Your current base is {base_mileage:.1f} miles/week. Consider building more base mileage before attempting marathon training.",
                "show_popup": True,
                "block_plan_creation": True,
            }
        else:
            return {
                "safe": True,
                "reason": f"{weeks_until_race:.1f} weeks with {base_mileage:.1f} miles/week base - adequate preparation time",
                "risk_level": "LOW",
                "user_message": f"✅ SAFE: You have {weeks_until_race:.1f} weeks until your marathon with {base_mileage:.1f} miles/week base. This provides adequate preparation time for marathon training.",
                "show_popup": False,
                "block_plan_creation": False,
            }

    elif weeks_until_race < 16:
        if base_mileage < 10:
            return {
                "safe": True,
                "reason": f"{weeks_until_race:.1f} weeks with {base_mileage:.1f} miles/week base - sufficient time to build fitness",
                "risk_level": "MODERATE",
                "user_message": f"⚠️ MODERATE RISK: You have {weeks_until_race:.1f} weeks until your marathon with {base_mileage:.1f} miles/week base. While you have sufficient time to build fitness, your low base mileage increases injury risk. Proceed with caution.",
                "show_popup": False,
                "block_plan_creation": False,
            }
        else:
            return {
                "safe": True,
                "reason": f"{weeks_until_race:.1f} weeks with {base_mileage:.1f} miles/week base - good preparation time",
                "risk_level": "LOW",
                "user_message": f"✅ SAFE: You have {weeks_until_race:.1f} weeks until your marathon with {base_mileage:.1f} miles/week base. This provides good preparation time for marathon training.",
                "show_popup": False,
                "block_plan_creation": False,
            }

    else:  # 16+ weeks
        return {
            "safe": True,
            "reason": f"{weeks_until_race:.1f} weeks with {base_mileage:.1f} miles/week base - excellent preparation time",
            "risk_level": "LOW",
            "user_message": f"✅ EXCELLENT: You have {weeks_until_race:.1f} weeks until your marathon with {base_mileage:.1f} miles/week base. This provides excellent preparation time for comprehensive marathon training.",
            "show_popup": False,
            "block_plan_creation": False,
        }


def _normalize_training_days(training_days_raw) -> list[str]:
    """Normalize training days to 3-letter uppercase format."""
    if not training_days_raw:
        # No hardcoded defaults - return empty list to force user to set training days
        return []

    normalized_days = []
    for day in training_days_raw:
        day_str = str(day).strip()

        # Handle enum values like "TrainingDay.MON" -> "Mon"
        if "." in day_str:
            day_str = day_str.split(".")[-1]  # Get the part after the dot

        if len(day_str) >= 3:
            normalized_day = day_str[:3].upper()
            normalized_days.append(normalized_day)

    return normalized_days


def load_recent_activities(
    session: Session, include_splits: bool = True, user_id: Optional[str] = None
) -> list[dict]:
    # Load activities from the view
    if user_id:
        activity_query = text(
            """
            SELECT *
            FROM v_activities_running_plan
            WHERE user_id = :user_id
            ORDER BY activity_date DESC
            LIMIT 50
        """
        )
        activity_rows = (
            session.execute(activity_query, {"user_id": user_id}).mappings().all()
        )
    else:
        activity_query = text(
            """
            SELECT *
            FROM v_activities_running_plan
            ORDER BY activity_date DESC
            LIMIT 50
        """
        )
        activity_rows = session.execute(activity_query).mappings().all()

    # DEBUG: Show raw SQL column names
    if activity_rows:
        print(f"  • Raw SQL columns: {list(activity_rows[0].keys())}")

    activities = [dict(row) for row in activity_rows]

    # Assess data quality BEFORE any calculations
    data_quality = assess_data_quality(activities)

    # Use filtered activities for all subsequent calculations
    activities = data_quality.get("filtered_activities", activities)

    if not include_splits:
        return activities, data_quality

    # Prepare to inject splits
    activity_map = {a["activity_id"]: a for a in activities}
    for a in activities:
        a["splits"] = []

    # Load matching splits
    split_query = text(
        """
        SELECT *
        FROM v_splits_running_plan
        WHERE activity_id = ANY(:ids)
        ORDER BY activity_id, split
    """
    )
    split_rows = (
        session.execute(split_query, {"ids": list(activity_map.keys())})
        .mappings()
        .all()
    )

    for split in split_rows:
        activity_id = split["activity_id"]
        if activity_id in activity_map:
            activity_map[activity_id]["splits"].append(dict(split))

    return activities, data_quality


def summarize_weekly_training(activities: list[dict]) -> list[str]:
    # Group activities by ISO week (year, week number)
    weeks = defaultdict(list)
    for activity in activities:
        date_obj = datetime.strptime(activity["activity_date"], "%Y-%m-%d")
        year_week = date_obj.isocalendar()[:2]  # (year, week)
        weeks[year_week].append(activity)

    summaries = []

    for (year, week), week_activities in sorted(weeks.items(), reverse=True):
        # Determine week start (Monday)
        week_start = datetime.strptime(f"{year}-W{week}-1", "%G-W%V-%u").date()
        week_label = week_start.strftime("Week of %b %d")

        total_runs = len(week_activities)
        total_miles = round(sum(a["distance"] for a in week_activities), 2)
        longest_run = round(max(a["distance"] for a in week_activities), 2)

        # Avg pace (convert from speed mph to pace min/mile)
        paces = [60 / a["avg_speed"] for a in week_activities if a["avg_speed"] > 0]
        avg_pace = mean(paces) if paces else 0
        avg_pace_str = f"{int(avg_pace)}:{int((avg_pace % 1) * 60):02d}/mi"

        # HR Zones (simplified)
        zone2_values = [a["hr_zone2"] for a in week_activities]
        avg_zone2 = mean(zone2_values) if zone2_values else 0
        zone_summary = "mostly Zone 2" if avg_zone2 > 40 else "mixed Zones"

        summary = (
            f"{week_label}: {total_runs} runs, {total_miles} miles, "
            f"longest run {longest_run}mi, avg pace {avg_pace_str}, HR {zone_summary}."
        )
        summaries.append(summary)

    return summaries


from uuid import UUID


def summarize_user_profile(session: Session, user_id: UUID) -> dict:
    # Pull data from user_profile table (age, experience, preferences, etc.)
    # Derive longest run + training frequency from activities
    # Return as JSON

    profile = session.query(UserProfile).filter_by(user_id=user_id).one_or_none()

    if not profile:
        return {}

    # Load activities to calculate longest run from actual data (if profile.longest_run is NULL)
    calculated_longest_run = None
    if not profile.longest_run:  # Only calculate if database value is missing
        activities, _ = load_recent_activities(
            session, include_splits=False, user_id=str(user_id)
        )

        if activities:
            distances = [
                float(activity.get("distance", 0))
                for activity in activities
                if activity.get("distance")
            ]
            if distances:
                calculated_longest_run = max(distances)

    # Convert age_group to numeric age for Jack Daniels formula
    def age_group_to_age(age_group):
        if not age_group:
            return 35  # Default
        age_group_str = str(age_group)
        if "18-24" in age_group_str or "18_24" in age_group_str:
            return 21
        elif "25-34" in age_group_str or "25_34" in age_group_str:
            return 30
        elif "35-44" in age_group_str or "35_44" in age_group_str:
            return 40
        elif "45-54" in age_group_str or "45_54" in age_group_str:
            return 50
        elif "55+" in age_group_str or "55_" in age_group_str:
            return 60
        elif "Under 18" in age_group_str:
            return 16
        else:
            return 35  # Default

    return {
        # Core profile data
        "age": age_group_to_age(profile.age_group),
        "age_group": profile.age_group,
        "runner_level": profile.runner_level,
        "weight": profile.weight,
        "height_feet": profile.height_feet,
        "height_inches": profile.height_inches,
        "training_days": _normalize_training_days(profile.training_days),
        # Race data
        "race_history": profile.race_history,
        "race_date": str(profile.race_date) if profile.race_date else None,
        "race_distance": profile.race_distance,
        "past_races": profile.past_races,
        # Preferences and goals
        "main_goal": profile.main_goal,
        "motivation": profile.motivation,
        "run_preference": profile.run_preference,
        "longest_run": profile.longest_run or calculated_longest_run,
        # Legacy format for compatibility
        "height": (
            f"{profile.height_feet}ft {profile.height_inches}in"
            if profile.height_feet
            else None
        ),
    }


def assemble_training_plan_data(session: Session, user_id: UUID) -> dict:
    print(f"\n🔍 DEBUG: Data Assembler - Loading data for user {user_id}")

    activities, data_quality = load_recent_activities(
        session, include_splits=True, user_id=str(user_id)
    )
    print(f"  • Loaded {len(activities)} activities")

    # DEBUG: Show what's actually in the activities JSON
    if activities:
        print(f"  • Sample activity JSON structure:")
        sample_activity = activities[0]
        for key, value in sample_activity.items():
            if key != "splits":  # Skip splits to keep output clean
                print(f"    - {key}: {value}")

        # Check specifically for heart rate fields
        print(f"  • Heart rate fields in activities:")
        for i, activity in enumerate(activities[:3]):  # Check first 3 activities
            activity_name = activity.get("activity_name", "Unknown")
            max_hr = activity.get("max_hr", "MISSING")
            avg_hr = activity.get("avg_hr", "MISSING")
            print(
                f"    Activity {i+1} ({activity_name}): max_hr={max_hr}, avg_hr={avg_hr}"
            )
    else:
        print(f"  • No activities found!")

    # DEBUG: Show date range of activities being used for weekly summaries
    if activities:
        dates = [a["activity_date"] for a in activities]
        print(f"  🔍 DEBUG: Activities date range: {min(dates)} to {max(dates)}")
        print(f"  🔍 DEBUG: Total activities for weekly summaries: {len(activities)}")
    
    weekly_summaries = summarize_weekly_training(activities)
    print(f"  • Generated {len(weekly_summaries)} weekly summaries")
    
    # DEBUG: Show first few weekly summaries
    if weekly_summaries:
        print(f"  • First 3 weekly summaries:")
        for i, summary in enumerate(weekly_summaries[:3]):
            print(f"    [{i+1}] {summary}")

    user_profile = summarize_user_profile(session, user_id)
    print(
        f"  • User profile keys: {list(user_profile.keys()) if user_profile else 'None'}"
    )

    if user_profile:
        print(f"  • User profile data:")
        for key, value in user_profile.items():
            # Add fallback indicators for key fields
            if key == "age":
                source = (
                    "✅ DATABASE (from age_group)"
                    if value
                    else "⚠️ FALLBACK (default 35)"
                )
            elif key == "weight":
                source = "✅ DATABASE" if value else "⚠️ FALLBACK (default 70)"
            elif key == "longest_run":
                source = "✅ DATABASE" if value else "⚠️ CALCULATED from activities"
            elif key == "runner_level":
                source = "✅ DATABASE" if value else "⚠️ FALLBACK (default Intermediate)"
            else:
                source = "✅ DATABASE" if value else "⚠️ MISSING"

            print(f"    - {key}: {value} - {source}")
    else:
        print(f"  • ⚠️ NO USER PROFILE FOUND for user {user_id}")

    # Assess marathon safety for marathon plans
    marathon_safety = assess_marathon_safety(
        user_profile, data_quality, weekly_summaries
    )

    # Enhanced quality assessment with data quality and marathon safety check
    quality_assessment = {
        "overall_quality": data_quality.get("quality", "UNKNOWN"),
        "quality_score": 75.0 if data_quality.get("quality") == "GOOD" else 50.0,
        "can_generate_plan": marathon_safety.get("safe", True),
        "recommendations": (
            ["Data quality sufficient for plan generation"]
            if data_quality.get("quality") == "GOOD"
            else ["Using fallback data due to insufficient training history"]
        ),
        "warnings": (
            [data_quality.get("reason", "")]
            if data_quality.get("use_fallbacks")
            else []
        ),
        "critical_issues": (
            [marathon_safety.get("reason", "")]
            if not marathon_safety.get("safe", True)
            else []
        ),
        "fallback_strategy": "ENABLED" if data_quality.get("use_fallbacks") else "NONE",
        "data_quality": data_quality,
        "marathon_safety": marathon_safety,
    }

    return {
        "user_profile": user_profile,
        "weekly_summaries": weekly_summaries,
        "activities": activities,  # keep raw activities for transparency
        "quality_assessment": quality_assessment,
    }
