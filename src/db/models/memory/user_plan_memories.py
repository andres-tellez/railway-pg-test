"""V1.6 Phase F — Layer C plan-aware long-term memory (stated preferences)."""

from __future__ import annotations

import uuid

from sqlalchemy import Column, ForeignKey, String, Text, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID

from src.db.db_session import Base

MEMORY_SOURCE_COACH_TOOL = "coach_tool"
MEMORY_SOURCE_SESSION_SUMMARY = "session_summary"


class UserPlanMemory(Base):
    """Durable snippets the coach or summarizer stored for future plan/context reads."""

    __tablename__ = "user_plan_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_identity.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    memory_text = Column(Text, nullable=False)
    source = Column(String(32), nullable=False)
    # Nullable for backward compatibility; inferred on write (keyword rules).
    memory_type = Column(String(32), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
