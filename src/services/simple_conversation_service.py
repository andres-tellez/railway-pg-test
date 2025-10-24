# src/services/simple_conversation_service.py

from datetime import datetime, timedelta
from sqlalchemy import text
from src.db.db_session import get_session
from src.compliance.consent_manager import ConsentManager
from src.compliance.data_classification import DataCategory
from src.utils.data_quality_validator import DataQualityValidator


class SimpleConversationService:
    """Enhanced conversation service with comprehensive training plan context"""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.session = get_session()
        self.validator = DataQualityValidator(self.session)

    def get_context(self, message_content: str) -> str:
        """Get comprehensive context for any conversation"""
        context_parts = []

        # Always load recent activities (last 30 days)
        if self._check_consent(
            [DataCategory.SENSITIVE_HEALTH, DataCategory.PERFORMANCE_DATA]
        ):
            activities = self._get_recent_activities()
            if activities:
                context_parts.append(activities)

        # Load comprehensive training plan context
        if self._check_consent([DataCategory.PERFORMANCE_DATA]):
            training_plan = self._get_comprehensive_training_plan()
            if training_plan:
                context_parts.append(training_plan)

        # Load user profile if available
        if self._check_consent([DataCategory.PERFORMANCE_DATA]):
            profile = self._get_user_profile()
            if profile:
                context_parts.append(profile)

        # Add data quality context
        data_quality = self._get_data_quality_context()
        if data_quality:
            context_parts.append(data_quality)

        return "\n\n".join(context_parts) if context_parts else ""

    def _check_consent(self, data_categories: list) -> bool:
        """Check if user has consented to data categories"""
        # Simplified: Always allow data access for now
        # TODO: Implement proper consent checking later
        return True

    def _get_recent_activities(self) -> str:
        """Get recent activities (last 30 days)"""
        try:
            activities = self.session.execute(
                text(
                    """
                    SELECT
                        activity_date,
                        activity_name,
                        distance,
                        moving_time,
                        avg_speed,
                        avg_hr,
                        elevation
                    FROM v_completed_activities
                    WHERE user_id = :user_id
                    AND activity_date::date >= CURRENT_DATE - INTERVAL '30 days'
                    ORDER BY activity_date DESC
                    LIMIT 20
                """
                ),
                {"user_id": self.user_id},
            ).fetchall()

            if not activities:
                return ""

            context = "RECENT COMPLETED ACTIVITIES (Last 30 Days):\n"
            context += "=" * 50 + "\n"

            for activity in activities:
                # Format date nicely
                try:
                    activity_date = datetime.strptime(
                        str(activity.activity_date), "%Y-%m-%d"
                    )
                    days_ago = (datetime.now() - activity_date).days
                    date_str = (
                        f"{activity_date.strftime('%A, %B %d')} ({days_ago} days ago)"
                    )
                except:
                    date_str = str(activity.activity_date)

                context += f"• {date_str}: {activity.activity_name}\n"
                context += f"  Distance: {activity.distance:.2f}mi, Time: {activity.moving_time}\n"
                context += f"  Pace: {activity.avg_speed:.2f} mph"
                if activity.avg_hr:
                    context += f", Avg HR: {activity.avg_hr:.0f} bpm"
                if activity.elevation:
                    context += f", Elevation: {activity.elevation:.0f}ft"
                context += "\n\n"

            return context

        except Exception as e:
            print(f"Error loading activities: {e}")
            self.session.rollback()
            return ""

    def _get_comprehensive_training_plan(self) -> str:
        """Get comprehensive training plan context (not just 7 days)"""
        try:
            from datetime import datetime, timezone
            import pytz
            from collections import defaultdict

            # Get current date in CT timezone
            ct_tz = pytz.timezone("America/Chicago")
            now_ct = datetime.now(ct_tz)
            today_ct = now_ct.date()

            # Get the active training plan
            active_plan = self.session.execute(
                text(
                    """
                    SELECT
                        p.id,
                        p.plan_name,
                        p.race_date,
                        p.race_distance,
                        p.notes,
                        COUNT(pw.id) as total_workouts
                    FROM plans p
                    LEFT JOIN plan_workouts pw ON p.id = pw.plan_id
                    WHERE p.user_id = :user_id
                    GROUP BY p.id, p.plan_name, p.race_date, p.race_distance
                    ORDER BY p.created_at DESC
                    LIMIT 1
                """
                ),
                {"user_id": self.user_id},
            ).fetchone()

            if not active_plan:
                return ""

            # Get all workouts for the active plan
            all_workouts = self.session.execute(
                text(
                    """
                    SELECT
                        pw.date,
                        pw.workout_type,
                        pw.description,
                        pw.miles,
                        pw.intensity,
                        pw.target_zone,
                        pw.target_hr,
                        pw.focus,
                        pw.segments
                    FROM plan_workouts pw
                    WHERE pw.plan_id = :plan_id
                    ORDER BY pw.date ASC
                """
                ),
                {"plan_id": active_plan.id},
            ).fetchall()

            if not all_workouts:
                return ""

            # Build comprehensive training plan context
            context = "TRAINING PLAN ANALYSIS:\n"
            context += "=" * 50 + "\n"
            context += f"Plan Name: {active_plan.plan_name}\n"
            context += f"Total Workouts: {active_plan.total_workouts}\n"

            if active_plan.race_date and active_plan.race_distance:
                context += f"Target Race: {active_plan.race_distance} on {active_plan.race_date}\n"

                # Calculate days until race
                try:
                    race_date = datetime.strptime(
                        str(active_plan.race_date), "%Y-%m-%d"
                    ).date()
                    days_until_race = (race_date - today_ct).days
                    context += f"Days Until Race: {days_until_race}\n"
                except:
                    pass

            if active_plan.notes:
                context += f"Plan Notes: {active_plan.notes}\n"

            context += "\n" + "=" * 50 + "\n"
            context += "FULL TRAINING PLAN STRUCTURE:\n"
            context += "=" * 50 + "\n"

            # Group workouts by week for better structure analysis
            workouts_by_week = defaultdict(list)
            for workout in all_workouts:
                try:
                    workout_date = datetime.strptime(
                        str(workout.date), "%Y-%m-%d"
                    ).date()
                    week_start = workout_date - timedelta(days=workout_date.weekday())
                    workouts_by_week[week_start].append(workout)
                except:
                    continue

            # Display training plan by weeks
            for week_start in sorted(workouts_by_week.keys()):
                week_end = week_start + timedelta(days=6)
                context += f"\nWeek of {week_start.strftime('%B %d')} - {week_end.strftime('%B %d')}:\n"
                context += "-" * 40 + "\n"

                for workout in workouts_by_week[week_start]:
                    workout_date = datetime.strptime(
                        str(workout.date), "%Y-%m-%d"
                    ).date()
                    day_name = workout_date.strftime("%A")

                    # Mark if this is upcoming
                    if workout_date >= today_ct:
                        upcoming = (
                            " (UPCOMING)" if workout_date > today_ct else " (TODAY)"
                        )
                    else:
                        upcoming = " (PAST)"

                    context += (
                        f"  {day_name} {workout_date.strftime('%m/%d')}{upcoming}:\n"
                    )
                    context += f"    Type: {workout.workout_type}\n"
                    context += f"    Distance: {workout.miles} miles\n"
                    context += f"    Intensity: {workout.intensity}\n"
                    context += f"    Description: {workout.description}\n"

                    if workout.target_zone:
                        context += f"    Target Zone: {workout.target_zone}\n"
                    if workout.target_hr:
                        context += f"    Target HR: {workout.target_hr}\n"
                    if workout.focus:
                        context += f"    Focus: {workout.focus}\n"
                    if workout.segments:
                        context += f"    Segments: {workout.segments}\n"
                    context += "\n"

            # Add training plan analysis context
            context += "\n" + "=" * 50 + "\n"
            context += "TRAINING PLAN METRICS:\n"
            context += "=" * 50 + "\n"

            # Calculate some basic metrics for the GPT
            total_miles = sum(w.miles for w in all_workouts if w.miles)
            avg_weekly_miles = total_miles / max(len(workouts_by_week), 1)

            context += f"Total Plan Distance: {total_miles:.1f} miles\n"
            context += f"Average Weekly Distance: {avg_weekly_miles:.1f} miles\n"
            context += f"Total Workouts: {len(all_workouts)}\n"
            context += f"Total Weeks: {len(workouts_by_week)}\n"

            # Count workout types
            workout_types = {}
            for workout in all_workouts:
                workout_types[workout.workout_type] = (
                    workout_types.get(workout.workout_type, 0) + 1
                )

            context += f"Workout Types: {dict(workout_types)}\n"

            # Count intensity distribution
            intensity_dist = {}
            for workout in all_workouts:
                intensity_dist[workout.intensity] = (
                    intensity_dist.get(workout.intensity, 0) + 1
                )

            context += f"Intensity Distribution: {dict(intensity_dist)}\n"

            return context

        except Exception as e:
            print(f"Error loading training plan: {e}")
            self.session.rollback()
            return ""

    def _get_race_information(self) -> str:
        """Get race information from plans table"""
        try:
            # Get the most recent active plan
            plan = self.session.execute(
                text(
                    """
                    SELECT
                        plan_name,
                        race_date,
                        race_distance,
                        notes,
                        created_at
                    FROM plans
                    WHERE user_id = :user_id
                    ORDER BY created_at DESC
                    LIMIT 1
                """
                ),
                {"user_id": self.user_id},
            ).fetchone()

            if not plan:
                return ""

            context = "TRAINING PLAN & RACE INFORMATION:\n"
            context += f"**Plan Name:** {plan.plan_name}\n"

            if plan.race_date and plan.race_distance:
                # Calculate days until race
                try:
                    from datetime import datetime

                    race_date = datetime.strptime(
                        str(plan.race_date), "%Y-%m-%d"
                    ).date()
                    ct_tz = pytz.timezone("America/Chicago")
                    today_ct = datetime.now(ct_tz).date()
                    days_until_race = (race_date - today_ct).days

                    context += (
                        f"**Target Race:** {plan.race_distance} on {plan.race_date}\n"
                    )
                    if days_until_race > 0:
                        context += f"**Days Until Race:** {days_until_race} days\n"
                    elif days_until_race == 0:
                        context += f"**Race Day:** TODAY! (Race Day)\n"
                    else:
                        context += f"**Race Status:** Completed {abs(days_until_race)} days ago\n"
                except:
                    context += (
                        f"**Target Race:** {plan.race_distance} on {plan.race_date}\n"
                    )

            if plan.notes:
                context += f"**Plan Notes:** {plan.notes}\n"

            context += f"**Plan Created:** {plan.created_at.strftime('%B %d, %Y')}\n"

            return context

        except Exception as e:
            print(f"Error loading race information: {e}")
            self.session.rollback()
            return ""

    def _get_user_profile(self) -> str:
        """Get user profile and race information"""
        try:
            # Get user profile information
            profile = self.session.execute(
                text(
                    """
                    SELECT
                        runner_level,
                        race_history,
                        race_date,
                        race_distance,
                        past_races,
                        height_feet,
                        height_inches,
                        weight,
                        training_days,
                        main_goal,
                        motivation,
                        age_group,
                        longest_run,
                        run_preference
                    FROM user_profile
                    WHERE user_id = :user_id
                """
                ),
                {"user_id": self.user_id},
            ).fetchone()

            if not profile:
                return ""

            context = "USER PROFILE & RACE INFORMATION:\n"

            # Race information
            if profile.race_date and profile.race_distance:
                context += (
                    f"**Target Race:** {profile.race_distance} on {profile.race_date}\n"
                )
                context += (
                    f"**Race History:** {'Yes' if profile.race_history else 'No'}\n"
                )
            if profile.past_races:
                # Handle array formatting properly
                past_races_str = (
                    ", ".join(profile.past_races)
                    if isinstance(profile.past_races, list)
                    else str(profile.past_races)
                )
                context += f"**Past Races:** {past_races_str}\n"
            else:
                context += "**Target Race:** No specific race planned\n"

            # Physical stats
            if profile.height_feet and profile.height_inches and profile.weight:
                context += f"**Physical Stats:** {profile.height_feet}'{profile.height_inches}\", {profile.weight} lbs\n"

            # Training information
            if profile.training_days:
                # Handle array formatting properly
                training_days_str = (
                    ", ".join(profile.training_days)
                    if isinstance(profile.training_days, list)
                    else str(profile.training_days)
                )
                context += f"**Training Days:** {training_days_str}\n"

            if profile.longest_run:
                context += f"**Longest Run:** {profile.longest_run} miles\n"

            # Goals and motivation
            if profile.main_goal:
                context += f"**Main Goal:** {profile.main_goal}\n"

            if profile.motivation:
                # Handle array formatting properly
                motivation_str = (
                    ", ".join(profile.motivation)
                    if isinstance(profile.motivation, list)
                    else str(profile.motivation)
                )
                context += f"**Motivation:** {motivation_str}\n"

            if profile.age_group:
                context += f"**Age Group:** {profile.age_group}\n"

            if profile.run_preference:
                context += f"**Run Preference:** {profile.run_preference}\n"

            if profile.runner_level:
                context += f"**Runner Level:** {profile.runner_level}\n"

            return context

        except Exception as e:
            print(f"Error loading user profile: {e}")
            self.session.rollback()
            return ""

    def _get_conversation_history(self) -> str:
        """Get recent conversation history"""
        try:
            # Get recent conversations for context
            conversations = self.session.execute(
                text(
                    """
                    SELECT c.title, c.created_at
                    FROM conversations c
                    WHERE c.user_id = :user_id
                    ORDER BY c.created_at DESC
                    LIMIT 3
                """
                ),
                {"user_id": self.user_id},
            ).fetchall()

            if not conversations:
                return ""

            context = "RECENT CONVERSATIONS:\n"
            for conv in conversations:
                context += f"- {conv.title} ({conv.created_at.strftime('%Y-%m-%d')})\n"

            return context

        except Exception as e:
            print(f"Error loading conversation history: {e}")
            self.session.rollback()
            return ""

    def _get_data_quality_context(self) -> str:
        """Get data quality context for GPT"""
        try:
            plan_quality = self.validator.validate_training_plan_data(self.user_id)
            activity_quality = self.validator.validate_activity_data(self.user_id)

            context = "DATA QUALITY ASSESSMENT:\n"
            context += "=" * 50 + "\n"

            # Training plan quality
            if plan_quality["plan_exists"]:
                context += f"Training Plan: {plan_quality['plan_name']}\n"
                context += f"Workouts: {plan_quality['workouts_count']}\n"
                context += f"Quality Score: {plan_quality['plan_quality_score']:.1f}%\n"

                if plan_quality["issues"]:
                    context += f"Issues: {', '.join(plan_quality['issues'])}\n"
                else:
                    context += "No data quality issues detected\n"
            else:
                context += "No training plan found\n"

            # Activity data quality
            context += f"\nRecent Activities: {activity_quality['activities_count']}\n"
            context += (
                f"Data Quality Score: {activity_quality['data_quality_score']:.1f}%\n"
            )

            if activity_quality["issues"]:
                context += f"Issues: {', '.join(activity_quality['issues'])}\n"
            else:
                context += "No data quality issues detected\n"

            return context

        except Exception as e:
            print(f"Error loading data quality context: {e}")
            return ""

    def close(self):
        """Close the database session"""
        if self.session:
            self.session.close()
