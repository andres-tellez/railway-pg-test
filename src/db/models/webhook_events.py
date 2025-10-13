"""
webhook_events.py

Database model for storing Strava webhook events.

This table serves as a queue and audit log for all webhook notifications
received from Strava. Processing happens asynchronously to ensure fast
webhook response times.
"""

from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    DateTime,
    JSON,
    Enum as SQLEnum,
)
from sqlalchemy.sql import func
from src.db.models.base import Base
import enum


class WebhookEventStatus(enum.Enum):
    """Status of webhook event processing"""

    PENDING = "pending"  # Received but not yet processed
    PROCESSING = "processing"  # Currently being processed
    COMPLETED = "completed"  # Successfully processed
    FAILED = "failed"  # Processing failed
    IGNORED = "ignored"  # Event type we don't care about


class WebhookEvent(Base):
    """
    Stores incoming webhook events from Strava.

    Strava sends webhooks for:
    - activity.create
    - activity.update
    - activity.delete
    - athlete.update
    - athlete.delete

    We primarily care about activity.create for automatic syncing.
    """

    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Strava event data
    object_type = Column(String, nullable=False)  # "activity" or "athlete"
    object_id = Column(BigInteger, nullable=False)  # activity_id or athlete_id
    aspect_type = Column(String, nullable=False)  # "create", "update", "delete"
    owner_id = Column(BigInteger, nullable=False)  # athlete_id who owns the object
    subscription_id = Column(BigInteger)  # Strava subscription ID

    # Event metadata
    event_time = Column(BigInteger)  # Unix timestamp from Strava
    updates = Column(JSON)  # Additional data (e.g., {"title": true} for updates)

    # Processing status
    status = Column(
        SQLEnum(WebhookEventStatus),
        nullable=False,
        default=WebhookEventStatus.PENDING,
        index=True,
    )
    error_message = Column(String)  # Store error if processing fails
    retry_count = Column(Integer, default=0)  # Track processing attempts

    # Timestamps
    received_at = Column(DateTime, nullable=False, server_default=func.now())
    processed_at = Column(DateTime)  # When processing completed

    def __repr__(self):
        return (
            f"<WebhookEvent(id={self.id}, "
            f"{self.object_type}.{self.aspect_type}, "
            f"object_id={self.object_id}, "
            f"status={self.status.value})>"
        )

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "object_type": self.object_type,
            "object_id": self.object_id,
            "aspect_type": self.aspect_type,
            "owner_id": self.owner_id,
            "subscription_id": self.subscription_id,
            "event_time": self.event_time,
            "updates": self.updates,
            "status": self.status.value,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "received_at": self.received_at.isoformat() if self.received_at else None,
            "processed_at": (
                self.processed_at.isoformat() if self.processed_at else None
            ),
        }
