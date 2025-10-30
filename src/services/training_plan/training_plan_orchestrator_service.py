"""
Training Plan Orchestrator Service

Purpose:
    Orchestrates the complete 6-layer training plan generation pipeline.
    This is the main entry point for generating training plans.

Responsibilities:
    - Coordinate all 6 layers in sequence
    - Handle errors and logging at each stage
    - Provide a clean API for plan generation
    - Manage dependencies (session, LLM client, etc.)

Architecture:
    Layer 1: DataCollectionService → Collect raw data
    Layer 2: InsightsCalculationService → Calculate insights
    Layer 3: PromptBuilderService → Build GPT prompt
    Layer 4: GptCoachService → Generate plan with LLM
    Layer 5: PlanValidationService → Validate plan safety
    Layer 6: PlanStorageService → Save to database

Dependencies:
    - All 6 layer services
    - Database session
    - LLM client factory
    - SQLAlchemy session

Usage:
    from src.services.training_plan.training_plan_orchestrator_service import TrainingPlanOrchestratorService

    orchestrator = TrainingPlanOrchestratorService.create_default()
    plan_id = orchestrator.generate_training_plan(
        session=session,
        user_id="123e4567-e89b-12d3-a456-426614174000",
        plan_request={
            "race_date": "2025-06-15",
            "race_distance": "Marathon",
            "race_name": "Boston Marathon",
            ...
        }
    )

Testing:
    See tests/services/training_plan/test_training_plan_orchestrator_service.py

Author: SmartCoach Development Team
Last Updated: October 29, 2025
"""

import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from src.services.training_plan.data_collection_service import DataCollectionService
from src.services.training_plan.insights_calculation_service import (
    InsightsCalculationService,
)
from src.services.training_plan.prompt_builder_service import PromptBuilderService
from src.services.training_plan.gpt_coach_service import GptCoachService
from src.services.training_plan.plan_validation_service import PlanValidationService
from src.services.training_plan.plan_storage_service import PlanStorageService
from src.services.training_plan.llm_factory import create_llm_client

logger = logging.getLogger(__name__)


class TrainingPlanOrchestratorService:
    """Orchestrates the complete 6-layer training plan generation pipeline."""

    def __init__(
        self,
        *,
        data_collection_service: Optional[DataCollectionService] = None,
        insights_calculation_service: Optional[InsightsCalculationService] = None,
        prompt_builder_service: Optional[PromptBuilderService] = None,
        gpt_coach_service: Optional[GptCoachService] = None,
        plan_validation_service: Optional[PlanValidationService] = None,
        plan_storage_service: Optional[PlanStorageService] = None,
    ):
        """
        Initialize orchestrator with all layer services.

        Args:
            data_collection_service: Layer 1 service (optional, creates default if None)
            insights_calculation_service: Layer 2 service (optional, creates default if None)
            prompt_builder_service: Layer 3 service (optional, creates default if None)
            gpt_coach_service: Layer 4 service (optional, creates default if None)
            plan_validation_service: Layer 5 service (optional, creates default if None)
            plan_storage_service: Layer 6 service (optional, creates default if None)
        """
        self.data_collection_service = (
            data_collection_service or DataCollectionService()
        )
        self.insights_calculation_service = (
            insights_calculation_service or InsightsCalculationService()
        )
        self.prompt_builder_service = prompt_builder_service or PromptBuilderService()
        self.plan_validation_service = (
            plan_validation_service or PlanValidationService()
        )
        self.plan_storage_service = plan_storage_service or PlanStorageService()

        # Layer 4 needs LLM client - create default
        if gpt_coach_service is None:
            llm_client = create_llm_client()
            self.gpt_coach_service = GptCoachService(llm_client=llm_client)
        else:
            self.gpt_coach_service = gpt_coach_service

    @staticmethod
    def create_default() -> "TrainingPlanOrchestratorService":
        """
        Create orchestrator with default service instances.

        Returns:
            TrainingPlanOrchestratorService with all defaults
        """
        return TrainingPlanOrchestratorService()

    def generate_training_plan(
        self,
        session: Session,
        user_id: str,
        plan_request: Dict[str, Any],
        *,
        activity_weeks: int = 12,
    ) -> int:
        """
        Generate a complete training plan through all 6 layers.

        Args:
            session: SQLAlchemy database session
            user_id: UUID string of the user
            plan_request: Plan request dictionary containing:
                - race_date: "YYYY-MM-DD" string
                - race_distance: str (e.g., "Marathon", "Half Marathon")
                - race_name: Optional[str]
                - race_location: Optional[str]
                - primary_goal: Optional[str]
                - marathon_experience: Optional[str]
                - target_time: Optional[str]
                - training_days: Optional[List[str]]
                - notes: Optional[str]
            activity_weeks: Number of weeks of activity history to analyze

        Returns:
            plan_id: Database ID of the created plan

        Raises:
            ValueError: If inputs are invalid or plan generation fails
            RuntimeError: If any layer fails unrecoverably
        """
        logger.info(f"Starting training plan generation for user {user_id}")

        try:
            # LAYER 1: Data Collection
            logger.debug("Layer 1: Collecting raw data")
            raw_data = self.data_collection_service.collect_all_data(
                session=session,
                user_id=user_id,
                plan_request=plan_request,
                activity_weeks=activity_weeks,
            )
            logger.info(
                f"Layer 1 complete: Collected {len(raw_data.get('strava_activities', []))} activities"
            )

            # LAYER 2: Insights Calculation
            logger.debug("Layer 2: Calculating insights")
            insights = self.insights_calculation_service.calculate_all_insights(
                raw_data
            )
            logger.info("Layer 2 complete: Insights calculated")

            # Extract user_profile for Layer 3
            user_profile = raw_data.get("user_profile", {})

            # LAYER 3: Prompt Builder
            logger.debug("Layer 3: Building GPT prompt")
            prompt = self.prompt_builder_service.build_complete_prompt(
                insights=insights,
                user_profile=user_profile,
                plan_request=plan_request,
            )
            logger.info("Layer 3 complete: Prompt built")

            # LAYER 4: GPT Coach
            logger.debug("Layer 4: Generating plan with LLM")
            generated_plan = self.gpt_coach_service.generate_plan(prompt)
            logger.info(
                f"Layer 4 complete: Plan generated ({generated_plan.get('plan_name', 'Unknown')})"
            )

            # LAYER 5: Plan Validation
            logger.debug("Layer 5: Validating plan")
            validation_result = self.plan_validation_service.validate_plan(
                generated_plan
            )

            if not validation_result.get("valid", False):
                violations = validation_result.get("violations", [])
                errors = [
                    v for v in violations if v.get("severity", "").lower() == "error"
                ]
                warnings = [
                    v for v in violations if v.get("severity", "").lower() == "warning"
                ]

                if errors:
                    logger.error(f"Layer 5 failed: {len(errors)} validation errors")
                    for error in errors:
                        logger.error(f"  - {error.get('rule')}: {error.get('details')}")
                    raise ValueError(
                        f"Plan validation failed with {len(errors)} errors. "
                        f"First error: {errors[0].get('details', 'Unknown')}"
                    )

                if warnings:
                    logger.warning(
                        f"Layer 5 warnings: {len(warnings)} validation warnings"
                    )
                    for warning in warnings:
                        logger.warning(
                            f"  - {warning.get('rule')}: {warning.get('details')}"
                        )

            logger.info("Layer 5 complete: Plan validated")

            # Extract validated plan from validation result
            validated_plan = validation_result.get("validated_plan", generated_plan)

            # LAYER 6: Plan Storage
            logger.debug("Layer 6: Saving plan to database")
            plan_id = self.plan_storage_service.save_validated_plan(
                session=session,
                user_id=user_id,
                validated_plan=validation_result,  # Pass full validation result
                plan_request=plan_request,
            )
            logger.info(f"Layer 6 complete: Plan saved with ID {plan_id}")

            logger.info(
                f"✅ Training plan generation complete: plan_id={plan_id} for user {user_id}"
            )
            return plan_id

        except ValueError as e:
            logger.error(
                f"Training plan generation failed (ValueError): {e}", exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"Training plan generation failed (unexpected error): {e}",
                exc_info=True,
            )
            raise RuntimeError(f"Plan generation failed: {e}") from e

    def generate_draft(
        self,
        session: Session,
        user_id: str,
        plan_request: Dict[str, Any],
        *,
        activity_weeks: int = 12,
    ) -> Dict[str, Any]:
        """
        Generate a draft training plan without saving to the database.

        Runs Layers 1-5 and returns both the generated plan and validation result.

        Returns:
            {
              "generated_plan": Dict,
              "validation": Dict
            }
        """
        logger.info(f"Starting draft plan generation for user {user_id}")

        # LAYER 1: Data Collection
        raw_data = self.data_collection_service.collect_all_data(
            session=session,
            user_id=user_id,
            plan_request=plan_request,
            activity_weeks=activity_weeks,
        )

        # LAYER 2: Insights Calculation
        insights = self.insights_calculation_service.calculate_all_insights(raw_data)

        # LAYER 3: Prompt Builder
        user_profile = raw_data.get("user_profile", {})
        prompt = self.prompt_builder_service.build_complete_prompt(
            insights=insights,
            user_profile=user_profile,
            plan_request=plan_request,
        )

        # LAYER 4: GPT Coach
        generated_plan = self.gpt_coach_service.generate_plan(prompt)

        # LAYER 5: Plan Validation
        validation_result = self.plan_validation_service.validate_plan(generated_plan)

        logger.info("Draft plan generation complete (not saved)")

        return {
            "generated_plan": generated_plan,
            "validation": validation_result,
        }
