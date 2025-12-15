"""
Tests for RaceInfoBuilder submodule of RunnerStateBuilder.

RaceInfoBuilder extracts race information from the active plan.
"""

import pytest
from datetime import date, timedelta
from unittest.mock import Mock, MagicMock, patch

from coach.builders.race_info_builder import RaceInfoBuilder


class TestRaceInfoBuilder:
    """Test RaceInfoBuilder with various scenarios."""

    def test_build_race_info_with_target_time(self):
        """Test building race info when plan has target time."""
        # Mock session and active plan
        mock_session = Mock()
        mock_plan = Mock()
        mock_plan.race_date = date.today() + timedelta(days=90)  # 90 days from now
        mock_plan.race_distance = "Marathon"
        mock_plan.primary_goal = "Target Time"
        mock_plan.target_time = "4:00:00"

        with patch(
            "coach.builders.race_info_builder.get_active_plan", return_value=mock_plan
        ):
            builder = RaceInfoBuilder(mock_session, "test_user_id")
            race_info = builder.build()

            assert race_info["date"] == mock_plan.race_date.isoformat()
            assert race_info["distance"] == "Marathon"
            assert race_info["goal_type"] == "Target Time"
            assert race_info["target_time"] == "4:00:00"

    def test_build_race_info_just_finish(self):
        """Test building race info when goal is Just Finish."""
        mock_session = Mock()
        mock_plan = Mock()
        mock_plan.race_date = date(2025, 6, 15)
        mock_plan.race_distance = "Marathon"
        mock_plan.primary_goal = "Just Finish"
        mock_plan.target_time = None

        with patch(
            "coach.builders.race_info_builder.get_active_plan", return_value=mock_plan
        ):
            builder = RaceInfoBuilder(mock_session, "test_user_id")
            race_info = builder.build()

            assert race_info["date"] == "2025-06-15"
            assert race_info["distance"] == "Marathon"
            assert race_info["goal_type"] == "Just Finish"
            assert (
                "target_time" not in race_info or race_info.get("target_time") is None
            )

    def test_build_race_info_no_active_plan(self):
        """Test building race info when no active plan exists."""
        mock_session = Mock()

        with patch(
            "coach.builders.race_info_builder.get_active_plan", return_value=None
        ):
            builder = RaceInfoBuilder(mock_session, "test_user_id")
            race_info = builder.build()

            # Should return None or empty dict when no plan exists
            assert race_info is None or race_info == {}

    def test_build_race_info_missing_date(self):
        """Test building race info when race_date is None."""
        mock_session = Mock()
        mock_plan = Mock()
        mock_plan.race_date = None
        mock_plan.race_distance = "Marathon"
        mock_plan.primary_goal = "Just Finish"

        with patch(
            "coach.builders.race_info_builder.get_active_plan", return_value=mock_plan
        ):
            builder = RaceInfoBuilder(mock_session, "test_user_id")
            race_info = builder.build()

            # Should handle missing date gracefully
            assert race_info is None or race_info.get("date") is None

    def test_build_race_info_missing_distance(self):
        """Test building race info when race_distance is None."""
        mock_session = Mock()
        mock_plan = Mock()
        mock_plan.race_date = date.today() + timedelta(days=60)
        mock_plan.race_distance = None
        mock_plan.primary_goal = "Just Finish"

        with patch(
            "coach.builders.race_info_builder.get_active_plan", return_value=mock_plan
        ):
            builder = RaceInfoBuilder(mock_session, "test_user_id")
            race_info = builder.build()

            # Should handle missing distance - may return None or use default
            assert (
                race_info is None
                or race_info.get("distance") is None
                or race_info.get("distance") == ""
            )
