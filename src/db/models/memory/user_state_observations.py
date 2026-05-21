"""Memory V2 — short-lived state observations."""

from __future__ import annotations

import uuid

from sqlalchemy import Column, ForeignKey, SmallInteger, String, Text, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import Float

from src.db.db_session import Base


class UserStateObservation(Base):
    """Short-lived state/mood/body-status memory rows."""

    __tablename__ = "user_state_observations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_identity.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tag = Column(String(64), nullable=False)
    body_area = Column(String(64), nullable=True)
    intensity = Column(SmallInteger, nullable=True)
    text = Column(Text, nullable=False)
    captured_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    valid_until = Column(TIMESTAMP(timezone=True), nullable=False)
    source = Column(String(32), nullable=False)
    confidence = Column(Float, nullable=False, server_default="1.0")
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    evidence_excerpt = Column(Text, nullable=True)
