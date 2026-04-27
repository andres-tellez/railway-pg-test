"""
Training Plan Generation Services

This namespace exposes the shared services still used by the refactored V2
pipeline (data collection, insights, storage). Plan validation for generation
lives in ``PlanValidationServiceV2`` under ``v2/``. End-to-end plan generation
logic is in ``src/services/training_plan/v2/plan_generation_orchestrator_v2.py``.

Product spec: docs/SMARTCOACH_SYSTEM_SPEC_V1.md — API: docs/API_DOCUMENTATION.md
"""

from .data_collection_service import DataCollectionService
from .insights_calculation_service import InsightsCalculationService
from .plan_storage_service import PlanStorageService

__all__ = [
    "DataCollectionService",
    "InsightsCalculationService",
    "PlanStorageService",
]
