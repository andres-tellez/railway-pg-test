"""Postgres adapter for interaction tracking repository."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from src.db.models.memory.coach_interactions import CoachInteraction
from src.smartcoach_mobile_coach.memory.domain.types import InteractionRecord
from src.smartcoach_mobile_coach.memory.domain.vocab import InteractionFlag


def _to_item(row: CoachInteraction) -> InteractionRecord:
    return InteractionRecord(
        id=row.id,
        user_id=row.user_id,
        conversation_id=row.conversation_id,
        flag=InteractionFlag(row.flag),
        key=row.key,
        captured_at=row.captured_at,
    )


class InteractionRepoPG:
    """Interaction repository backed by `coach_interactions`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_recent(
        self, *, user_id: UUID, conversation_id: UUID, since: datetime
    ) -> Sequence[InteractionRecord]:
        rows = (
            self._session.query(CoachInteraction)
            .filter(
                CoachInteraction.user_id == user_id,
                CoachInteraction.conversation_id == conversation_id,
                CoachInteraction.captured_at >= since,
            )
            .order_by(CoachInteraction.captured_at.desc())
            .all()
        )
        out: list[InteractionRecord] = []
        for row in rows:
            try:
                out.append(_to_item(row))
            except Exception:
                continue
        return tuple(out)

    def record(self, item: InteractionRecord) -> InteractionRecord:
        existing = (
            self._session.query(CoachInteraction)
            .filter(
                CoachInteraction.user_id == item.user_id,
                CoachInteraction.conversation_id == item.conversation_id,
                CoachInteraction.flag == item.flag.value,
                CoachInteraction.key == item.key,
            )
            .first()
        )
        if existing is not None:
            return _to_item(existing)
        row = CoachInteraction(
            id=item.id if item.id else uuid.uuid4(),
            user_id=item.user_id,
            conversation_id=item.conversation_id,
            flag=item.flag.value,
            key=item.key,
            captured_at=item.captured_at,
        )
        self._session.add(row)
        self._session.flush()
        return _to_item(row)
