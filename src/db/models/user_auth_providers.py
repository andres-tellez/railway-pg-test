from sqlalchemy import Column, String, ForeignKey, DateTime, func, PrimaryKeyConstraint
from src.db.db_session import Base


class UserAuthProvider(Base):
    __tablename__ = "user_auth_providers"

    user_id = Column(String, ForeignKey("user_identity.user_id"), nullable=False)
    provider_name = Column(String, nullable=False)
    provider_user_id = Column(String, nullable=False)
    full_provider_id = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (PrimaryKeyConstraint("provider_name", "provider_user_id"),)
