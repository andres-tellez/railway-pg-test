"""
Layer 2: Insights Calculation Service

Purpose:
    Transform raw data from Layer 1 into actionable insights for training plan generation.
    This layer applies running coaching expertise to analyze user's fitness, patterns, and safety.

Responsibilities:
    - Calculate current fitness metrics
    - Analyze training consistency patterns
    - Assess injury and overtraining risks
    - Generate safe recommendations for starting points

Dependencies:
    - Layer 1 output (raw data package)
    - Running coaching principles (10% rule, injury prevention, etc.)

Testing:
    See tests/services/training_plan/test_insights_calculation_service.py

Author: SmartCoach Development Team
Last Updated: October 29, 2025
"""

import logging
from typing import Dict, List, Any
from datetime import datetime

from .calculations.fitness_calculator import (
    calculate_weekly_mileage,
    find_longest_run,
    calculate_average_pace,
    calculate_fitness_trend,
)
from .calculations.recommendations_generator import RecommendationsGenerator

logger = logging.getLogger(__name__)


class InsightsCalculationService:
    """
    Main service that orchestrates all insight calculations.

    Takes raw data from Layer 1 and transforms it into actionable insights
    that can be used by Layer 3 (Prompt Builder) and Layer 4 (GPT Coach).
    """

    @staticmethod
    def calculate_all_insights(raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate all insights from raw data.

        Args:
            raw_data: Complete data package from Layer 1 containing:
                - user_profile: User demographic and preference information
                - strava_activities: Historical running activity data
                - plan_request: The original plan request parameters
                - metadata: Collection metadata

        Returns:
            Complete insights package containing:
                - current_fitness: Current fitness level metrics
                - recommendations: Safe starting points and progression
                - metadata: Calculation metadata (timestamp, counts, data quality)

        Raises:
            ValueError: If required data is missing or invalid

        Example:
            >>> insights = InsightsCalculationService.calculate_all_insights(raw_data)
            >>> print(insights["current_fitness"]["weekly_mileage"])
            25.3
        """
        logger.info("Starting insights calculation")

        # Validate input data
        if not raw_data or "strava_activities" not in raw_data:
            raise ValueError("Invalid raw_data: missing strava_activities")

        activities = raw_data["strava_activities"]
        user_profile = raw_data.get("user_profile", {})
        plan_request = raw_data.get("plan_request", {})

        logger.debug(
            f"Processing {len(activities)} activities for insights calculation"
        )

        # Calculate current fitness metrics (simple functions)
        current_fitness = InsightsCalculationService._calculate_current_fitness(
            activities
        )

        # Generate recommendations (complex class)
        recommendations_generator = RecommendationsGenerator()
        recommendations = recommendations_generator.generate_recommendations(
            activities, user_profile, plan_request
        )

        # Combine all insights - only what GPT needs
        insights = {
            "current_fitness": current_fitness,
            "recommendations": recommendations,
            "metadata": {
                "calculated_at": datetime.now().isoformat(),
                "activities_analyzed": len(activities),
                "weeks_analyzed": InsightsCalculationService._get_analysis_period_weeks(
                    activities
                ),
                "data_quality": "sufficient" if len(activities) >= 10 else "limited",
            },
        }

        logger.info(
            f"Insights calculation complete: {len(activities)} activities analyzed"
        )
        return insights

    @staticmethod
    def _calculate_current_fitness(activities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate current fitness metrics using simple functions."""
        if not activities:
            return {
                "weekly_mileage": 0.0,
                "longest_run": 0.0,
                "average_pace": 0.0,
                "fitness_trend": "Unknown",
            }

        return {
            "weekly_mileage": calculate_weekly_mileage(activities),
            "longest_run": find_longest_run(activities),
            "average_pace": calculate_average_pace(activities),
            "fitness_trend": calculate_fitness_trend(activities),
        }

    @staticmethod
    def _get_analysis_period_weeks(activities: List[Dict[str, Any]]) -> int:
        """Calculate the analysis period in weeks."""
        if not activities:
            return 0

        # Get date range
        dates = [
            datetime.strptime(a["date"], "%Y-%m-%d")
            for a in activities
            if a.get("date")
        ]
        if not dates:
            return 0

        earliest = min(dates)
        latest = max(dates)
        days_diff = (latest - earliest).days
        weeks = max(1, days_diff // 7)

        return weeks
