"""
Strava Sync Service

Service to sync user data from Strava, including max heart rate.
"""

import logging
from sqlalchemy.orm import Session
from src.services.strava_access_service import StravaClient
from src.services.token_service import get_valid_token
from src.db.dao.user_profile_dao import save_user_profile, get_user_profile
from src.db.dao.user_athletes_dao import get_by_user_id
from src.utils.strava_exceptions import (
    StravaTokenNotFoundError,
    StravaTokenRefreshError,
    StravaTokenRevokedError,
)

logger = logging.getLogger(__name__)


def sync_max_hr_from_strava(session: Session, user_id: str) -> tuple[bool, str]:
    """
    Sync max heart rate from Strava to user profile.

    Args:
        session: Database session
        user_id: User ID

    Returns:
        Tuple of (success: bool, error_message: str)
        If success is True, error_message is empty
        If success is False, error_message contains the reason
    """
    try:
        # Get athlete_id for this user
        link = get_by_user_id(user_id)
        if not link:
            error_msg = (
                "No Strava account linked. Please connect your Strava account first."
            )
            logger.warning(f"No athlete link found for user {user_id}")
            return False, error_msg
        athlete_id = link.athlete_id

        # Get valid access token
        try:
            access_token = get_valid_token(session, athlete_id)
        except StravaTokenNotFoundError:
            error_msg = "No Strava tokens found. Please reconnect your Strava account."
            logger.warning(f"No tokens found for athlete {athlete_id}")
            return False, error_msg
        except StravaTokenRevokedError:
            error_msg = (
                "Strava tokens have been revoked. Please reconnect your Strava account."
            )
            logger.warning(f"Tokens revoked for athlete {athlete_id}")
            return False, error_msg
        except StravaTokenRefreshError as e:
            error_msg = f"Failed to refresh Strava tokens: {str(e)}. Please reconnect your Strava account."
            logger.warning(f"Failed to refresh token for athlete {athlete_id}: {e}")
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error accessing Strava: {str(e)}"
            logger.error(
                f"Unexpected error getting token for athlete {athlete_id}: {e}"
            )
            return False, error_msg

        # Fetch athlete profile from Strava
        try:
            client = StravaClient(access_token)
            athlete_data = client.get_athlete()
            logger.debug(f"Athlete data from Strava API: {athlete_data}")
        except Exception as e:
            error_msg = f"Failed to fetch data from Strava: {str(e)}"
            logger.error(f"Error fetching athlete data from Strava: {e}")
            return False, error_msg

        # Check for max_heartrate in the response
        max_hr = athlete_data.get("max_heartrate")
        logger.info(f"Max HR from Strava API: {max_hr} (type: {type(max_hr)})")

        # Also check for alternative field names or nested structures
        if not max_hr:
            # Check if it's in a different field
            logger.debug(f"Full athlete data keys: {list(athlete_data.keys())}")
            # Some APIs might return it as null instead of missing
            if (
                "max_heartrate" in athlete_data
                and athlete_data["max_heartrate"] is None
            ):
                logger.info(
                    f"max_heartrate field exists but is None for athlete {athlete_id}"
                )

        if not max_hr:
            error_msg = "No max heart rate found in your Strava profile. Please set your max HR in Strava (Settings → My Performance → Heart Rate Zones). Note: The max HR must be set in your Strava account settings for it to sync."
            logger.info(
                f"No max_heartrate in Strava profile for athlete {athlete_id}. Available fields: {list(athlete_data.keys())}"
            )
            return False, error_msg

        # Get current user profile
        current_profile = get_user_profile(session, user_id)
        if not current_profile:
            error_msg = "User profile not found. Please complete your profile first."
            logger.warning(f"No user profile found for user {user_id}")
            return False, error_msg

        # Update profile with Strava max HR
        profile_data = {
            "user_id": user_id,
            "ageGroup": current_profile.get("age_group", "30-39"),
            "height_feet": current_profile.get("height_feet"),
            "height_inches": current_profile.get("height_inches"),
            "weight": current_profile.get("weight"),
            "max_hr": max_hr,
            "motivation": current_profile.get("motivation", []),
        }

        save_user_profile(session, profile_data)
        logger.info(f"Synced max HR {max_hr} from Strava for user {user_id}")

        # Recalculate HR zones for all active plans
        try:
            from src.services.training_plan.recalculate_hr_zones_service import (
                recalculate_hr_zones_for_user,
            )

            recalc_results = recalculate_hr_zones_for_user(session, user_id)
            logger.info(
                f"Recalculated HR zones for {len(recalc_results)} plans after max HR sync"
            )
        except Exception as e:
            # Log but don't fail the sync if recalculation fails
            logger.warning(f"Could not recalculate HR zones after max HR sync: {e}")

        return True, ""

    except Exception as e:
        error_msg = f"Unexpected error syncing max HR: {str(e)}"
        logger.error(
            f"Error syncing max HR from Strava for user {user_id}: {e}", exc_info=True
        )
        return False, error_msg
