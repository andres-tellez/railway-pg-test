# src/services/user_identity_service.py
from __future__ import annotations
from datetime import datetime

from sqlalchemy import select

from src.db.db_session import get_session
from src.db.models import UserIdentity
from src.db.models.user_profile import UserProfile
from src.db.dao.user_athletes_dao import get_by_user_id

from src.db.dao.user_identity_dao import (
    upsert_identity,
    resolve_user_id_from_auth_provider,  # ✅ single source of truth
)
from src.utils.normalize_claims import normalize_claims


def get_user_status(user_id: str) -> dict:
    """
    Check if the user has completed onboarding (UserProfile exists)
    and whether they have linked a Strava athlete.
    """
    session = get_session()
    try:
        has_onboarded = (
            session.execute(
                select(UserProfile).where(UserProfile.user_id == user_id)
            ).scalar_one_or_none()
            is not None
        )

        link = get_by_user_id(user_id)
        has_strava = link is not None

        return {"hasOnboarded": has_onboarded, "hasStrava": has_strava}
    finally:
        session.close()
