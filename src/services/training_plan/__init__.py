"""
Training Plan Generation Services

This namespace exposes the shared services still used by the refactored V2
pipeline (data collection, insights, validation, storage). The end-to-end plan
generation logic now lives under
`src/services/training_plan/v2/plan_generation_orchestrator_v2.py`.

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
