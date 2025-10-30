"""
Training Plan Generation Services

This package implements a 6-layer architecture for generating marathon training plans:

Layer 1: Data Collection Service - Fetch raw data from database
Layer 2: Insights Calculation Service - Calculate safety-critical metrics
Layer 3: Prompt Builder Service - Structure data into optimized GPT prompt
Layer 4: GPT Coach Service - Generate training plan using AI
Layer 5: Plan Validation Service - Verify plan follows safety rules
Layer 6: Plan Storage Service - Save validated plan to database

Orchestrator: Training Plan Orchestrator Service - Coordinates all 6 layers

Usage:
    from src.services.training_plan import TrainingPlanOrchestratorService

    orchestrator = TrainingPlanOrchestratorService.create_default()
    plan_id = orchestrator.generate_training_plan(
        session=session,
        user_id=user_id,
        plan_request=plan_request
    )

Architecture Documentation: docs/training-plan-architecture-v3.md
"""

from .data_collection_service import DataCollectionService
from .insights_calculation_service import InsightsCalculationService
from .prompt_builder_service import PromptBuilderService
from .gpt_coach_service import GptCoachService
from .plan_validation_service import PlanValidationService
from .plan_storage_service import PlanStorageService
from .training_plan_orchestrator_service import TrainingPlanOrchestratorService

__all__ = [
    "DataCollectionService",
    "InsightsCalculationService",
    "PromptBuilderService",
    "GptCoachService",
    "PlanValidationService",
    "PlanStorageService",
    "TrainingPlanOrchestratorService",
]
