"""
Authentication Audit Log Model
===============================

Stores structured audit logs for authentication events.

Events logged:
- login (success/failure)
- logout
- token_refresh
- token_revocation
- oauth_callback
- account_linking

Used for:
- Security monitoring
- Compliance (GDPR, SOC2)
- Attack detection
- Forensic analysis
"""

from sqlalchemy import Column, String, DateTime, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from src.db.db_session import Base


class AuthAuditLog(Base):
    __tablename__ = "auth_audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=True, index=True)  # Internal user_id (UUID)
    auth0_sub = Column(String, nullable=True, index=True)  # Auth0 subject
    athlete_id = Column(String, nullable=True, index=True)  # Strava athlete ID

    event_type = Column(
        String, nullable=False, index=True
    )  # login, logout, token_refresh, etc.
    event_status = Column(String, nullable=False)  # success, failure
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)

    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    details = Column(JSON, nullable=True)  # Additional context (error messages, etc.)
    message = Column(Text, nullable=True)  # Human-readable message

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            "id": str(self.id),
            "user_id": self.user_id,
            "auth0_sub": self.auth0_sub,
            "athlete_id": self.athlete_id,
            "event_type": self.event_type,
            "event_status": self.event_status,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "details": self.details,
            "message": self.message,
        }
