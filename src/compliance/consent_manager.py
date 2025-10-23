# src/compliance/consent_manager.py

import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.db.db_session import Base
from src.compliance.data_classification import DataCategory


class ConsentType(Enum):
    """Types of consent for data processing"""

    DATA_COLLECTION = "data_collection"
    DATA_PROCESSING = "data_processing"
    DATA_SHARING = "data_sharing"
    AI_ANALYSIS = "ai_analysis"
    HEALTH_DATA = "health_data"
    LOCATION_DATA = "location_data"
    CONVERSATION_STORAGE = "conversation_storage"


class ConsentStatus(Enum):
    """Consent status"""

    GRANTED = "granted"
    DENIED = "denied"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"


class UserConsent(Base):
    """User consent tracking for compliance"""

    __tablename__ = "user_consents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("user_identity.user_id"), nullable=False
    )
    consent_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)
    granted_at = Column(DateTime, nullable=True)
    withdrawn_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    consent_text = Column(Text, nullable=True)
    version = Column(String(10), nullable=False, default="1.0")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ConsentManager:
    """Manage user consent for data processing"""

    REQUIRED_CONSENTS = {
        ConsentType.DATA_COLLECTION: {
            "description": "Collect and store your running data, profile information, and conversation history",
            "required_for": [
                DataCategory.PERSONAL_IDENTIFIABLE,
                DataCategory.PERFORMANCE_DATA,
            ],
        },
        ConsentType.HEALTH_DATA: {
            "description": "Process heart rate and health-related metrics from your activities",
            "required_for": [DataCategory.SENSITIVE_HEALTH],
        },
        ConsentType.LOCATION_DATA: {
            "description": "Store GPS coordinates from your running activities",
            "required_for": [DataCategory.LOCATION_DATA],
        },
        ConsentType.AI_ANALYSIS: {
            "description": "Use AI to analyze your data and provide personalized coaching advice",
            "required_for": [DataCategory.CONVERSATION_DATA],
        },
        ConsentType.CONVERSATION_STORAGE: {
            "description": "Store conversation history to provide contextual coaching",
            "required_for": [DataCategory.CONVERSATION_DATA],
        },
    }

    @classmethod
    def check_consent(
        cls, session, user_id: str, data_categories: List[DataCategory]
    ) -> bool:
        """Check if user has consented to process specific data categories"""

        required_consents = []
        for category in data_categories:
            for consent_type, details in cls.REQUIRED_CONSENTS.items():
                if category in details["required_for"]:
                    required_consents.append(consent_type)

        # Check if user has granted all required consents
        for consent_type in required_consents:
            consent = (
                session.query(UserConsent)
                .filter_by(
                    user_id=user_id,
                    consent_type=consent_type.value,
                    status=ConsentStatus.GRANTED.value,
                )
                .first()
            )

            if not consent or (
                consent.expires_at and consent.expires_at < datetime.utcnow()
            ):
                return False

        return True

    @classmethod
    def grant_consent(
        cls,
        session,
        user_id: str,
        consent_type: ConsentType,
        consent_text: str = None,
        expires_in_days: int = 365,
    ) -> UserConsent:
        """Grant consent for data processing"""

        # Withdraw any existing consent
        existing = (
            session.query(UserConsent)
            .filter_by(user_id=user_id, consent_type=consent_type.value)
            .first()
        )

        if existing:
            existing.status = ConsentStatus.WITHDRAWN.value
            existing.withdrawn_at = datetime.utcnow()

        # Create new consent
        consent = UserConsent(
            user_id=user_id,
            consent_type=consent_type.value,
            status=ConsentStatus.GRANTED.value,
            granted_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=expires_in_days),
            consent_text=consent_text
            or cls.REQUIRED_CONSENTS[consent_type]["description"],
        )

        session.add(consent)
        session.commit()
        return consent

    @classmethod
    def withdraw_consent(cls, session, user_id: str, consent_type: ConsentType) -> bool:
        """Withdraw consent for data processing"""

        consent = (
            session.query(UserConsent)
            .filter_by(
                user_id=user_id,
                consent_type=consent_type.value,
                status=ConsentStatus.GRANTED.value,
            )
            .first()
        )

        if consent:
            consent.status = ConsentStatus.WITHDRAWN.value
            consent.withdrawn_at = datetime.utcnow()
            session.commit()
            return True

        return False
