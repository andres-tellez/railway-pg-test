# src/services/simple_conversation_service.py

from datetime import datetime, timedelta
from sqlalchemy import text
from src.db.db_session import get_session
from src.compliance.consent_manager import ConsentManager
from src.compliance.data_classification import DataCategory


class SimpleConversationService:
    """Simplified conversation service that loads comprehensive recent data"""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.session = get_session()

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

        # Load planned workouts (next 7 days) for training plan context
        if self._check_consent([DataCategory.PERFORMANCE_DATA]):
            planned_workouts = self._get_planned_workouts()
            if planned_workouts:
                context_parts.append(planned_workouts)

        # Load race information from plans
        if self._check_consent([DataCategory.PERFORMANCE_DATA]):
            race_info = self._get_race_information()
            if race_info:
                context_parts.append(race_info)

        # Always load user profile if available
        if self._check_consent([DataCategory.PERFORMANCE_DATA]):
            profile = self._get_user_profile()
            if profile:
                context_parts.append(profile)

        # Load conversation history if consent given
        if self._check_consent([DataCategory.CONVERSATION_DATA]):
            history = self._get_conversation_history()
            if history:
                context_parts.append(history)

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
                        avg_hr
                    FROM v_activities_running_plan
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

            context = "RECENT RUNNING ACTIVITIES (Last 30 Days):\n"
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

                context += f"- {date_str}: {activity.activity_name}\n"
                context += f"  Distance: {activity.distance:.2f}mi, Time: {activity.moving_time}\n"
                context += f"  Pace: {activity.avg_speed:.2f} mph"
                if activity.avg_hr:
                    context += f", Avg HR: {activity.avg_hr:.0f} bpm"
                context += "\n"

            return context

        except Exception as e:
            print(f"Error loading activities: {e}")
            self.session.rollback()
            return ""

    def _get_planned_workouts(self) -> str:
        """Get planned workouts (next 7 days)"""
        try:
            # Use local timezone instead of database CURRENT_DATE
            from datetime import datetime, timezone
            import pytz

            # Get current date in CT timezone
            ct_tz = pytz.timezone("America/Chicago")
            now_ct = datetime.now(ct_tz)
            today_ct = now_ct.date()

            planned_workouts = self.session.execute(
                text(
                    """
                    SELECT
                        pw.date,
                        pw.workout_type,
                        pw.description,
                        pw.miles,
                        pw.intensity,
                        pw.target_zone
                    FROM plan_workouts pw
                    JOIN plans p ON pw.plan_id = p.id
                    WHERE p.user_id = :user_id
                    AND pw.date >= :today_date
                    AND pw.date <= :today_date + INTERVAL '7 days'
                    ORDER BY pw.date ASC
                """
                ),
                {"user_id": self.user_id, "today_date": today_ct},
            ).fetchall()

            if not planned_workouts:
                return ""

            context = "PLANNED WORKOUTS (Next 7 Days):\n"

            # Create a set of days with workouts for easy checking
            workout_days = set()
            for workout in planned_workouts:
                try:
                    workout_date = datetime.strptime(
                        str(workout.date), "%Y-%m-%d"
                    ).date()
                    workout_days.add(workout_date)
                except:
                    pass

            # List all days in the next 7 days and mark which have workouts
            from datetime import timedelta

            for i in range(7):
                check_date = today_ct + timedelta(days=i)
                day_name = check_date.strftime("%A")

                if check_date in workout_days:
                    # Find the workout for this day
                    workout = next(
                        (w for w in planned_workouts if str(w.date) == str(check_date)),
                        None,
                    )
                    if workout:
                        if i == 0:
                            date_str = "Today"
                        elif i == 1:
                            date_str = "Tomorrow"
                        else:
                            date_str = f"{day_name}, {check_date.strftime('%B %d')} (in {i} days)"

                        context += f"- {date_str}: {workout.workout_type} - {workout.miles}mi\n"
                        context += f"  Description: {workout.description}\n"
                        context += f"  Intensity: {workout.intensity}"
                        if workout.target_zone:
                            context += f", Target Zone: {workout.target_zone}"
                        context += "\n"
                else:
                    # No workout planned for this day
                    if i == 0:
                        date_str = "Today"
                    elif i == 1:
                        date_str = "Tomorrow"
                    else:
                        date_str = (
                            f"{day_name}, {check_date.strftime('%B %d')} (in {i} days)"
                        )

                    context += f"- {date_str}: NO WORKOUT PLANNED\n"

            # Add explicit summary to prevent hallucination
            context += "\n**IMPORTANT: Only the days listed above with specific workouts have runs planned. Days marked 'NO WORKOUT PLANNED' have NO runs scheduled.**\n"

            return context

        except Exception as e:
            print(f"Error loading planned workouts: {e}")
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

    def close(self):
        """Close the database session"""
        if self.session:
            self.session.close()
