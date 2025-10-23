# src/services/conversation_context_service.py

import time
import asyncio
from typing import Dict, List, Any, Optional
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import text
from src.db.db_session import get_session
from src.config.conversation_config import ConversationConfig

# from src.compliance.consent_manager import ConsentManager, ConsentType
# from src.compliance.data_classification import DataCategory


# Temporary simplified compliance classes
class DataCategory:
    PERSONAL_IDENTIFIABLE = "personal_identifiable"
    PERFORMANCE_DATA = "performance_data"
    SENSITIVE_HEALTH = "sensitive_health"
    CONVERSATION_DATA = "conversation_data"


class ConsentManager:
    @staticmethod
    def check_consent(session, user_id, data_categories):
        # For now, always return True - implement proper consent checking later
        return True


class ConversationContextService:
    """Fast, tweakable conversation context service with caching and async support"""

    def __init__(self, session, user_id: str):
        self.session = session
        self.user_id = user_id
        self._cache = {}
        self._cache_timestamps = {}

    def get_context(
        self, message_content: str, conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get comprehensive context with smart loading and caching"""

        start_time = time.time()

        # Check cache first
        if ConversationConfig.is_cache_enabled():
            cached_context = self._get_cached_context()
            if cached_context:
                print(
                    f"⚡ Context loaded from cache in {time.time() - start_time:.3f}s"
                )
                return cached_context

        # Load context components
        context = {}

        # Load user profile (always needed)
        if self._check_consent([DataCategory.PERSONAL_IDENTIFIABLE]):
            context["user_profile"] = self._get_user_profile_context()

        # Load training plan if relevant
        if ConversationConfig.should_load_context(
            message_content, "training_plan"
        ) and self._check_consent([DataCategory.PERFORMANCE_DATA]):
            context["training_plan"] = self._get_training_plan_context()

        # Load activities if relevant
        if ConversationConfig.should_load_context(
            message_content, "activities"
        ) and self._check_consent(
            [DataCategory.SENSITIVE_HEALTH, DataCategory.PERFORMANCE_DATA]
        ):
            context["activities"] = self._get_activities_context()

        # Load splits if relevant
        if ConversationConfig.should_load_context(
            message_content, "splits"
        ) and self._check_consent([DataCategory.SENSITIVE_HEALTH]):
            context["splits"] = self._get_splits_context()

        # Load conversation history if consent given
        if conversation_id and self._check_consent([DataCategory.CONVERSATION_DATA]):
            context["conversation_history"] = self._get_conversation_history(
                conversation_id
            )

        # Cache context
        if ConversationConfig.is_cache_enabled():
            self._cache_context(context)

        print(f"⚡ Context loaded in {time.time() - start_time:.3f}s")
        return context

    def _check_consent(self, data_categories: List[DataCategory]) -> bool:
        """Check if user has consented to process specific data categories"""
        if not ConversationConfig.COMPLIANCE["require_consent"]:
            return True
        return ConsentManager.check_consent(self.session, self.user_id, data_categories)

    def _get_cached_context(self) -> Optional[Dict[str, Any]]:
        """Get context from cache if valid"""
        cache_key = f"{self.user_id}_context"
        if cache_key in self._cache:
            cache_time = self._cache_timestamps.get(cache_key, 0)
            ttl_seconds = ConversationConfig.CACHE_SETTINGS["ttl_minutes"] * 60
            if time.time() - cache_time < ttl_seconds:
                return self._cache[cache_key]
        return None

    def _cache_context(self, context: Dict[str, Any]):
        """Cache context with timestamp"""
        cache_key = f"{self.user_id}_context"
        self._cache[cache_key] = context
        self._cache_timestamps[cache_key] = time.time()

    def _get_user_profile_context(self) -> str:
        """Get user profile context using optimized query"""
        try:
            result = self.session.execute(
                text(
                    """
                SELECT
                    runner_level,
                    age_group,
                    height_feet,
                    height_inches,
                    weight,
                    main_goal,
                    motivation,
                    training_days,
                    race_history,
                    past_races,
                    longest_run,
                    run_preference,
                    race_date,
                    race_distance
                FROM user_profile
                WHERE user_id = :user_id
            """
                ),
                {"user_id": self.user_id},
            ).fetchone()

            if not result:
                return ""

            context = f"""
RUNNER PROFILE:
- Level: {result.runner_level}
- Age Group: {result.age_group}
- Height: {result.height_feet}'{result.height_inches}"
- Weight: {result.weight} lbs
- Main Goal: {result.main_goal}
- Motivation: {', '.join(result.motivation) if result.motivation else 'Not specified'}
- Training Days: {', '.join(result.training_days) if result.training_days else 'Not specified'}
- Race History: {'Yes' if result.race_history else 'No'}
- Past Races: {', '.join(result.past_races) if result.past_races else 'None'}
- Longest Run: {result.longest_run} miles
- Run Preference: {result.run_preference}
"""

            if result.race_date and result.race_distance:
                context += (
                    f"- Upcoming Race: {result.race_distance} on {result.race_date}\n"
                )

            return context

        except Exception as e:
            print(f"Error loading user profile context: {e}")
            return ""

    def _get_training_plan_context(self) -> str:
        """Get training plan context using optimized query"""
        try:
            result = self.session.execute(
                text(
                    """
                SELECT
                    p.plan_name,
                    p.race_date,
                    p.race_distance,
                    json_agg(
                        json_build_object(
                            'date', w.date,
                            'workout_type', w.workout_type,
                            'description', w.description,
                            'miles', w.miles,
                            'target_zone', w.target_zone,
                            'intensity', w.intensity
                        ) ORDER BY w.date
                    ) as workouts
                FROM plans p
                LEFT JOIN workflow w ON p.id = w.plan_id
                WHERE p.user_id = :user_id
                GROUP BY p.id, p.plan_name, p.race_date, p.race_distance
                ORDER BY p.created_at DESC
                LIMIT 1
            """
                ),
                {"user_id": self.user_id},
            ).fetchone()

            if not result:
                return ""

            context = f"""
CURRENT TRAINING PLAN:
- Plan: {result.plan_name}
- Race Goal: {result.race_distance} on {result.race_date}
- Total Workouts: {len(result.workouts) if result.workouts else 0}

UPCOMING WORKOUTS (next {ConversationConfig.get_context_limit('training_workouts')} days):
"""

            if result.workouts:
                for workout in result.workouts[
                    : ConversationConfig.get_context_limit("training_workouts")
                ]:
                    context += f"- {workout['date']}: {workout['workout_type']}\n"
                    context += f"  {workout['miles']} miles, {workout['intensity']} intensity\n"
                    context += f"  {workout['description']}\n"

            return context

        except Exception as e:
            print(f"Error loading training plan context: {e}")
            return ""

    def _get_activities_context(self) -> str:
        """Get recent activities context using database view"""
        try:
            activities = self.session.execute(
                text(
                    f"""
                SELECT
                    start_date,
                    name,
                    conv_distance,
                    conv_moving_time,
                    conv_avg_speed,
                    average_heartrate
                FROM {ConversationConfig.DATABASE_VIEWS['activities']}
                WHERE user_id = :user_id
                ORDER BY start_date DESC
                LIMIT :limit
            """
                ),
                {
                    "user_id": self.user_id,
                    "limit": ConversationConfig.get_context_limit("activities"),
                },
            ).fetchall()

            if not activities:
                return ""

            context = "\nRECENT RUNNING ACTIVITIES:\n"
            for activity in activities:
                context += (
                    f"- {activity.start_date.strftime('%Y-%m-%d')}: {activity.name}\n"
                )
                context += f"  Distance: {activity.conv_distance:.2f}mi, Time: {activity.conv_moving_time}\n"
                context += f"  Pace: {activity.conv_avg_speed:.2f} mph"
                if activity.average_heartrate:
                    context += f", Avg HR: {activity.average_heartrate:.0f}"
                context += "\n"

            return context

        except Exception as e:
            print(f"Error loading activities context: {e}")
            return ""

    def _get_splits_context(self) -> str:
        """Get splits context using database view"""
        try:
            splits = self.session.execute(
                text(
                    f"""
                SELECT
                    a.start_date,
                    a.name,
                    s.lap_index,
                    s.conv_moving_time,
                    s.conv_avg_speed,
                    s.average_heartrate,
                    s.pace_zone
                FROM {ConversationConfig.DATABASE_VIEWS['splits']} s
                JOIN {ConversationConfig.DATABASE_VIEWS['activities']} a ON s.activity_id = a.activity_id
                WHERE a.user_id = :user_id
                ORDER BY a.start_date DESC, s.lap_index
                LIMIT :limit
            """
                ),
                {
                    "user_id": self.user_id,
                    "limit": ConversationConfig.get_context_limit("splits"),
                },
            ).fetchall()

            if not splits:
                return ""

            context = "\nDETAILED SPLITS ANALYSIS:\n"
            current_activity = None

            for split in splits:
                if current_activity != split.name:
                    current_activity = split.name
                    context += (
                        f"\n{split.start_date.strftime('%Y-%m-%d')}: {split.name}\n"
                    )

                context += f"  Mile {split.lap_index}: {split.conv_moving_time} ({split.conv_avg_speed:.2f} mph)"
                if split.average_heartrate:
                    context += f" - HR: {split.average_heartrate:.0f}"
                if split.pace_zone:
                    context += f" - Zone: {split.pace_zone}"
                context += "\n"

            return context

        except Exception as e:
            print(f"Error loading splits context: {e}")
            return ""

    def _get_conversation_history(self, conversation_id: str) -> List[Dict[str, str]]:
        """Get conversation history"""
        try:
            messages = self.session.execute(
                text(
                    """
                SELECT role, content, created_at
                FROM conversation_messages
                WHERE conversation_id = :conversation_id
                ORDER BY created_at DESC
                LIMIT :limit
            """
                ),
                {
                    "conversation_id": conversation_id,
                    "limit": ConversationConfig.get_context_limit(
                        "conversation_history"
                    ),
                },
            ).fetchall()

            return [
                {"role": msg.role, "content": msg.content} for msg in reversed(messages)
            ]

        except Exception as e:
            print(f"Error loading conversation history: {e}")
            return []
