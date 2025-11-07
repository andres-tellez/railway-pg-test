"""
Training Plan Generation Services

This package implements deterministic plan generation for marathon training plans:

Layer 1: Data Collection Service - Fetch raw data from database
Layer 2: Insights Calculation Service - Calculate safety-critical metrics
Layer 5: Plan Validation Service - Verify plan follows safety rules
Layer 6: Plan Storage Service - Save validated plan to database

Core Services:
- Pass1LongRunFirst: Deterministic long-run progression
- WeeklyTotalCalculator: Calculate weekly totals from long runs
- Pass3WorkoutDistribution: Distribute workouts across training days

Usage:
    from src.services.training_plan import DataCollectionService, PlanStorageService

    # See orchestrator_three_pass.ThreePassOrchestrator for full flow

Architecture Documentation: docs/training-plan-architecture-v3.md
"""

from .data_collection_service import DataCollectionService
from .insights_calculation_service import InsightsCalculationService
from .plan_validation_service import PlanValidationService
from .plan_storage_service import PlanStorageService

__all__ = [
    "DataCollectionService",
    "InsightsCalculationService",
    "PlanValidationService",
    "PlanStorageService",
]
