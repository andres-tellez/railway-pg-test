"""V1.6 Phase F — persisted session summaries (Topic 6 Layer B write path)."""

from __future__ import annotations

import uuid

from sqlalchemy import Column, ForeignKey, Text, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import JSON

from src.db.db_session import Base


class SessionSummary(Base):
    """One row per completed coach exchange summarization (curated text only)."""

    __tablename__ = "session_summaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_identity.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    summary_text = Column(Text, nullable=False)
    thread_tags = Column(JSON, nullable=False, default=list)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
