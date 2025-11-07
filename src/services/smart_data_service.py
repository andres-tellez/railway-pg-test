# src/services/smart_data_service.py

import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy import text
from src.db.db_session import get_session


class SmartDataService:
    """
    Natural language querying service that provides relevant data
    based on user questions using natural language understanding.

    Available data sources:
    - v_completed_activities: Historical activity data
    - v_planned_activities: Planned workouts
    - user_profile: User profile and race information
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.session = get_session()
        self._cache = {}  # Simple in-memory cache

    def close(self):
        """Close the database session"""
        if self.session:
            self.session.close()

    def get_context_for_question(self, question: str) -> Dict:
        """
        Use natural language querying to get relevant data for the user's question.
        """
        try:
            # Get data for the question using natural language understanding
            data_result = self._get_data_for_question(question)

            # Return the result in a structured format
            context = {
                "current_date": time.strftime("%Y-%m-%d"),
                "user_id": self.user_id,
                "question": question,
                "data": data_result,
                "data_sources": [
                    "user_profile",
                    "recent_activities",
                    "planned_workouts",
                    "race_context",
                ],
            }

            return context

        except Exception as e:
            # Fallback to error context
            return {
                "current_date": time.strftime("%Y-%m-%d"),
                "user_id": self.user_id,
                "question": question,
                "error": str(e),
                "data_sources": [],
            }

    def _get_data_for_question(self, question: str) -> Dict:
        """
        Get comprehensive data for the question - let GPT decide what to use.
        """
        data_result = {}

        # Always provide comprehensive data - let GPT decide what to use
        data_result["user_profile"] = self._get_user_profile_data()
        data_result["recent_activities"] = self._get_recent_activities()
        data_result["planned_workouts"] = self._get_planned_workouts_optimized()
        data_result["race_context"] = self._get_race_context()

        # Add question clarity analysis for vague questions
        data_result["question_analysis"] = self._analyze_question_clarity(
            question.lower()
        )

        return data_result

    def _get_recent_activities(self) -> List[Dict]:
        """Get recent completed activities"""
        try:
            result = self.session.execute(
                text(
                    """
                SELECT
                    activity_date,
                    activity_name,
                    distance,
                    avg_speed,
                    avg_hr,
                    max_hr,
                    elevation,
                    moving_time
                FROM v_completed_activities
                WHERE user_id = :user_id
                ORDER BY activity_date DESC
                LIMIT 20
            """
                ),
                {"user_id": self.user_id},
            ).fetchall()

            activities = []
            for row in result:
                activities.append(
                    {
                        "date": str(row.activity_date),
                        "activity_name": row.activity_name,
                        "distance": row.distance,
                        "avg_speed": row.avg_speed,
                        "avg_hr": row.avg_hr,
                        "max_hr": row.max_hr,
                        "elevation": row.elevation,
                        "moving_time": row.moving_time,
                    }
                )
            return activities
        except Exception as e:
            print(f"Error getting recent activities: {e}")
            return []

    def _analyze_question_clarity(self, question_lower: str) -> Dict:
        """Simple analysis of question clarity"""
        vague_phrases = [
            "how am i",
            "how are things",
            "tell me about",
            "show me",
            "what about",
        ]
        is_vague = any(phrase in question_lower for phrase in vague_phrases)

        return {
            "is_vague": is_vague,
            "available_data": [
                "training_schedule",
                "race_info",
                "recent_progress",
                "this_week_workouts",
            ],
            "suggested_clarifications": (
                [
                    "What specific aspect would you like to know about?",
                    "Are you asking about your training schedule, progress, or race preparation?",
                ]
                if is_vague
                else []
            ),
        }

    def _get_user_profile_data(self) -> Dict:
        """Get user profile and race information (cached)"""
        cache_key = f"user_profile_{self.user_id}"

        # Check cache first
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            result = self.session.execute(
                text(
                    """
                SELECT
                    motivation,
                    age_group,
                    height_feet,
                    height_inches,
                    weight
                FROM user_profile
                WHERE user_id = :user_id
            """
                ),
                {"user_id": self.user_id},
            ).fetchone()

            if result:
                profile_data = {
                    "motivation": result.motivation,
                    "age_group": result.age_group,
                    "height_feet": result.height_feet,
                    "height_inches": result.height_inches,
                    "weight": result.weight,
                }
                # Cache the result
                self._cache[cache_key] = profile_data
                return profile_data
            return {}
        except Exception as e:
            print(f"Error getting user profile: {e}")
            return {}

    def _get_race_context(self) -> Dict:
        """Get race context and timeline (cached)"""
        cache_key = f"race_context_{self.user_id}"

        # Check cache first
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            result = self.session.execute(
                text(
                    """
                SELECT
                    race_date,
                    race_distance,
                    main_goal
                FROM user_profile
                WHERE user_id = :user_id
            """
                ),
                {"user_id": self.user_id},
            ).fetchone()

            if result and result.race_date:
                race_date = result.race_date
                if isinstance(race_date, str):
                    race_date = datetime.strptime(race_date, "%Y-%m-%d").date()
                weeks_until_race = (race_date - datetime.now().date()).days // 7

                race_data = {
                    "race_date": str(race_date),
                    "race_distance": result.race_distance,
                    "main_goal": result.main_goal,
                    "weeks_until_race": weeks_until_race,
                }
                # Cache the result
                self._cache[cache_key] = race_data
                return race_data
            return {}
        except Exception as e:
            print(f"Error getting race context: {e}")
            return {}

    def _get_planned_workouts_optimized(self) -> List[Dict]:
        """Get planned workouts (limited to 16 weeks)"""
        try:
            result = self.session.execute(
                text(
                    """
                SELECT
                    date,
                    workout_type,
                    miles,
                    description
                FROM v_planned_activities
                WHERE plan_id IN (
                    SELECT id FROM plans WHERE user_id = :user_id
                )
                AND date <= CURRENT_DATE + INTERVAL '16 weeks'
                ORDER BY date
            """
                ),
                {"user_id": self.user_id},
            ).fetchall()

            workouts = []
            for row in result:
                workouts.append(
                    {
                        "date": str(row.date),
                        "workout_type": row.workout_type,
                        "miles": row.miles,
                        "description": row.description,
                    }
                )
            return workouts
        except Exception as e:
            print(f"Error getting planned workouts: {e}")
            return []

    def _get_planned_workouts(self) -> List[Dict]:
        """Get planned workouts (all) - for backward compatibility"""
        try:
            result = self.session.execute(
                text(
                    """
                SELECT
                    date,
                    workout_type,
                    miles,
                    description
                FROM v_planned_activities
                WHERE plan_id IN (
                    SELECT id FROM plans WHERE user_id = :user_id
                )
                ORDER BY date
            """
                ),
                {"user_id": self.user_id},
            ).fetchall()

            workouts = []
            for row in result:
                workouts.append(
                    {
                        "date": str(row.date),
                        "workout_type": row.workout_type,
                        "miles": row.miles,
                        "description": row.description,
                    }
                )
            return workouts
        except Exception as e:
            print(f"Error getting planned workouts: {e}")
            return []
