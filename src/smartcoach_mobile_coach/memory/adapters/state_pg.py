"""Postgres adapter for state observation repository."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from src.db.models.memory.user_state_observations import UserStateObservation
from src.smartcoach_mobile_coach.memory.domain.types import Provenance, StateObservation
from src.smartcoach_mobile_coach.memory.domain.vocab import Source, StateTag


def _to_source(raw: str | None) -> Source:
    value = (raw or "").strip().lower()
    if value in ("user_statement", "coach_tool", "summarizer", "inferred", "system"):
        return Source(value)
    return Source.SYSTEM


def _to_state_tag(raw: str | None) -> StateTag:
    value = (raw or "").strip().lower()
    if value in (
        "headache",
        "sore",
        "low_sleep",
        "high_stress",
        "low_motivation",
        "sick",
        "injury_flare",
        "good_day",
    ):
        return StateTag(value)
    return StateTag.SORE


def _to_item(row: UserStateObservation) -> StateObservation:
    return StateObservation(
        id=row.id,
        user_id=row.user_id,
        text=row.text,
        tag=_to_state_tag(row.tag),
        captured_at=row.captured_at,
        valid_until=row.valid_until,
        body_area=row.body_area,
        intensity=row.intensity,
        provenance=Provenance(
            source=_to_source(row.source),
            captured_at=row.captured_at,
            conversation_id=row.conversation_id,
            confidence=float(row.confidence or 1.0),
            evidence_excerpt=row.evidence_excerpt,
        ),
    )


class StateRepoPG:
    """State observations repository backed by `user_state_observations`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_active(self, user_id: UUID, now: datetime) -> Sequence[StateObservation]:
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        rows = (
            self._session.query(UserStateObservation)
            .filter(
                UserStateObservation.user_id == user_id,
                UserStateObservation.valid_until >= now,
            )
            .order_by(UserStateObservation.captured_at.desc())
            .all()
        )
        return tuple(_to_item(r) for r in rows)

    def append(self, item: StateObservation) -> StateObservation:
        row = UserStateObservation(
            id=item.id,
            user_id=item.user_id,
            tag=item.tag.value,
            body_area=item.body_area,
            intensity=item.intensity,
            text=item.text,
            captured_at=item.captured_at,
            valid_until=item.valid_until,
            source=(
                item.provenance.source.value if item.provenance else Source.SYSTEM.value
            ),
            confidence=(item.provenance.confidence if item.provenance else 1.0),
            conversation_id=(
                item.provenance.conversation_id if item.provenance else None
            ),
            evidence_excerpt=(
                item.provenance.evidence_excerpt if item.provenance else None
            ),
        )
        self._session.add(row)
        self._session.flush()
        return _to_item(row)
