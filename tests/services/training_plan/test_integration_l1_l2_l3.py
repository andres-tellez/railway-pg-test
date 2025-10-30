from datetime import datetime, timedelta

import pytest

from src.services.training_plan.data_collection_service import DataCollectionService
from src.services.training_plan.insights_calculation_service import (
    InsightsCalculationService,
)
from src.services.training_plan.prompt_builder_service import PromptBuilderService
from src.db.models.user_profile import UserProfile
from src.db.models.activities import Activity


class TestIntegrationL1L2L3:
    def test_end_to_end_prompt_building(self, test_db_session):
        # Arrange: create a user profile
        user_id = "12345678-1234-5678-1234-567812345678"
        profile = UserProfile(
            user_id=user_id,
            age_group="30-39",
            height_feet=5,
            height_inches=10,
            weight=165.0,
            training_days=["Mon", "Wed", "Fri"],
        )
        test_db_session.add(profile)

        # Create recent run activities (last few weeks)
        base_date = datetime.now()
        runs = [5.0, 6.0, 8.0, 10.0]  # miles
        for i, miles in enumerate(runs):
            a = Activity(
                activity_id=900000 + i,
                athlete_id=42,
                user_id=user_id,
                name=f"Run {i}",
                type="Run",
                start_date=base_date - timedelta(days=i * 3),
                distance=miles * 1609.34,
                conv_distance=miles,
                moving_time=int(miles * 600),
                elapsed_time=int(miles * 610),
                average_heartrate=140 + i,
                average_speed=2.68,
            )
            test_db_session.add(a)

        test_db_session.commit()

        # Plan request 12 weeks out
        plan_request = {
            "race_date": (datetime.now() + timedelta(weeks=12)).strftime("%Y-%m-%d"),
            "primary_goal": "Just Finish",
            "marathon_experience": "First",
            "training_days": ["Mon", "Wed", "Fri"],
        }

        # Act: L1 collect data
        raw = DataCollectionService.collect_all_data(
            test_db_session, user_id, plan_request, activity_weeks=12
        )

        # L2 calculate insights
        insights = InsightsCalculationService.calculate_all_insights(raw)

        # L3 build prompt
        prompt = PromptBuilderService.build_complete_prompt(
            insights, raw["user_profile"], raw["plan_request"]
        )

        # Assert: sanity checks across the flow
        assert raw["user_profile"]["age_group"] == "30-39"
        assert len(raw["strava_activities"]) >= 1

        assert "current_fitness" in insights
        assert "recommendations" in insights
        assert insights["current_fitness"]["weekly_mileage"] >= 0

        assert "messages" in prompt and len(prompt["messages"]) == 2
        system = next(m for m in prompt["messages"] if m["role"] == "system")
        user = next(m for m in prompt["messages"] if m["role"] == "user")

        assert "You are an elite marathon running coach" in system["content"]
        for section in [
            "# RUNNER PROFILE",
            "# RACE GOAL",
            "# CURRENT FITNESS",
            "# TRAINING RECOMMENDATIONS",
            "# SCHEDULE CONSTRAINTS",
            "# YOUR TASK",
            "# OUTPUT FORMAT",
        ]:
            assert section in user["content"]

    def test_end_to_end_with_limited_data_warnings(self, test_db_session):
        # Arrange: create a user profile but no activities
        user_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        profile = UserProfile(
            user_id=user_id,
            age_group="25-29",
            height_feet=5,
            height_inches=7,
            weight=150.0,
            training_days=["Tue", "Thu"],
        )
        test_db_session.add(profile)
        test_db_session.commit()

        # Race date within 8 weeks to trigger time warning
        plan_request = {
            "race_date": (datetime.now() + timedelta(weeks=8)).strftime("%Y-%m-%d"),
            "primary_goal": "Just Finish",
            "marathon_experience": "First",
            "training_days": ["Tue", "Thu"],
        }

        # Act
        raw = DataCollectionService.collect_all_data(
            test_db_session, user_id, plan_request, activity_weeks=12
        )
        insights = InsightsCalculationService.calculate_all_insights(raw)
        prompt = PromptBuilderService.build_complete_prompt(
            insights, raw["user_profile"], raw["plan_request"]
        )

        # Assert: warnings present for time constraint and limited data
        user = next(m for m in prompt["messages"] if m["role"] == "user")
        content = user["content"]
        assert "TIME CONSTRAINT" in content
        assert "LIMITED DATA" in content
        # With no activities, readiness should be false, so base building warning should appear
        assert "BASE BUILDING NEEDED" in content
