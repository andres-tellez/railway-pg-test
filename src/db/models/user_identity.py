# src/db/models/user_identity.py

from sqlalchemy import Column, String, Boolean, DateTime
from datetime import datetime
from src.db.db_session import Base


class UserIdentity(Base):
    __tablename__ = "user_identity"

    user_id = Column(String, primary_key=True)
    email = Column(String, nullable=True)
    email_verified = Column(Boolean, nullable=True)
    name = Column(String, nullable=True)
    picture = Column(String, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "email": self.email,
            "email_verified": self.email_verified,
            "name": self.name,
            "picture": self.picture,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
