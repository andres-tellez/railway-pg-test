# src/compliance/data_classification.py

from enum import Enum
from typing import Dict, List


class DataCategory(Enum):
    """Data classification categories for compliance"""

    PERSONAL_IDENTIFIABLE = "pii"  # Name, email
    SENSITIVE_HEALTH = "health"  # Heart rate, medical info
    LOCATION_DATA = "location"  # GPS coordinates
    PERFORMANCE_DATA = "performance"  # Running metrics
    CONVERSATION_DATA = "conversation"  # Chat messages
    ANONYMIZED = "anonymized"  # Aggregated, non-identifiable


class DataClassification:
    """Classify data for compliance purposes"""

    CLASSIFICATIONS = {
        # User Profile Data
        "name": DataCategory.PERSONAL_IDENTIFIABLE,
        "email": DataCategory.PERSONAL_IDENTIFIABLE,
        "height": DataCategory.SENSITIVE_HEALTH,
        "weight": DataCategory.SENSITIVE_HEALTH,
        "age_group": DataCategory.PERSONAL_IDENTIFIABLE,
        # Activity Data
        "heart_rate": DataCategory.SENSITIVE_HEALTH,
        "average_heartrate": DataCategory.SENSITIVE_HEALTH,
        "max_heartrate": DataCategory.SENSITIVE_HEALTH,
        "gps_coordinates": DataCategory.LOCATION_DATA,
        "start_location": DataCategory.LOCATION_DATA,
        "end_location": DataCategory.LOCATION_DATA,
        # Performance Data
        "distance": DataCategory.PERFORMANCE_DATA,
        "pace": DataCategory.PERFORMANCE_DATA,
        "time": DataCategory.PERFORMANCE_DATA,
        "splits": DataCategory.PERFORMANCE_DATA,
        # Conversation Data
        "message_content": DataCategory.CONVERSATION_DATA,
        "gpt_response": DataCategory.CONVERSATION_DATA,
    }

    @classmethod
    def get_classification(cls, field_name: str) -> DataCategory:
        """Get data classification for a field"""
        return cls.CLASSIFICATIONS.get(field_name, DataCategory.PERSONAL_IDENTIFIABLE)

    @classmethod
    def requires_consent(cls, field_name: str) -> bool:
        """Check if field requires explicit consent"""
        classification = cls.get_classification(field_name)
        return classification in [
            DataCategory.SENSITIVE_HEALTH,
            DataCategory.LOCATION_DATA,
            DataCategory.CONVERSATION_DATA,
        ]

    @classmethod
    def requires_encryption(cls, field_name: str) -> bool:
        """Check if field requires encryption"""
        classification = cls.get_classification(field_name)
        return classification in [
            DataCategory.SENSITIVE_HEALTH,
            DataCategory.PERSONAL_IDENTIFIABLE,
            DataCategory.LOCATION_DATA,
        ]
