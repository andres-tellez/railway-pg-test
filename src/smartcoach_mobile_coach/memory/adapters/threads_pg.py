"""Postgres adapter for open-threads repository."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from src.db.models.memory.user_open_threads import UserOpenThread
from src.smartcoach_mobile_coach.memory.domain.types import OpenThread, Provenance
from src.smartcoach_mobile_coach.memory.domain.vocab import Source, ThreadTopic


def _to_source(raw: str | None) -> Source:
    value = (raw or "").strip().lower()
    if value in ("user_statement", "coach_tool", "summarizer", "inferred", "system"):
        return Source(value)
    return Source.SYSTEM


def _to_topic(raw: str | None) -> ThreadTopic:
    value = (raw or "").strip().lower()
    if value in (
        "injury_recheck",
        "plan_decision",
        "goal_revisit",
        "progress_checkin",
        "user_request",
    ):
        return ThreadTopic(value)
    return ThreadTopic.USER_REQUEST


def _to_item(row: UserOpenThread) -> OpenThread:
    return OpenThread(
        id=row.id,
        user_id=row.user_id,
        text=row.text,
        topic=_to_topic(row.topic),
        due_at=row.due_at,
        status=row.status,
        created_at=row.created_at,
        provenance=Provenance(
            source=_to_source(row.source),
            captured_at=row.created_at,
            conversation_id=row.conversation_id,
        ),
    )


class ThreadRepoPG:
    """Open-threads repository backed by `user_open_threads`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_due(self, user_id: UUID, now: datetime) -> Sequence[OpenThread]:
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        rows = (
            self._session.query(UserOpenThread)
            .filter(
                UserOpenThread.user_id == user_id,
                UserOpenThread.status == "open",
                UserOpenThread.due_at <= now,
            )
            .order_by(UserOpenThread.due_at.asc())
            .all()
        )
        return tuple(_to_item(r) for r in rows)

    def append(self, item: OpenThread) -> OpenThread:
        row = UserOpenThread(
            id=item.id,
            user_id=item.user_id,
            topic=item.topic.value,
            text=item.text,
            due_at=item.due_at,
            status=item.status,
            created_at=item.created_at,
            source=item.provenance.source.value,
            conversation_id=item.provenance.conversation_id,
        )
        self._session.add(row)
        self._session.flush()
        return _to_item(row)
