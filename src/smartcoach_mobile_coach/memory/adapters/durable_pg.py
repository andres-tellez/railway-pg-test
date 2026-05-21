"""Postgres adapter for durable memory repository."""

from __future__ import annotations

from typing import Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from src.db.models.memory.user_plan_memories import UserPlanMemory
from src.smartcoach_mobile_coach.memory.domain.types import DurableItem, Provenance
from src.smartcoach_mobile_coach.memory.domain.vocab import DurableType, Source


def _to_durable_type(raw: str | None) -> DurableType:
    value = (raw or "").strip().lower()
    if value in (
        "goal",
        "constraint",
        "preference",
        "training_days",
        "long_run_day",
        "other",
    ):
        return DurableType(value)
    return DurableType.OTHER


def _to_source(raw: str | None) -> Source:
    value = (raw or "").strip().lower()
    if value in ("coach_tool", "session_summary"):
        return Source.COACH_TOOL if value == "coach_tool" else Source.SUMMARIZER
    if value in ("user_statement", "inferred", "system"):
        return Source(value)
    return Source.SYSTEM


def _to_item(row: UserPlanMemory) -> DurableItem:
    captured = row.created_at
    return DurableItem(
        id=row.id,
        user_id=row.user_id,
        text=row.memory_text,
        durable_type=_to_durable_type(row.memory_type),
        provenance=Provenance(
            source=_to_source(row.source),
            captured_at=captured,
            conversation_id=None,
        ),
    )


class DurableRepoPG:
    """Durable memory repository backed by `user_plan_memories`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_user(self, user_id: UUID) -> Sequence[DurableItem]:
        rows = (
            self._session.query(UserPlanMemory)
            .filter(UserPlanMemory.user_id == user_id)
            .order_by(UserPlanMemory.created_at.desc())
            .all()
        )
        return tuple(_to_item(r) for r in rows)

    def append(self, item: DurableItem) -> DurableItem:
        row = UserPlanMemory(
            user_id=item.user_id,
            memory_text=item.text,
            source=item.provenance.source.value,
            memory_type=item.durable_type.value,
        )
        self._session.add(row)
        self._session.flush()
        return _to_item(row)
