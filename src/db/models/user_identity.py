# src/db/models/user_identity.py

import uuid as uuid_lib

from sqlalchemy import Column, String, Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from src.db.db_session import Base


class UserIdentity(Base):
    __tablename__ = "user_identity"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    email = Column(String, nullable=True)
    email_verified = Column(Boolean, nullable=True)
    name = Column(String, nullable=True)
    picture = Column(String, nullable=True)

    # Set when first full Strava sync + enrichment pipeline reports coach_data_ready;
    # until then, mile splits / streams are not persisted (see persist_splits_for_user).
    initial_strava_import_completed_at = Column(DateTime(timezone=True), nullable=True)

    # ✅ ensure default + update on change
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    plans = relationship("Plan", back_populates="user", cascade="all, delete-orphan")
