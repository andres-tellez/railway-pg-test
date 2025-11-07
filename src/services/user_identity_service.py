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
    import logging

    logger = logging.getLogger(__name__)

    # Ensure user_id is a string (might be UUID object)
    user_id_str = str(user_id) if user_id else None
    if not user_id_str:
        logger.warning("get_user_status called with None or empty user_id")
        return {"hasOnboarded": False, "hasStrava": False}

    print(
        f"[DEBUG] 🔍 get_user_status called with user_id={user_id_str} (type: {type(user_id).__name__})"
    )
    logger.info(
        f"🔍 get_user_status called with user_id={user_id_str} (type: {type(user_id).__name__})"
    )

    session = get_session()
    try:
        has_onboarded = (
            session.execute(
                select(UserProfile).where(UserProfile.user_id == user_id_str)
            ).scalar_one_or_none()
            is not None
        )

        link = get_by_user_id(user_id_str)
        has_strava = link is not None

        print(
            f"[DEBUG] ✅ User status for {user_id_str}: hasOnboarded={has_onboarded}, hasStrava={has_strava}, link={'found' if link else 'not found'}"
        )
        logger.info(
            f"✅ User status for {user_id_str}: hasOnboarded={has_onboarded}, hasStrava={has_strava}, "
            f"link={'found' if link else 'not found'}"
        )

        if link:
            print(
                f"[DEBUG]    Link details: user_id={link.user_id}, athlete_id={link.athlete_id}"
            )
            logger.info(
                f"   Link details: user_id={link.user_id}, athlete_id={link.athlete_id}"
            )
        else:
            # Debug: check if any links exist at all
            from src.db.models.user_athletes import UserAthleteLink

            all_links = session.query(UserAthleteLink).all()
            print(f"[DEBUG]    No link found. Total links in DB: {len(all_links)}")
            logger.info(f"   No link found. Total links in DB: {len(all_links)}")
            if all_links:
                print(
                    f"[DEBUG]    Sample link user_id: {all_links[0].user_id} (type: {type(all_links[0].user_id).__name__})"
                )
                logger.info(
                    f"   Sample link user_id: {all_links[0].user_id} (type: {type(all_links[0].user_id).__name__})"
                )

        return {"hasOnboarded": has_onboarded, "hasStrava": has_strava}
    finally:
        session.close()
