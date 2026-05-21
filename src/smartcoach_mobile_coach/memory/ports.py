"""
Purpose:
- Define repository and policy ports for MemoryService.

Responsibilities:
- Declare Protocol-based interfaces that adapters must implement.
- Keep service logic decoupled from storage and external APIs.

Non-goals:
- No concrete adapter implementations.
- No business policy logic.

Guardrails:
- Allowed imports/calls: typing + memory domain types only.
- Must not import SQLAlchemy models, orchestrator, or OpenAI services.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Protocol, Sequence
from uuid import UUID

from src.smartcoach_mobile_coach.memory.domain.observation import Observation
from src.smartcoach_mobile_coach.memory.domain.scope import Scope
from src.smartcoach_mobile_coach.memory.domain.types import (
    Callback,
    DurableItem,
    InteractionRecord,
    OpenThread,
    RecordResult,
    SessionSummaryItem,
    StateObservation,
)
from src.smartcoach_mobile_coach.memory.domain.view import MemoryView


class DurableRepo(Protocol):
    def list_for_user(self, user_id: UUID) -> Sequence[DurableItem]: ...

    def append(self, item: DurableItem) -> DurableItem: ...


class StateRepo(Protocol):
    def list_active(
        self, user_id: UUID, now: datetime
    ) -> Sequence[StateObservation]: ...

    def append(self, item: StateObservation) -> StateObservation: ...


class ThreadRepo(Protocol):
    def list_due(self, user_id: UUID, now: datetime) -> Sequence[OpenThread]: ...

    def append(self, item: OpenThread) -> OpenThread: ...


class InteractionRepo(Protocol):
    def list_recent(
        self,
        *,
        user_id: UUID,
        conversation_id: UUID,
        since: datetime,
    ) -> Sequence[InteractionRecord]: ...

    def record(self, item: InteractionRecord) -> InteractionRecord: ...


class SummaryRepo(Protocol):
    def read_latest(self, user_id: UUID) -> SessionSummaryItem | None: ...

    def append(self, item: SessionSummaryItem) -> SessionSummaryItem: ...


class SummarizerLLM(Protocol):
    def summarize(
        self,
        *,
        user_id: UUID,
        turns: Sequence[Mapping[str, Any]],
        timeout_s: float,
    ) -> Mapping[str, Any]: ...


class ObservationClassifier(Protocol):
    def classify(self, obs: Observation) -> Observation: ...


class ProactiveCallbackPolicy(Protocol):
    def choose(self, *, view: MemoryView, budget: int) -> Sequence[Callback]: ...


class PromptRenderer(Protocol):
    def render(self, view: MemoryView) -> str: ...


class MemoryServicePort(Protocol):
    def record(self, obs: Observation) -> RecordResult: ...

    def get_view(self, scope: Scope) -> MemoryView: ...
