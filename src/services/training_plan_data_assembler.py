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
import statistics
from sqlalchemy.sql import text
from typing import Optional
from src.db.models.user_profile import UserProfile


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
            LIMIT 12
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
            LIMIT 12
        """
        )
        activity_rows = session.execute(activity_query).mappings().all()

    activities = [dict(row) for row in activity_rows]

    if not include_splits:
        return activities

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

    return activities


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
        avg_pace = statistics.mean(paces)
        avg_pace_str = f"{int(avg_pace)}:{int((avg_pace % 1) * 60):02d}/mi"

        # HR Zones (simplified)
        avg_zone2 = statistics.mean([a["hr_zone2"] for a in week_activities])
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

    return {
        "runner_level": profile.runner_level,
        "race_history": profile.race_history,
        "race_date": str(profile.race_date) if profile.race_date else None,
        "race_distance": profile.race_distance,
        "past_races": profile.past_races,
        "height": (
            f"{profile.height_feet}ft {profile.height_inches}in"
            if profile.height_feet
            else None
        ),
        "weight": profile.weight,
        "training_days": profile.training_days,
        "main_goal": profile.main_goal,
        "motivation": profile.motivation,
        "age_group": profile.age_group,
        "longest_run": profile.longest_run,
        "run_preference": profile.run_preference,
    }


def assemble_training_plan_data(session: Session, user_id: UUID) -> dict:
    activities = load_recent_activities(
        session, include_splits=True, user_id=str(user_id)
    )
    weekly_summaries = summarize_weekly_training(activities)
    user_profile = summarize_user_profile(session, user_id)

    return {
        "user_profile": user_profile,
        "weekly_summaries": weekly_summaries,
        "activities": activities,  # keep raw activities for transparency
    }
