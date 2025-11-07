"""
Tests for Layer 2: Insights Calculation Service

Tests all components of the insights calculation layer including:
- Main InsightsCalculationService orchestrator
- Simple calculation functions (fitness_calculator)
- RecommendationsGenerator class
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from src.services.training_plan.insights_calculation_service import (
    InsightsCalculationService,
)
from src.services.training_plan.calculations.fitness_calculator import (
    calculate_weekly_mileage,
    find_longest_run,
    calculate_average_pace,
    calculate_fitness_trend,
)
from src.services.training_plan.calculations.recommendations_generator import (
    RecommendationsGenerator,
)


class TestFitnessCalculator:
    """Tests for simple fitness calculation functions."""

    def test_calculate_weekly_mileage_empty_activities(self):
        """Test weekly mileage calculation with no activities."""
        result = calculate_weekly_mileage([])
        assert result == 0.0

    def test_calculate_weekly_mileage_recent_activities(self):
        """Test weekly mileage calculation with activities in 4 complete weeks."""
        # Create 4 weeks of activity data
        activities = []
        start_date = datetime(2025, 9, 1)  # A Monday
        for week in range(4):
            week_start = start_date + timedelta(weeks=week)
            activities.extend(
                [
                    {
                        "date": (week_start + timedelta(days=0)).strftime("%Y-%m-%d"),
                        "distance": 5.0,
                    },
                    {
                        "date": (week_start + timedelta(days=2)).strftime("%Y-%m-%d"),
                        "distance": 3.0,
                    },
                    {
                        "date": (week_start + timedelta(days=4)).strftime("%Y-%m-%d"),
                        "distance": 2.0,
                    },
                ]
            )

        result = calculate_weekly_mileage(activities)
        # Should return average of 4 weeks: (10+10+10+10)/4 = 10.0
        assert result == 10.0

    def test_calculate_weekly_mileage_last_complete_week(self):
        """Test weekly mileage returns the last complete week's mileage."""
        # Activities spanning multiple complete weeks
        activities = [
            {"date": "2025-10-21", "distance": 5.0},  # Monday of last complete week
            {"date": "2025-10-23", "distance": 3.0},  # Wednesday of last complete week
            {"date": "2025-10-25", "distance": 8.0},  # Friday of last complete week
        ]

        result = calculate_weekly_mileage(activities)
        assert result == 16.0  # Should return the last complete week's mileage

    def test_find_longest_run_empty_activities(self):
        """Test longest run finding with no activities."""
        result = find_longest_run([])
        assert result == 0.0

    def test_find_longest_run_recent_activities(self):
        """Test longest run finding with recent activities."""
        activities = [
            {"date": "2025-10-29", "distance": 5.0},
            {"date": "2025-10-25", "distance": 8.5},
            {
                "date": "2025-10-20",
                "distance": 12.0,
            },  # 9 days ago (included in 2 weeks)
        ]

        result = find_longest_run(activities, weeks=2)
        assert result == 12.0  # Should be 12.0, not 8.5

    def test_calculate_average_pace_empty_activities(self):
        """Test average pace calculation with no activities."""
        result = calculate_average_pace([])
        assert result == "0:00/mile"

    def test_calculate_average_pace_with_activities(self):
        """Test average pace calculation with activities in complete weeks."""
        # Create activities spanning multiple complete weeks
        activities = []
        start_date = datetime(2025, 9, 1)  # A Monday
        for week in range(4):
            week_start = start_date + timedelta(weeks=week)
            activities.extend(
                [
                    {
                        "date": (week_start + timedelta(days=0)).strftime("%Y-%m-%d"),
                        "distance": 5.0,
                        "moving_time": 2400,
                    },  # 8:00/mile
                    {
                        "date": (week_start + timedelta(days=2)).strftime("%Y-%m-%d"),
                        "distance": 3.0,
                        "moving_time": 1800,
                    },  # 10:00/mile
                ]
            )

        result = calculate_average_pace(activities)
        # Should be somewhere between 8:00 and 10:00/mile
        assert ":" in result and "/mile" in result

    def test_calculate_fitness_trend_insufficient_data(self):
        """Test fitness trend with insufficient data."""
        activities = [
            {"date": "2025-10-29", "distance": 5.0},
        ]

        result = calculate_fitness_trend(activities)
        assert result == "Insufficient Data"

    def test_calculate_fitness_trend_improving(self):
        """Test fitness trend showing improvement."""
        # Need activities in complete weeks (Mon-Sun) to properly calculate trend
        # Let's create 8 weeks of gradually improving data
        activities = []
        start_date = datetime(2025, 9, 1)  # A Monday
        for week in range(8):
            week_start = start_date + timedelta(weeks=week)
            # 3 runs per week with increasing total mileage
            base_distance = 5.0 + (week * 0.5)  # Gradual increase
            activities.extend(
                [
                    {
                        "date": (week_start + timedelta(days=0)).strftime("%Y-%m-%d"),
                        "distance": base_distance,
                    },
                    {
                        "date": (week_start + timedelta(days=2)).strftime("%Y-%m-%d"),
                        "distance": base_distance,
                    },
                    {
                        "date": (week_start + timedelta(days=4)).strftime("%Y-%m-%d"),
                        "distance": base_distance,
                    },
                ]
            )

        result = calculate_fitness_trend(activities)
        assert result == "Improving"


class TestRecommendationsGenerator:
    """Tests for RecommendationsGenerator class."""

    def test_generate_recommendations_empty_activities(self):
        """Test recommendations with no activities."""
        generator = RecommendationsGenerator()
        result = generator.generate_recommendations([], {}, {})

        assert result["starting_mileage"]["weekly_mileage"] == 0.0
        assert result["starting_mileage"]["ready_for_marathon"] == False
        assert result["starting_mileage"]["confidence"] == "Low"
        assert result["progression_rate"]["rate_percent"] == 10.0
        assert result["training_frequency"]["runs_per_week"] == 3

    def test_generate_recommendations_with_activities(self):
        """Test recommendations with training history."""
        activities = [
            {"date": "2025-10-29", "distance": 5.0},
            {"date": "2025-10-27", "distance": 5.0},
            {"date": "2025-10-25", "distance": 5.0},
        ]

        user_profile = {"training_days": ["Mon", "Wed", "Fri"]}
        plan_request = {"primary_goal": "Just Finish"}

        generator = RecommendationsGenerator()
        result = generator.generate_recommendations(
            activities, user_profile, plan_request
        )

        assert result["starting_mileage"]["weekly_mileage"] > 0
        assert result["progression_rate"]["rate_percent"] > 0
        assert len(result["focus_areas"]) > 0
        assert result["training_frequency"]["runs_per_week"] > 0
        assert result["long_run_distance"]["distance"] > 0


class TestInsightsCalculationService:
    """Tests for main InsightsCalculationService orchestrator."""

    def test_calculate_all_insights_empty_data(self):
        """Test insights calculation with empty data."""
        raw_data = {"strava_activities": [], "user_profile": {}, "plan_request": {}}

        result = InsightsCalculationService.calculate_all_insights(raw_data)

        assert "current_fitness" in result
        assert "recommendations" in result
        assert "metadata" in result

        assert result["current_fitness"]["weekly_mileage"] == 0.0

    def test_calculate_all_insights_with_data(self):
        """Test insights calculation with real data."""
        raw_data = {
            "strava_activities": [
                {"date": "2025-10-29", "distance": 5.0, "moving_time": 2400},
                {"date": "2025-10-27", "distance": 5.0, "moving_time": 2400},
                {"date": "2025-10-25", "distance": 5.0, "moving_time": 2400},
            ],
            "user_profile": {
                "age_group": "30-39",
                "training_days": ["Mon", "Wed", "Fri"],
            },
            "plan_request": {
                "primary_goal": "Just Finish",
            },
        }

        result = InsightsCalculationService.calculate_all_insights(raw_data)

        # Verify all sections are present
        assert "current_fitness" in result
        assert "recommendations" in result
        assert "metadata" in result

        # Verify data quality
        assert result["current_fitness"]["weekly_mileage"] > 0
        assert result["recommendations"]["starting_mileage"]["weekly_mileage"] > 0

    def test_calculate_all_insights_missing_data(self):
        """Test insights calculation with missing required data."""
        # Missing strava_activities
        raw_data = {"user_profile": {}, "plan_request": {}}

        with pytest.raises(
            ValueError, match="Invalid raw_data: missing strava_activities"
        ):
            InsightsCalculationService.calculate_all_insights(raw_data)

    def test_calculate_all_insights_none_data(self):
        """Test insights calculation with None data."""
        with pytest.raises(
            ValueError, match="Invalid raw_data: missing strava_activities"
        ):
            InsightsCalculationService.calculate_all_insights(None)


class TestIntegrationScenarios:
    """Integration tests for realistic scenarios."""

    def test_beginner_runner_scenario(self):
        """Test insights for a beginner runner."""
        raw_data = {
            "strava_activities": [
                {"date": "2025-10-29", "distance": 3.0, "moving_time": 1800},
                {"date": "2025-10-26", "distance": 2.5, "moving_time": 1500},
                {"date": "2025-10-23", "distance": 2.0, "moving_time": 1200},
            ],
            "user_profile": {
                "age_group": "25-29",
                "training_days": ["Tue", "Thu", "Sat"],
            },
            "plan_request": {
                "primary_goal": "Just Finish",
            },
        }

        result = InsightsCalculationService.calculate_all_insights(raw_data)

        # Should recommend conservative starting points
        assert result["recommendations"]["starting_mileage"]["confidence"] in [
            "Low",
            "Medium",
        ]
        assert "Base Building" in result["recommendations"]["focus_areas"]
        assert "Marathon Education" in result["recommendations"]["focus_areas"]

    def test_experienced_runner_scenario(self):
        """Test insights for an experienced runner."""
        raw_data = {
            "strava_activities": [
                {"date": "2025-10-29", "distance": 8.0, "moving_time": 3600},
                {"date": "2025-10-27", "distance": 6.0, "moving_time": 2700},
                {"date": "2025-10-25", "distance": 10.0, "moving_time": 4500},
                {"date": "2025-10-23", "distance": 5.0, "moving_time": 2250},
                {"date": "2025-10-21", "distance": 7.0, "moving_time": 3150},
                {"date": "2025-10-19", "distance": 6.0, "moving_time": 2700},
            ],
            "user_profile": {
                "age_group": "35-39",
                "training_days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
            },
            "plan_request": {
                "primary_goal": "Target Time",
            },
        }

        result = InsightsCalculationService.calculate_all_insights(raw_data)

        # Should recommend higher starting points
        assert result["recommendations"]["starting_mileage"]["confidence"] in [
            "High",
            "Medium",
        ]
        assert (
            "Marathon Preparation" in result["recommendations"]["focus_areas"]
            or "Mileage Building" in result["recommendations"]["focus_areas"]
        )  # Adjusted expectation
        assert "Pace Training" in result["recommendations"]["focus_areas"]

    def test_inconsistent_runner_scenario(self):
        """Test insights for an inconsistent runner."""
        raw_data = {
            "strava_activities": [
                {"date": "2025-10-29", "distance": 10.0, "moving_time": 4500},
                {"date": "2025-10-20", "distance": 2.0, "moving_time": 1200},
                {"date": "2025-10-10", "distance": 8.0, "moving_time": 3600},
                {"date": "2025-10-01", "distance": 1.0, "moving_time": 600},
            ],
            "user_profile": {
                "age_group": "40-44",
                "training_days": ["Mon", "Wed", "Fri"],
            },
            "plan_request": {
                "primary_goal": "Just Finish",
            },
        }

        result = InsightsCalculationService.calculate_all_insights(raw_data)

        # Should recommend building consistency and base
        assert (
            "Consistency" in result["recommendations"]["focus_areas"]
            or "Base Building" in result["recommendations"]["focus_areas"]
        )
