"""Memory V2 — open follow-up threads."""

from __future__ import annotations

import uuid

from sqlalchemy import Column, ForeignKey, String, Text, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID

from src.db.db_session import Base


class UserOpenThread(Base):
    """Follow-up commitments/questions the coach should revisit."""

    __tablename__ = "user_open_threads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_identity.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic = Column(String(64), nullable=False)
    text = Column(Text, nullable=False)
    due_at = Column(TIMESTAMP(timezone=True), nullable=False)
    status = Column(String(16), nullable=False, server_default="open")
    resolved_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    source = Column(String(32), nullable=False)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
