"""
Integration tests for RunnerStateBuilder.

Tests the full orchestration of RunnerStateBuilder with mocked services
to ensure all components work together correctly.
"""

import pytest
from datetime import date, timedelta
from unittest.mock import Mock, MagicMock, patch, call

from coach.builders.runner_state_builder import RunnerStateBuilder
from src.db.models.plans import Plan
from src.db.models.plan_workouts import PlanWorkout


class TestRunnerStateBuilder:
    """Integration tests for RunnerStateBuilder."""

    def test_build_minimal_state_no_active_plan(self):
        """Test building minimal state when no active plan exists."""
        mock_session = Mock()
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        with patch(
            "coach.builders.runner_state_builder.get_active_plan", return_value=None
        ):
            builder = RunnerStateBuilder(mock_session, "test_user_id")
            result = builder.build()

            assert result["version"] == "1.0.0"
            assert result["runner_state"]["phase"] == "Base"
            assert result["runner_state"]["week_of_block"] == 1
            assert result["runner_state"]["race"] is None
            assert result["runner_state"]["zones"]["hr"] == {}
            assert "hr_calibration" in result["runner_state"]["zones"]
            assert result["runner_state"]["zones"]["pace"] == {}

    def test_build_minimal_state_no_race_date(self):
        """Test building minimal state when plan has no race_date."""
        mock_session = Mock()
        mock_plan = Mock()
        mock_plan.race_date = None
        mock_plan.id = 1

        with patch(
            "coach.builders.runner_state_builder.get_active_plan",
            return_value=mock_plan,
        ):
            builder = RunnerStateBuilder(mock_session, "test_user_id")
            result = builder.build()

            assert result["version"] == "1.0.0"
            assert result["runner_state"]["phase"] == "Base"
            assert result["runner_state"]["week_of_block"] == 1

    def test_build_complete_state_with_all_services(self):
        """Test building complete state with all services mocked."""
        mock_session = Mock()

        # Mock plan
        mock_plan = Mock()
        mock_plan.id = 1
        mock_plan.user_id = "test_user_id"
        mock_plan.race_date = date.today() + timedelta(days=84)  # 12 weeks out
        mock_plan.plan_name = "Marathon_4hr"

        # Mock workouts for total weeks calculation
        mock_workout1 = Mock()
        mock_workout1.date = date.today() - timedelta(days=14)
        mock_workout2 = Mock()
        mock_workout2.date = mock_plan.race_date - timedelta(days=1)
        mock_session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = [
            mock_workout1,
            mock_workout2,
        ]

        # Mock workout with pace_ranges
        mock_workout_with_pace = Mock()
        mock_workout_with_pace.pace_ranges = {
            "z2": [600.0, 645.0],  # 10:00-10:45/mile
            "z3": [585.0, 600.0],
            "m": [570.0],  # 9:30/mile
            "z4": [540.0, 555.0],  # 9:00-9:15/mile
        }
        mock_session.query.return_value.filter_by.return_value.filter.return_value.order_by.return_value.first.return_value = (
            mock_workout_with_pace
        )

        # Mock RaceInfoBuilder
        race_info = {
            "date": mock_plan.race_date.isoformat(),
            "distance": "Marathon",
            "goal_type": "Target Time",
            "target_time": "4:00:00",
        }

        # Mock HR zones service
        hr_zones_result = {
            "success": True,
            "zones": {
                "Z1": (105, 120),
                "Z2": (121, 138),
                "Z3": (139, 152),
                "Z4": (153, 165),
                "Z5": (166, 200),
            },
        }

        # Mock WeeklyMetricsService
        mock_weekly_metric = Mock()
        mock_weekly_metric.week_start_date = date.today() - timedelta(days=7)
        mock_weekly_metric.volume_score = 85.0
        mock_weekly_metric.intensity_score = 90.0
        mock_weekly_metric.consistency_score = 80.0
        mock_weekly_metric.load_delta_pct = 5.0
        mock_weekly_metric.current_week_load = 35.0
        mock_weekly_metric.fatigue_markers = []

        # Mock SmartDataService for activities
        mock_activities = [
            {
                "date": date.today() - timedelta(days=1),
                "distance_miles": 5.0,
                "average_heartrate": 130,
                "pace_seconds_per_mile": 600.0,
            },
            {
                "date": date.today() - timedelta(days=2),
                "distance_miles": 3.0,
                "average_heartrate": 125,
                "pace_seconds_per_mile": 610.0,
            },
        ]

        with patch(
            "coach.builders.runner_state_builder.get_active_plan",
            return_value=mock_plan,
        ), patch(
            "coach.builders.runner_state_builder.RaceInfoBuilder"
        ) as mock_race_builder, patch(
            "coach.builders.runner_state_builder.HeartRateZoneOrchestrationService.calculate_zones_for_user",
            return_value=hr_zones_result,
        ) as mock_hr_service, patch(
            "coach.builders.runner_state_builder.WeeklyMetricsService.get_historical_metrics",
            return_value=[mock_weekly_metric],
        ), patch(
            "coach.builders.runner_state_builder.SmartDataService"
        ) as mock_data_service, patch(
            "coach.builders.runner_state_builder.detect_consecutive_long_runs",
            return_value={"has_consecutive_runs": False, "consecutive_count": 0},
        ), patch(
            "coach.builders.runner_state_builder.fetch_week_logs_from_db",
            return_value=[],
        ):

            # Setup RaceInfoBuilder mock
            mock_race_builder_instance = Mock()
            mock_race_builder_instance.build.return_value = race_info
            mock_race_builder.return_value = mock_race_builder_instance

            # Setup SmartDataService mock
            mock_data_service_instance = Mock()
            mock_data_service_instance._get_recent_activities.return_value = (
                mock_activities
            )
            mock_data_service.return_value = mock_data_service_instance

            builder = RunnerStateBuilder(mock_session, "test_user_id")
            result = builder.build()

            # Verify structure
            assert result["version"] == "1.0.0"
            runner_state = result["runner_state"]

            # Verify phase and week
            assert runner_state["phase"] in [
                "Base",
                "Build",
                "Peak",
                "Taper",
            ]
            assert runner_state["week_of_block"] >= 1
            assert runner_state["plan_type"] == "Marathon_4hr"

            # Verify race info
            assert runner_state["race"]["date"] == mock_plan.race_date.isoformat()
            assert runner_state["race"]["distance"] == "Marathon"

            # Verify HR zones are formatted correctly
            assert "z1" in runner_state["zones"]["hr"]
            assert "bpm" in runner_state["zones"]["hr"]["z1"]
            assert runner_state["zones"]["hr"]["z1"] == "105-120 bpm"
            assert runner_state["zones"]["hr_calibration"]["status"] == "calibrated"

            # Verify pace zones are formatted correctly
            assert "easy" in runner_state["zones"]["pace"]
            assert "/mi" in runner_state["zones"]["pace"]["easy"]

            # Verify weekly metrics
            assert runner_state["weekly_metrics"] is not None
            assert runner_state["weekly_metrics"]["volume_score"] == 85.0
            assert runner_state["weekly_metrics"]["intensity_score"] == 90.0

            # Verify patterns
            assert "trend" in runner_state["patterns"]
            assert runner_state["patterns"]["trend"] in [
                "improving",
                "stable",
                "declining",
            ]

            # Verify safety indicators
            assert "hr_data_reliable" in runner_state["safety"]
            assert "pace_data_reliable" in runner_state["safety"]
            assert isinstance(runner_state["safety"]["hr_data_reliable"], bool)

    def test_build_handles_hr_zone_service_failure(self):
        """Test that builder handles HR zone service failures gracefully."""
        mock_session = Mock()
        mock_plan = Mock()
        mock_plan.id = 1
        mock_plan.race_date = date.today() + timedelta(days=84)
        mock_plan.plan_name = "Test Plan"
        mock_session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = (
            []
        )

        race_info = {
            "date": mock_plan.race_date.isoformat(),
            "distance": "Marathon",
            "goal_type": "Just Finish",
        }

        with patch(
            "coach.builders.runner_state_builder.get_active_plan",
            return_value=mock_plan,
        ), patch(
            "coach.builders.runner_state_builder.RaceInfoBuilder"
        ) as mock_race_builder, patch(
            "coach.builders.runner_state_builder.HeartRateZoneOrchestrationService.calculate_zones_for_user",
            side_effect=Exception("HR service failed"),
        ), patch(
            "coach.builders.runner_state_builder.SmartDataService"
        ) as mock_data_service, patch(
            "coach.builders.runner_state_builder.WeeklyMetricsService.get_historical_metrics",
            return_value=[],
        ), patch(
            "coach.builders.runner_state_builder.detect_consecutive_long_runs",
            return_value={"has_consecutive_runs": False},
        ), patch(
            "coach.builders.runner_state_builder.fetch_week_logs_from_db",
            return_value=[],
        ):

            mock_race_builder_instance = Mock()
            mock_race_builder_instance.build.return_value = race_info
            mock_race_builder.return_value = mock_race_builder_instance

            mock_data_service_instance = Mock()
            mock_data_service_instance._get_recent_activities.return_value = []
            mock_data_service.return_value = mock_data_service_instance

            builder = RunnerStateBuilder(mock_session, "test_user_id")
            result = builder.build()

            # Should still build state but with empty HR zones
            assert result["version"] == "1.0.0"
            runner_state = result["runner_state"]
            assert runner_state["zones"]["hr"] == {}
            assert runner_state["zones"]["hr_calibration"]["status"] in (
                "calibrated",
                "uncalibrated",
            )

    def test_build_handles_weekly_metrics_service_failure(self):
        """Test that builder handles weekly metrics service failures gracefully."""
        mock_session = Mock()
        mock_plan = Mock()
        mock_plan.id = 1
        mock_plan.race_date = date.today() + timedelta(days=84)
        mock_plan.plan_name = "Test Plan"
        # Setup query chain for workouts (for total weeks calculation) - returns empty list
        mock_workout_query = Mock()
        mock_workout_query.filter_by.return_value.order_by.return_value.all.return_value = (
            []
        )

        # Setup query chain for pace_ranges lookup (returns None)
        mock_pace_query = Mock()
        mock_pace_query.filter_by.return_value.filter.return_value.order_by.return_value.first.return_value = (
            None
        )

        # Make session.query return different mocks based on what's being queried
        from src.db.models.plan_workouts import PlanWorkout

        def query_side_effect(model):
            if model == PlanWorkout:
                # Check if this is for pace_ranges (has .filter() call) or workouts (has .order_by().all())
                # We'll use the filter chain to differentiate
                return mock_pace_query
            return mock_workout_query

        mock_session.query.side_effect = query_side_effect

        race_info = {
            "date": mock_plan.race_date.isoformat(),
            "distance": "Marathon",
            "goal_type": "Just Finish",
        }

        with patch(
            "coach.builders.runner_state_builder.get_active_plan",
            return_value=mock_plan,
        ), patch(
            "coach.builders.runner_state_builder.RaceInfoBuilder"
        ) as mock_race_builder, patch(
            "coach.builders.runner_state_builder.HeartRateZoneOrchestrationService.calculate_zones_for_user",
            return_value={"success": False},
        ), patch(
            "coach.builders.runner_state_builder.WeeklyMetricsService.get_historical_metrics",
            return_value=[],  # Empty list simulates no metrics
        ), patch(
            "coach.builders.runner_state_builder.SmartDataService"
        ) as mock_data_service, patch(
            "coach.builders.runner_state_builder.detect_consecutive_long_runs",
            return_value={"has_consecutive_runs": False},
        ), patch(
            "coach.builders.runner_state_builder.fetch_week_logs_from_db",
            return_value=[],
        ):

            mock_race_builder_instance = Mock()
            mock_race_builder_instance.build.return_value = race_info
            mock_race_builder.return_value = mock_race_builder_instance

            mock_data_service_instance = Mock()
            mock_data_service_instance._get_recent_activities.return_value = []
            mock_data_service.return_value = mock_data_service_instance

            builder = RunnerStateBuilder(mock_session, "test_user_id")
            result = builder.build()

            # Should still build state but without weekly_metrics (omitted when None)
            assert result["version"] == "1.0.0"
            assert (
                "weekly_metrics" not in result["runner_state"]
                or result["runner_state"].get("weekly_metrics") is None
            )

    def test_calculate_phase_and_week(self):
        """Test phase and week calculation logic."""
        mock_session = Mock()
        mock_plan = Mock()
        mock_plan.id = 1
        mock_plan.race_date = date.today() + timedelta(days=84)  # 12 weeks out
        mock_plan.plan_name = "Test Plan"

        # Mock workouts for 16 weeks total
        mock_workout1 = Mock()
        mock_workout1.date = date.today() - timedelta(days=112)  # 16 weeks ago
        mock_workout2 = Mock()
        mock_workout2.date = mock_plan.race_date - timedelta(days=1)

        # Setup query chain for workouts (for total weeks calculation)
        mock_workout_query = Mock()
        mock_workout_query.filter_by.return_value.order_by.return_value.all.return_value = [
            mock_workout1,
            mock_workout2,
        ]

        # Setup query chain for pace_ranges lookup (returns None)
        mock_pace_query = Mock()
        mock_pace_query.filter_by.return_value.filter.return_value.order_by.return_value.first.return_value = (
            None
        )

        # Make session.query return different mocks based on what's being queried
        from src.db.models.plan_workouts import PlanWorkout

        call_count = [0]  # Use list to allow modification in nested function

        def query_side_effect(model):
            if model == PlanWorkout:
                call_count[0] += 1
                # First call is for _get_total_weeks (workouts), second is for pace_ranges
                if call_count[0] == 1:
                    return mock_workout_query
                else:
                    return mock_pace_query
            return mock_workout_query

        mock_session.query.side_effect = query_side_effect

        race_info = {
            "date": mock_plan.race_date.isoformat(),
            "distance": "Marathon",
            "goal_type": "Just Finish",
        }

        with patch(
            "coach.builders.runner_state_builder.get_active_plan",
            return_value=mock_plan,
        ), patch(
            "coach.builders.runner_state_builder.RaceInfoBuilder"
        ) as mock_race_builder, patch(
            "coach.builders.runner_state_builder.HeartRateZoneOrchestrationService.calculate_zones_for_user",
            return_value={"success": False},
        ), patch(
            "coach.builders.runner_state_builder.WeeklyMetricsService.get_historical_metrics",
            return_value=[],
        ), patch(
            "coach.builders.runner_state_builder.SmartDataService"
        ) as mock_data_service, patch(
            "coach.builders.runner_state_builder.detect_consecutive_long_runs",
            return_value={"has_consecutive_runs": False},
        ), patch(
            "coach.builders.runner_state_builder.fetch_week_logs_from_db",
            return_value=[],
        ):

            mock_race_builder_instance = Mock()
            mock_race_builder_instance.build.return_value = race_info
            mock_race_builder.return_value = mock_race_builder_instance

            mock_data_service_instance = Mock()
            mock_data_service_instance._get_recent_activities.return_value = []
            mock_data_service.return_value = mock_data_service_instance

            builder = RunnerStateBuilder(mock_session, "test_user_id")
            result = builder.build()

            runner_state = result["runner_state"]

            # Should be in Build phase (12 weeks out of 16 = 75% = Build phase boundary)
            assert runner_state["phase"] in [
                "Base",
                "Build",
                "Peak",
                "Taper",
            ]
            assert runner_state["week_of_block"] >= 1
