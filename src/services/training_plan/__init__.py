"""
Training Plan Generation Services

This namespace exposes shared services used alongside the V2 deterministic
pipeline (data collection, storage). Plan validation lives in
``PlanValidationServiceV2`` under ``v2/``. End-to-end plan generation is in
``src/services/training_plan/v2/plan_generation_orchestrator_v2.py``.

Product spec: docs/SMARTCOACH_SYSTEM_SPEC_V1.md — API: docs/API_DOCUMENTATION.md
"""

from .data_collection_service import DataCollectionService
from .plan_storage_service import PlanStorageService

__all__ = [
    "DataCollectionService",
    "PlanStorageService",
]
