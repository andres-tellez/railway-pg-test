"""
Integration tests for QuestionContextBuilder.

Tests the full orchestration of QuestionContextBuilder with mocked services
to ensure intent-specific context is built correctly.
"""

import pytest
from datetime import date, timedelta
from unittest.mock import Mock, MagicMock, patch

from coach.builders.question_context_builder import QuestionContextBuilder


class TestQuestionContextBuilder:
    """Integration tests for QuestionContextBuilder."""

    def test_build_workout_review_context(self):
        """Test building context for workout_review intent."""
        mock_session = Mock()

        # Mock activity data
        mock_activity = {
            "date": date.today().isoformat(),
            "distance_miles": 8.5,
            "pace_seconds_per_mile": 600.0,  # 10:00/mile
            "average_heartrate": 145,
            "hr_zone1": 5.0,
            "hr_zone2": 60.0,
            "hr_zone3": 35.0,
        }

        with patch(
            "coach.builders.question_context_builder.SmartDataService"
        ) as mock_data_service, patch(
            "coach.builders.question_context_builder.get_active_plan",
            return_value=None,
        ):
            mock_data_service_instance = Mock()
            mock_data_service_instance._get_recent_activities.return_value = [
                mock_activity
            ]
            mock_data_service.return_value = mock_data_service_instance

            builder = QuestionContextBuilder(mock_session, "test_user_id")
            result = builder.build("How did my long run go?")

            assert result["version"] == "1.0.0"
            question_context = result["question_context"]
            assert question_context["intent"] == "workout_review"
            assert "workout_review" in question_context
            assert "activity" in question_context["workout_review"]
            assert (
                question_context["workout_review"]["activity"]["distance_miles"] == 8.5
            )
            assert "avg_pace" in question_context["workout_review"]["activity"]

    def test_build_this_week_plan_context(self):
        """Test building context for this_week_plan intent."""
        mock_session = Mock()

        # Mock plan
        mock_plan = Mock()
        mock_plan.id = 1
        mock_plan.race_date = date.today() + timedelta(days=84)  # 12 weeks out

        # Mock workout
        mock_workout = Mock()
        mock_workout.date = date.today()
        mock_workout.workout_type = "Easy Run"
        mock_workout.miles = 5.0
        mock_workout.target_zone = "9:00-10:00/mile"
        mock_workout.description = "Easy recovery run"

        mock_session.query.return_value.filter_by.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
            mock_workout
        ]

        with patch(
            "coach.builders.question_context_builder.get_active_plan",
            return_value=mock_plan,
        ):
            builder = QuestionContextBuilder(mock_session, "test_user_id")
            result = builder.build("What's my plan for this week?")

            assert result["version"] == "1.0.0"
            question_context = result["question_context"]
            assert question_context["intent"] == "this_week_plan"
            assert "this_week_plan" in question_context
            assert "current_week" in question_context["this_week_plan"]
            assert "workouts" in question_context["this_week_plan"]["current_week"]

    def test_build_progress_check_context(self):
        """Test building context for progress_check intent."""
        mock_session = Mock()

        # Mock activities
        mock_activities = [
            {
                "date": (date.today() - timedelta(days=i)).isoformat(),
                "distance_miles": 5.0,
            }
            for i in range(7)
        ]

        with patch(
            "coach.builders.question_context_builder.SmartDataService"
        ) as mock_data_service:
            mock_data_service_instance = Mock()
            mock_data_service_instance._get_recent_activities.return_value = (
                mock_activities
            )
            mock_data_service.return_value = mock_data_service_instance

            builder = QuestionContextBuilder(mock_session, "test_user_id")
            result = builder.build("How am I doing?")

            assert result["version"] == "1.0.0"
            question_context = result["question_context"]
            assert question_context["intent"] == "progress_check"
            assert "progress_check" in question_context

    def test_build_injury_context_with_safety_flags(self):
        """Test building context for injury_or_symptom intent with safety flags."""
        mock_session = Mock()

        with patch(
            "coach.builders.question_context_builder.SafetyScanner"
        ) as mock_safety_scanner:
            mock_safety_scanner_instance = Mock()
            mock_safety_scanner_instance.scan_for_schema.return_value = {
                "version": "1.0.0",
                "safety_flags": {
                    "has_medical_red_flag": True,
                    "flags": ["chest pain", "dizziness"],
                    "severity": "critical",
                },
            }
            mock_safety_scanner.return_value = mock_safety_scanner_instance

            builder = QuestionContextBuilder(mock_session, "test_user_id")
            result = builder.build("I'm experiencing chest pain when running")

            assert result["version"] == "1.0.0"
            question_context = result["question_context"]
            assert question_context["intent"] == "injury_or_symptom"
            assert "injury_or_symptom" in question_context
            assert "safety_flags" in question_context["injury_or_symptom"]
            assert len(question_context["injury_or_symptom"]["safety_flags"]) > 0

    def test_build_motivation_context(self):
        """Test building context for motivation_support intent."""
        mock_session = Mock()

        # Mock activities
        mock_activities = [
            {
                "date": (date.today() - timedelta(days=i)).isoformat(),
                "distance_miles": 3.0,
            }
            for i in range(10)
        ]

        with patch(
            "coach.builders.question_context_builder.SmartDataService"
        ) as mock_data_service:
            mock_data_service_instance = Mock()
            mock_data_service_instance._get_recent_activities.return_value = (
                mock_activities
            )
            mock_data_service.return_value = mock_data_service_instance

            builder = QuestionContextBuilder(mock_session, "test_user_id")
            result = builder.build("I need motivation to keep going")

            assert result["version"] == "1.0.0"
            question_context = result["question_context"]
            assert question_context["intent"] == "motivation_support"
            assert "motivation_support" in question_context

    def test_build_general_education_context(self):
        """Test building context for general_education intent."""
        mock_session = Mock()

        builder = QuestionContextBuilder(mock_session, "test_user_id")
        result = builder.build("What is VO2 max?")

        assert result["version"] == "1.0.0"
        question_context = result["question_context"]
        assert question_context["intent"] == "general_education"
        assert "general_education" in question_context

    def test_handles_empty_activities_gracefully(self):
        """Test that builder handles empty activity lists gracefully."""
        mock_session = Mock()

        with patch(
            "coach.builders.question_context_builder.SmartDataService"
        ) as mock_data_service, patch(
            "coach.builders.question_context_builder.get_active_plan",
            return_value=None,
        ):
            mock_data_service_instance = Mock()
            mock_data_service_instance._get_recent_activities.return_value = []
            mock_data_service.return_value = mock_data_service_instance

            builder = QuestionContextBuilder(mock_session, "test_user_id")
            result = builder.build("How did my run go?")

            # Should still return valid context even with no activities
            assert result["version"] == "1.0.0"
            question_context = result["question_context"]
            assert question_context["intent"] == "workout_review"
            # workout_review context may be empty but should exist
            assert "workout_review" in question_context

    def test_handles_errors_gracefully(self):
        """Test that builder handles errors and returns fallback context."""
        mock_session = Mock()

        # Force an error in intent classification
        with patch(
            "coach.builders.question_context_builder.IntentClassifier"
        ) as mock_classifier:
            mock_classifier_instance = Mock()
            mock_classifier_instance.classify.side_effect = Exception(
                "Classification failed"
            )
            mock_classifier.return_value = mock_classifier_instance

            builder = QuestionContextBuilder(mock_session, "test_user_id")
            result = builder.build("Test question")

            # Should return fallback context
            assert result["version"] == "1.0.0"
            question_context = result["question_context"]
            assert question_context["intent"] == "general_education"  # Fallback intent

    def test_schema_validation(self):
        """Test that output validates against QuestionContext schema."""
        mock_session = Mock()

        with patch(
            "coach.builders.question_context_builder.SmartDataService"
        ) as mock_data_service:
            mock_data_service_instance = Mock()
            mock_data_service_instance._get_recent_activities.return_value = []
            mock_data_service.return_value = mock_data_service_instance

            builder = QuestionContextBuilder(mock_session, "test_user_id")
            result = builder.build("What's my plan this week?")

            # Should pass schema validation (handled internally, but verify structure)
            assert result["version"] == "1.0.0"
            assert "question_context" in result
            assert "intent" in result["question_context"]
