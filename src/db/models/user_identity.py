from sqlalchemy import Column, String, Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from src.db.db_session import Base


class UserIdentity(Base):
    __tablename__ = "user_identity"

    user_id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )  # ✅ UUID

    email = Column(String, nullable=True)
    email_verified = Column(Boolean, nullable=True)
    name = Column(String, nullable=True)
    picture = Column(String, nullable=True)
    updated_at = Column(DateTime, nullable=False, server_default=func.now())

    def to_dict(self):
        return {
            "user_id": str(self.user_id),  # ✅ convert UUID to string
            "email": self.email,
            "email_verified": self.email_verified,
            "name": self.name,
            "picture": self.picture,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
