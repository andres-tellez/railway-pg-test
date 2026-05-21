"""Postgres adapter for session summary repository."""

from __future__ import annotations

from sqlalchemy.orm import Session
from uuid import UUID

from src.db.models.memory.session_summaries import SessionSummary
from src.smartcoach_mobile_coach.memory.domain.types import SessionSummaryItem


def _to_item(row: SessionSummary) -> SessionSummaryItem:
    return SessionSummaryItem(
        id=row.id,
        user_id=row.user_id,
        conversation_id=row.conversation_id,
        text=row.summary_text,
        tags=tuple(row.thread_tags or []),
        created_at=row.created_at,
    )


class SummaryRepoPG:
    """Summary repository backed by `session_summaries`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def read_latest(self, user_id: UUID) -> SessionSummaryItem | None:
        row = (
            self._session.query(SessionSummary)
            .filter(SessionSummary.user_id == user_id)
            .order_by(SessionSummary.created_at.desc())
            .first()
        )
        if row is None:
            return None
        return _to_item(row)

    def append(self, item: SessionSummaryItem) -> SessionSummaryItem:
        row = SessionSummary(
            user_id=item.user_id,
            conversation_id=item.conversation_id,
            summary_text=item.text,
            thread_tags=list(item.tags),
        )
        self._session.add(row)
        self._session.flush()
        return _to_item(row)
