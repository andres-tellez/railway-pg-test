"""Memory V2 — interaction tracking rows."""

from __future__ import annotations

import uuid

from sqlalchemy import Column, ForeignKey, String, TIMESTAMP, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID

from src.db.db_session import Base


class CoachInteraction(Base):
    """Per-conversation interaction markers (e.g., recapped_run for activity id)."""

    __tablename__ = "coach_interactions"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "conversation_id",
            "flag",
            "key",
            name="uq_coach_interactions_scope",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_identity.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    flag = Column(String(64), nullable=False)
    key = Column(String(128), nullable=False)
    captured_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
