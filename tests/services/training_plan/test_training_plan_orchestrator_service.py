"""
Tests for Training Plan Orchestrator Service

Tests the complete end-to-end flow through all 6 layers.
"""

import json
import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.services.training_plan.training_plan_orchestrator_service import (
    TrainingPlanOrchestratorService,
)
from src.services.training_plan.data_collection_service import DataCollectionService
from src.services.training_plan.insights_calculation_service import (
    InsightsCalculationService,
)
from src.services.training_plan.prompt_builder_service import PromptBuilderService
from src.services.training_plan.gpt_coach_service import GptCoachService
from src.services.training_plan.plan_validation_service import PlanValidationService
from src.services.training_plan.plan_storage_service import PlanStorageService
from src.db.models.user_identity import UserIdentity
from src.db.models.plans import Plan


def _sample_plan_request():
    """Create a sample plan request."""
    race_date = (datetime.now() + timedelta(weeks=16)).strftime("%Y-%m-%d")
    return {
        "race_date": race_date,
        "race_distance": "Marathon",
        "race_name": "Test Marathon",
        "race_location": "Test City",
        "primary_goal": "Just Finish",
        "marathon_experience": "First",
        "target_time": "4:00:00",
        "training_days": ["Mon", "Wed", "Sat"],
        "notes": "Test plan",
    }


def _mock_generated_plan():
    """Create a mock generated plan from Layer 4."""
    return {
        "plan_name": "16 Week Marathon Plan",
        "plan_summary": "Test plan",
        "weeks": [
            {
                "week_number": 1,
                "phase": "Base Building",
                "weekly_mileage": 20.0,
                "workouts": [
                    {
                        "day": "Monday",
                        "workout_type": "Easy Run",
                        "distance_miles": 3.0,
                        "pace_guidance": "Easy",
                        "workout_description": "Easy 3 mile run",
                    }
                ],
            }
        ],
    }


class TestTrainingPlanOrchestratorService:
    def test_create_default(self):
        """Test that create_default returns a working orchestrator."""
        orchestrator = TrainingPlanOrchestratorService.create_default()
        assert orchestrator is not None
        assert orchestrator.data_collection_service is not None
        assert orchestrator.insights_calculation_service is not None
        assert orchestrator.prompt_builder_service is not None
        assert orchestrator.gpt_coach_service is not None
        assert orchestrator.plan_validation_service is not None
        assert orchestrator.plan_storage_service is not None

    def test_dependency_injection(self):
        """Test that services can be injected."""
        mock_l1 = Mock(spec=DataCollectionService)
        mock_l2 = Mock(spec=InsightsCalculationService)
        mock_l3 = Mock(spec=PromptBuilderService)
        mock_l4 = Mock(spec=GptCoachService)
        mock_l5 = Mock(spec=PlanValidationService)
        mock_l6 = Mock(spec=PlanStorageService)

        orchestrator = TrainingPlanOrchestratorService(
            data_collection_service=mock_l1,
            insights_calculation_service=mock_l2,
            prompt_builder_service=mock_l3,
            gpt_coach_service=mock_l4,
            plan_validation_service=mock_l5,
            plan_storage_service=mock_l6,
        )

        assert orchestrator.data_collection_service is mock_l1
        assert orchestrator.insights_calculation_service is mock_l2
        assert orchestrator.prompt_builder_service is mock_l3
        assert orchestrator.gpt_coach_service is mock_l4
        assert orchestrator.plan_validation_service is mock_l5
        assert orchestrator.plan_storage_service is mock_l6

    def test_generate_training_plan_happy_path(self, test_db_session):
        """Test successful end-to-end plan generation with mocked layers."""
        # Setup: Create user
        user_id = uuid.uuid4()
        test_db_session.add(UserIdentity(user_id=user_id, email="test@example.com"))
        test_db_session.commit()

        # Create mocks for each layer
        mock_l1 = Mock(spec=DataCollectionService)
        mock_l1.collect_all_data.return_value = {
            "user_profile": {"age_group": "30-39"},
            "strava_activities": [],
            "plan_request": _sample_plan_request(),
            "metadata": {},
        }

        mock_l2 = Mock(spec=InsightsCalculationService)
        mock_l2.calculate_all_insights.return_value = {
            "current_fitness": {},
            "recommendations": {},
            "metadata": {},
        }

        mock_l3 = Mock(spec=PromptBuilderService)
        mock_l3.build_complete_prompt.return_value = {
            "messages": [{"role": "system", "content": "test"}],
            "config": {},
        }

        mock_l4 = Mock(spec=GptCoachService)
        mock_l4.generate_plan.return_value = _mock_generated_plan()

        mock_l5 = Mock(spec=PlanValidationService)
        mock_l5.validate_plan.return_value = {
            "valid": True,
            "violations": [],
            "validated_plan": _mock_generated_plan(),
        }

        mock_l6 = Mock(spec=PlanStorageService)
        mock_l6.save_validated_plan.return_value = 123

        # Create orchestrator with mocked services
        orchestrator = TrainingPlanOrchestratorService(
            data_collection_service=mock_l1,
            insights_calculation_service=mock_l2,
            prompt_builder_service=mock_l3,
            gpt_coach_service=mock_l4,
            plan_validation_service=mock_l5,
            plan_storage_service=mock_l6,
        )

        plan_request = _sample_plan_request()

        # Execute
        plan_id = orchestrator.generate_training_plan(
            session=test_db_session,
            user_id=str(user_id),
            plan_request=plan_request,
        )

        # Verify
        assert plan_id == 123

        # Verify all layers were called
        mock_l1.collect_all_data.assert_called_once()
        mock_l2.calculate_all_insights.assert_called_once()
        mock_l3.build_complete_prompt.assert_called_once()
        mock_l4.generate_plan.assert_called_once()
        mock_l5.validate_plan.assert_called_once()
        mock_l6.save_validated_plan.assert_called_once()

    def test_generate_training_plan_validation_errors_raise(self, test_db_session):
        """Test that validation errors cause plan generation to fail."""
        user_id = uuid.uuid4()
        test_db_session.add(UserIdentity(user_id=user_id, email="test@example.com"))
        test_db_session.commit()

        # Create mocks for all layers up to validation
        mock_l1 = Mock(spec=DataCollectionService)
        mock_l1.collect_all_data.return_value = {
            "user_profile": {"age_group": "30-39"},
            "strava_activities": [],
            "plan_request": _sample_plan_request(),
            "metadata": {},
        }

        mock_l2 = Mock(spec=InsightsCalculationService)
        mock_l2.calculate_all_insights.return_value = {
            "current_fitness": {},
            "recommendations": {},
            "metadata": {},
        }

        mock_l3 = Mock(spec=PromptBuilderService)
        mock_l3.build_complete_prompt.return_value = {
            "messages": [{"role": "system", "content": "test"}],
            "config": {},
        }

        mock_l4 = Mock(spec=GptCoachService)
        mock_l4.generate_plan.return_value = _mock_generated_plan()

        # Create orchestrator with mocked validation service that returns errors
        mock_validation = Mock(spec=PlanValidationService)
        mock_validation.validate_plan.return_value = {
            "valid": False,
            "violations": [
                {
                    "rule": "10_PERCENT_RULE",
                    "severity": "error",
                    "location": "Week 3 to Week 4",
                    "details": "25% increase exceeds 10% rule",
                    "suggestion": "Reduce Week 4 mileage",
                }
            ],
            "validated_plan": None,
        }

        orchestrator = TrainingPlanOrchestratorService(
            data_collection_service=mock_l1,
            insights_calculation_service=mock_l2,
            prompt_builder_service=mock_l3,
            gpt_coach_service=mock_l4,
            plan_validation_service=mock_validation,
        )
        plan_request = _sample_plan_request()

        # Execute and verify error
        with pytest.raises(ValueError, match="Plan validation failed"):
            orchestrator.generate_training_plan(
                session=test_db_session,
                user_id=str(user_id),
                plan_request=plan_request,
            )

    def test_generate_training_plan_validation_warnings_pass(self, test_db_session):
        """Test that validation warnings allow plan generation to continue."""
        user_id = uuid.uuid4()
        test_db_session.add(UserIdentity(user_id=user_id, email="test@example.com"))
        test_db_session.commit()

        # Create mocks for all layers
        mock_l1 = Mock(spec=DataCollectionService)
        mock_l1.collect_all_data.return_value = {
            "user_profile": {"age_group": "30-39"},
            "strava_activities": [],
            "plan_request": _sample_plan_request(),
            "metadata": {},
        }

        mock_l2 = Mock(spec=InsightsCalculationService)
        mock_l2.calculate_all_insights.return_value = {
            "current_fitness": {},
            "recommendations": {},
            "metadata": {},
        }

        mock_l3 = Mock(spec=PromptBuilderService)
        mock_l3.build_complete_prompt.return_value = {
            "messages": [{"role": "system", "content": "test"}],
            "config": {},
        }

        mock_l4 = Mock(spec=GptCoachService)
        mock_l4.generate_plan.return_value = _mock_generated_plan()

        # Create orchestrator with mocked validation service that returns warnings only
        mock_validation = Mock(spec=PlanValidationService)
        mock_validation.validate_plan.return_value = {
            "valid": True,
            "violations": [
                {
                    "rule": "CONSECUTIVE_HARD_DAYS",
                    "severity": "warning",
                    "location": "Week 5",
                    "details": "Back-to-back hard workouts",
                    "suggestion": "Add rest day",
                }
            ],
            "validated_plan": _mock_generated_plan(),
        }

        # Mock Layer 6 to return a plan_id
        mock_storage = Mock(spec=PlanStorageService)
        mock_storage.save_validated_plan.return_value = 123

        orchestrator = TrainingPlanOrchestratorService(
            data_collection_service=mock_l1,
            insights_calculation_service=mock_l2,
            prompt_builder_service=mock_l3,
            gpt_coach_service=mock_l4,
            plan_validation_service=mock_validation,
            plan_storage_service=mock_storage,
        )
        plan_request = _sample_plan_request()

        # Execute - should succeed with warnings
        plan_id = orchestrator.generate_training_plan(
            session=test_db_session,
            user_id=str(user_id),
            plan_request=plan_request,
        )

        assert plan_id == 123

    def test_generate_training_plan_data_collection_error(self, test_db_session):
        """Test that Layer 1 errors are properly handled."""
        user_id = uuid.uuid4()

        # Create orchestrator with mocked Layer 1 that raises error
        mock_l1 = Mock(spec=DataCollectionService)
        mock_l1.collect_all_data.side_effect = ValueError("User not found")

        orchestrator = TrainingPlanOrchestratorService(
            data_collection_service=mock_l1,
        )
        plan_request = _sample_plan_request()

        # Execute and verify error propagation
        with pytest.raises(ValueError, match="User not found"):
            orchestrator.generate_training_plan(
                session=test_db_session,
                user_id=str(user_id),
                plan_request=plan_request,
            )
