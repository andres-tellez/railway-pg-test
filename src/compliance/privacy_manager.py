# src/compliance/privacy_manager.py

import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy import text
from src.db.db_session import get_session
from src.compliance.data_classification import DataCategory, DataClassification


class PrivacyManager:
    """Handle data privacy, anonymization, and user rights"""

    @classmethod
    def anonymize_data(cls, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Anonymize data by removing/masking sensitive fields"""

        anonymized = {}
        for key, value in data.items():
            classification = DataClassification.get_classification(key)

            if classification == DataCategory.PERSONAL_IDENTIFIABLE:
                # Hash personal identifiers
                anonymized[key] = cls._hash_identifier(value)
            elif classification == DataCategory.SENSITIVE_HEALTH:
                # Remove or aggregate health data
                anonymized[key] = cls._anonymize_health_data(key, value)
            elif classification == DataCategory.LOCATION_DATA:
                # Generalize location data (remove precise coordinates)
                anonymized[key] = cls._generalize_location(value)
            else:
                # Keep other data as-is
                anonymized[key] = value

        return anonymized

    @classmethod
    def _hash_identifier(cls, value: Any) -> str:
        """Hash personal identifiers"""
        if value is None:
            return None
        return hashlib.sha256(str(value).encode()).hexdigest()[:16]

    @classmethod
    def _anonymize_health_data(cls, field: str, value: Any) -> Any:
        """Anonymize health-related data"""
        if field in ["heart_rate", "average_heartrate", "max_heartrate"]:
            # Round to nearest 10 to reduce precision
            return round(value / 10) * 10 if value else None
        return value

    @classmethod
    def _generalize_location(cls, value: Any) -> Any:
        """Generalize location data"""
        if value is None:
            return None
        # Remove precise coordinates, keep only general area
        return "General Area" if isinstance(value, str) else None

    @classmethod
    def get_user_data_export(cls, session, user_id: str) -> Dict[str, Any]:
        """Export all user data for GDPR compliance"""

        export_data = {
            "export_date": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "data_categories": {},
        }

        # Export user profile
        profile = session.execute(
            text(
                """
            SELECT * FROM user_profile WHERE user_id = :user_id
        """
            ),
            {"user_id": user_id},
        ).fetchone()

        if profile:
            export_data["data_categories"]["profile"] = dict(profile._mapping)

        # Export activities (anonymized)
        activities = session.execute(
            text(
                """
            SELECT * FROM v_completed_activities
            WHERE user_id = :user_id
            ORDER BY start_date DESC
        """
            ),
            {"user_id": user_id},
        ).fetchall()

        if activities:
            export_data["data_categories"]["activities"] = [
                cls.anonymize_data(dict(activity._mapping), user_id)
                for activity in activities
            ]

        # Export conversations
        conversations = session.execute(
            text(
                """
            SELECT c.*, json_agg(
                json_build_object(
                    'role', m.role,
                    'content', m.content,
                    'created_at', m.created_at
                ) ORDER BY m.created_at
            ) as messages
            FROM conversations c
            LEFT JOIN conversation_messages m ON c.id = m.conversation_id
            WHERE c.user_id = :user_id
            GROUP BY c.id
        """
            ),
            {"user_id": user_id},
        ).fetchall()

        if conversations:
            export_data["data_categories"]["conversations"] = [
                dict(conv._mapping) for conv in conversations
            ]

        return export_data

    @classmethod
    def delete_user_data(cls, session, user_id: str) -> bool:
        """Delete all user data for GDPR compliance"""

        try:
            # Delete conversations and messages
            session.execute(
                text(
                    """
                DELETE FROM conversation_messages
                WHERE conversation_id IN (
                    SELECT id FROM conversations WHERE user_id = :user_id
                )
            """
                ),
                {"user_id": user_id},
            )

            session.execute(
                text(
                    """
                DELETE FROM conversations WHERE user_id = :user_id
            """
                ),
                {"user_id": user_id},
            )

            # Delete user profile
            session.execute(
                text(
                    """
                DELETE FROM user_profile WHERE user_id = :user_id
            """
                ),
                {"user_id": user_id},
            )

            # Delete user identity
            session.execute(
                text(
                    """
                DELETE FROM user_identity WHERE user_id = :user_id
            """
                ),
                {"user_id": user_id},
            )

            # Note: We don't delete activities as they come from Strava
            # User should delete them from Strava directly

            session.commit()
            return True

        except Exception as e:
            session.rollback()
            print(f"Error deleting user data: {e}")
            return False

    @classmethod
    def get_data_retention_policy(cls) -> Dict[str, Any]:
        """Get data retention policy"""

        return {
            "conversation_data": {
                "retention_period": "2 years",
                "reason": "Provide contextual coaching and improve service",
            },
            "activity_data": {
                "retention_period": "Indefinite (controlled by Strava)",
                "reason": "Historical performance analysis",
            },
            "user_profile": {
                "retention_period": "Account lifetime + 1 year",
                "reason": "Service provision and legal requirements",
            },
            "consent_records": {
                "retention_period": "7 years",
                "reason": "Legal compliance and audit requirements",
            },
        }
