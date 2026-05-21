"""
Memory package public API.

Phase 1 skeleton:
- Defines package boundaries and typed interfaces.
- Does not wire orchestrator consumers or persistence adapters yet.
"""

from src.smartcoach_mobile_coach.memory.config import MemoryConfig, load_memory_config
from src.smartcoach_mobile_coach.memory.domain.observation import Observation
from src.smartcoach_mobile_coach.memory.domain.scope import Scope
from src.smartcoach_mobile_coach.memory.domain.types import (
    Callback,
    DurableItem,
    InteractionRecord,
    OpenThread,
    Provenance,
    RecordResult,
    SessionSummaryItem,
    StateObservation,
)
from src.smartcoach_mobile_coach.memory.domain.view import MemoryView, ViewDiagnostics
from src.smartcoach_mobile_coach.memory.domain.vocab import (
    DurableType,
    InteractionFlag,
    MemoryKind,
    Source,
    StateTag,
    ThreadTopic,
)
from src.smartcoach_mobile_coach.memory.factory import build_memory_service
from src.smartcoach_mobile_coach.memory.service import MemoryService

__all__ = [
    "Callback",
    "DurableItem",
    "DurableType",
    "InteractionFlag",
    "InteractionRecord",
    "MemoryConfig",
    "MemoryKind",
    "MemoryService",
    "MemoryView",
    "Observation",
    "OpenThread",
    "Provenance",
    "RecordResult",
    "Scope",
    "SessionSummaryItem",
    "Source",
    "StateObservation",
    "StateTag",
    "ThreadTopic",
    "ViewDiagnostics",
    "load_memory_config",
    "build_memory_service",
]
