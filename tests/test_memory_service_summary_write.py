"""MemoryService.write_session_summary tests."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from src.smartcoach_mobile_coach.memory.domain.observation import Observation
from src.smartcoach_mobile_coach.memory.domain.types import (
    Callback,
    DurableItem,
    InteractionRecord,
    OpenThread,
    SessionSummaryItem,
    StateObservation,
)
from src.smartcoach_mobile_coach.memory.domain.vocab import MemoryKind, Source
from src.smartcoach_mobile_coach.memory.service import MemoryService


class _DurableRepoFake:
    def __init__(self) -> None:
        self.items: list[DurableItem] = []

    def list_for_user(self, user_id: uuid.UUID) -> Sequence[DurableItem]:
        return tuple(i for i in self.items if i.user_id == user_id)

    def append(self, item: DurableItem) -> DurableItem:
        self.items.append(item)
        return item


class _StateRepoFake:
    def list_active(
        self, user_id: uuid.UUID, now: datetime
    ) -> Sequence[StateObservation]:
        return tuple()

    def append(self, item: StateObservation) -> StateObservation:
        return item


class _ThreadRepoFake:
    def list_due(self, user_id: uuid.UUID, now: datetime) -> Sequence[OpenThread]:
        return tuple()

    def append(self, item: OpenThread) -> OpenThread:
        return item


class _InteractionRepoFake:
    def list_recent(
        self, *, user_id: uuid.UUID, conversation_id: uuid.UUID, since: datetime
    ) -> Sequence[InteractionRecord]:
        return tuple()

    def record(self, item: InteractionRecord) -> InteractionRecord:
        return item


class _SummaryRepoFake:
    def __init__(self) -> None:
        self.items: list[SessionSummaryItem] = []

    def read_latest(self, user_id: uuid.UUID) -> SessionSummaryItem | None:
        rows = [i for i in self.items if i.user_id == user_id]
        return rows[-1] if rows else None

    def append(self, item: SessionSummaryItem) -> SessionSummaryItem:
        self.items.append(item)
        return item


@dataclass
class _SummarizerFake:
    payload: Mapping[str, Any]

    def summarize(
        self,
        *,
        user_id: uuid.UUID,
        turns: Sequence[Mapping[str, Any]],
        timeout_s: float,
    ) -> Mapping[str, Any]:
        assert user_id
        assert turns
        assert timeout_s > 0
        return self.payload


class _SummarizerRaisesFake:
    def summarize(
        self,
        *,
        user_id: uuid.UUID,
        turns: Sequence[Mapping[str, Any]],
        timeout_s: float,
    ) -> Mapping[str, Any]:
        raise RuntimeError("llm unavailable")


class _ClassifierNoop:
    def classify(self, obs: Observation) -> Observation:
        return obs


class _CallbackPolicyNoop:
    def choose(self, *, view, budget: int) -> Sequence[Callback]:
        return tuple()


class _PromptRendererNoop:
    def render(self, view) -> str:
        return ""


def _service_with_summarizer(
    summarizer,
) -> tuple[MemoryService, _SummaryRepoFake, _DurableRepoFake]:
    summary_repo = _SummaryRepoFake()
    durable_repo = _DurableRepoFake()
    service = MemoryService(
        durable_repo=durable_repo,
        state_repo=_StateRepoFake(),
        thread_repo=_ThreadRepoFake(),
        interaction_repo=_InteractionRepoFake(),
        summary_repo=summary_repo,
        summarizer_llm=summarizer,
        classifier=_ClassifierNoop(),
        callback_policy=_CallbackPolicyNoop(),
        prompt_renderer=_PromptRendererNoop(),
    )
    return service, summary_repo, durable_repo


def test_write_session_summary_persists_summary_and_memories() -> None:
    payload = {
        "content": json.dumps(
            {
                "summary_text": "User discussed pacing confidence and agreed on recovery emphasis.",
                "thread_tags": ["pacing", "recovery"],
                "plan_memories": [
                    "I can only run 4 days per week because of work schedule.",
                    "Thanks for the help",
                ],
            }
        ),
        "model": "gpt-4o-mini",
        "cost": 0.0004,
    }
    service, summary_repo, durable_repo = _service_with_summarizer(
        _SummarizerFake(payload)
    )
    result = service.write_session_summary(
        user_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        user_message="Can you summarize this chat?",
        assistant_reply={"content": "Sure - here's what we covered."},
        tool_names=["get_run_summary"],
    )
    assert result.kind == MemoryKind.SUMMARY
    assert result.action == "created"
    assert len(summary_repo.items) == 1
    assert summary_repo.items[0].tags == ("pacing", "recovery")
    assert len(durable_repo.items) == 1
    assert durable_repo.items[0].provenance.source == Source.SUMMARIZER


def test_write_session_summary_rejects_llm_failure() -> None:
    service, summary_repo, durable_repo = _service_with_summarizer(
        _SummarizerRaisesFake()
    )
    result = service.write_session_summary(
        user_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        user_message="Please summarize",
        assistant_reply="summary please",
        tool_names=[],
    )
    assert result.kind == MemoryKind.SUMMARY
    assert result.action == "rejected"
    assert result.reason == "llm_failure"
    assert len(summary_repo.items) == 0
    assert len(durable_repo.items) == 0


def test_write_session_summary_rejects_invalid_payload() -> None:
    payload = {"content": "{bad-json"}
    service, summary_repo, durable_repo = _service_with_summarizer(
        _SummarizerFake(payload)
    )
    result = service.write_session_summary(
        user_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        user_message="Please summarize",
        assistant_reply="text",
        tool_names=[],
    )
    assert result.kind == MemoryKind.SUMMARY
    assert result.action == "rejected"
    assert result.reason == "invalid_summary_payload"
    assert len(summary_repo.items) == 0
    assert len(durable_repo.items) == 0
