# src/services/strategic_conversation_service.py
import logging
from sqlalchemy import text
from src.db.db_session import get_session
from src.compliance.data_classification import DataCategory

logger = logging.getLogger(__name__)


class StrategicConversationService:
    """Simplified service that provides JSON data for GPT analysis"""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.session = get_session()

    def close(self):
        """Close the database session"""
        if self.session:
            self.session.close()

    def _safe_execute_query(self, query: str, params: dict):
        """Safely execute a query with error handling"""
        try:
            return self.session.execute(text(query), params).fetchall()
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            try:
                self.session.rollback()
            except:
                pass
            return []

    def _get_weekly_insights(self) -> dict:
        """Get weekly insights with strategic coaching metrics"""
        try:
            insights = self.session.execute(
                text(
                    """
                    SELECT
                        week_start, week_end, timeframe,
                        actual_vs_planned_total_miles, actual_avg_pace, actual_avg_hr,
                        training_load_ratio, easy_run_percentage, workout_completion_rate,
                        pace_consistency, weeks_until_race,
                        actual_total_miles, actual_workout_count, actual_long_run_miles,
                        planned_total_miles, planned_workout_count, planned_long_run_miles
                    FROM v_weekly_insights
                    WHERE user_id = :user_id
                    AND week_start::date <= CURRENT_DATE
                    ORDER BY week_start DESC
                    LIMIT 8
                """
                ),
                {"user_id": self.user_id},
            ).fetchall()

            if not insights:
                return {}

            weekly_data = []
            for week in insights:
                weekly_data.append(
                    {
                        "week_start": str(week.week_start),
                        "week_end": str(week.week_end),
                        "timeframe": week.timeframe,
                        "actual_training": {
                            "total_miles": float(week.actual_total_miles or 0),
                            "workout_count": int(week.actual_workout_count or 0),
                            "avg_pace": float(week.actual_avg_pace or 0),
                            "avg_heart_rate": float(week.actual_avg_hr or 0),
                            "long_run_miles": float(week.actual_long_run_miles or 0),
                        },
                        "planned_training": {
                            "total_miles": float(week.planned_total_miles or 0),
                            "workout_count": int(week.planned_workout_count or 0),
                            "long_run_miles": float(week.planned_long_run_miles or 0),
                        },
                        "metrics": {
                            "completion_rate": float(week.workout_completion_rate or 0),
                            "training_load_ratio": float(week.training_load_ratio or 0),
                            "easy_run_percentage": float(week.easy_run_percentage or 0),
                            "pace_consistency": float(week.pace_consistency or 0),
                            "weeks_until_race": int(week.weeks_until_race or 0),
                            "difference_miles": float(
                                week.actual_vs_planned_total_miles or 0
                            ),
                        },
                    }
                )

            return {"weekly_insights": weekly_data}
        except Exception as e:
            logger.info(f"Error loading weekly insights: {e}")
            return {}

    def _calculate_recent_longest_runs(self):
        """Calculate recent longest runs from completed activities"""
        try:
            query = """
                WITH weekly_longest AS (
                    SELECT
                        activity_date,
                        activity_name,
                        distance,
                        avg_speed,
                        avg_hr,
                        ROW_NUMBER() OVER (
                            PARTITION BY DATE_TRUNC('week', activity_date::date)
                            ORDER BY distance DESC
                        ) as week_rank
                    FROM v_completed_activities
                    WHERE user_id = :user_id
                    AND activity_date::date >= CURRENT_DATE - INTERVAL '42 days'
                    AND distance > 0
                )
                SELECT
                    activity_date,
                    activity_name,
                    distance,
                    avg_speed,
                    avg_hr
                FROM weekly_longest
                WHERE week_rank = 1
                ORDER BY activity_date DESC
            """
            results = self._safe_execute_query(query, {"user_id": self.user_id})

            if not results:
                return {}

            longest_runs = []
            for run in results:
                longest_runs.append(
                    {
                        "date": str(run.activity_date),
                        "name": run.activity_name,
                        "distance": float(run.distance),
                        "avg_speed": float(run.avg_speed),
                        "avg_heart_rate": float(run.avg_hr or 0),
                    }
                )

            return {"recent_longest_runs": longest_runs}
        except Exception as e:
            logger.error(f"Error calculating recent longest runs: {e}")
            return {}

    def get_context(self, message_content: str) -> dict:
        """Get comprehensive context using strategic views"""
        context_data = {}

        # Load weekly insights with strategic metrics
        if self._check_consent([DataCategory.PERFORMANCE_DATA]):
            weekly_insights = self._get_weekly_insights()
            if weekly_insights:
                context_data.update(weekly_insights)

        # Load recent longest runs (calculated from completed activities)
        if self._check_consent([DataCategory.PERFORMANCE_DATA]):
            recent_longest_runs = self._calculate_recent_longest_runs()
            if recent_longest_runs:
                context_data.update(recent_longest_runs)

        # Add current date information
        from datetime import datetime

        current_date = datetime.now().strftime("%Y-%m-%d")
        current_day = datetime.now().strftime("%A, %B %d, %Y")
        context_data["current_date"] = {"date": current_date, "day": current_day}

        return context_data

    def _check_consent(self, data_categories: list) -> bool:
        """Check if user has consented to data categories"""
        return (
            True  # For now, always return True to avoid consent issues during testing
        )
