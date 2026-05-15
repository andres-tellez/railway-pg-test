"""
Append-only product / funnel analytics events (pilot MVP).

Query with SQL by event_name, outcome, and created_at. Optional properties JSON
for counts, error codes, trace ids, etc.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID

from src.db.db_session import Base


class ProductAnalyticsEvent(Base):
    __tablename__ = "product_analytics_event"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=True, index=True)
    event_name = Column(String, nullable=False, index=True)
    outcome = Column(String, nullable=False, index=True)
    source = Column(String, nullable=False, default="server")
    correlation_id = Column(String, nullable=True, index=True)
    client_event_id = Column(String, nullable=True, index=True)
    properties = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
