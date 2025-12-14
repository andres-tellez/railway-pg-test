# src/db/dao/user_profile_dao.py
from sqlalchemy.orm import Session
from sqlalchemy import text
from src.db.models.user_profile import UserProfile
from src.utils.normalize import normalize_postgres_row


def save_user_profile(session: Session, profile_data: dict):
    """
    Inserts or updates a user profile record in the database.
    Uses ORM merge() instead of raw insert/update.
    """
    # ageGroup is now a string (e.g., "30-39") - no enum conversion needed
    age_group_value = profile_data.get("ageGroup", "30-39")

    # Check if profile exists
    user_id = profile_data["user_id"]
    existing_profile = session.query(UserProfile).filter_by(user_id=user_id).first()

    if existing_profile:
        # Update existing profile
        existing_profile.age_group = age_group_value
        existing_profile.height_feet = profile_data.get("height_feet")
        existing_profile.height_inches = profile_data.get("height_inches")
        existing_profile.weight = profile_data.get("weight")
        existing_profile.max_hr = profile_data.get("max_hr")
        existing_profile.max_hr_source = profile_data.get("max_hr_source")
        existing_profile.resting_hr = profile_data.get("resting_hr")
        existing_profile.resting_hr_source = profile_data.get("resting_hr_source")
        existing_profile.resting_hr_updated_at = profile_data.get(
            "resting_hr_updated_at"
        )
        existing_profile.hrmax_calculated_at = profile_data.get("hrmax_calculated_at")
        existing_profile.hrmax_confidence = profile_data.get("hrmax_confidence")
        existing_profile.hrmax_activity_count = profile_data.get("hrmax_activity_count")
        existing_profile.last_hrmax_activity_id = profile_data.get(
            "last_hrmax_activity_id"
        )
        existing_profile.unit_system = profile_data.get("unit_system")

        session.commit()
        return session.query(UserProfile).filter_by(user_id=user_id).first()
    else:
        # Create new profile
        session.execute(
            text(
                """
            INSERT INTO user_profile (
                user_id, age_group, height_feet, height_inches, weight, max_hr,
                max_hr_source, resting_hr, resting_hr_source, resting_hr_updated_at,
                hrmax_calculated_at, hrmax_confidence,
                hrmax_activity_count, last_hrmax_activity_id, unit_system
            )
            VALUES (
                :user_id, :age_group, :height_feet, :height_inches, :weight, :max_hr,
                :max_hr_source, :resting_hr, :resting_hr_source, :resting_hr_updated_at,
                :hrmax_calculated_at, :hrmax_confidence,
                :hrmax_activity_count, :last_hrmax_activity_id, :unit_system
            )
            """
            ),
            {
                "user_id": user_id,
                "age_group": age_group_value,
                "height_feet": profile_data.get("height_feet"),
                "height_inches": profile_data.get("height_inches"),
                "weight": profile_data.get("weight"),
                "max_hr": profile_data.get("max_hr"),
                "max_hr_source": profile_data.get("max_hr_source"),
                "resting_hr": profile_data.get("resting_hr"),
                "resting_hr_source": profile_data.get("resting_hr_source"),
                "resting_hr_updated_at": profile_data.get("resting_hr_updated_at"),
                "hrmax_calculated_at": profile_data.get("hrmax_calculated_at"),
                "hrmax_confidence": profile_data.get("hrmax_confidence"),
                "hrmax_activity_count": profile_data.get("hrmax_activity_count"),
                "last_hrmax_activity_id": profile_data.get("last_hrmax_activity_id"),
                "unit_system": profile_data.get("unit_system", "imperial"),
            },
        )
        session.commit()
        return session.query(UserProfile).filter_by(user_id=user_id).first()


def get_user_profile(session: Session, user_id: str) -> dict:
    """
    Fetches and normalizes the user profile row by user_id.
    Converts database enum values back to frontend-friendly values.
    """
    profile = session.query(UserProfile).filter_by(user_id=user_id).first()
    if not profile:
        return None

    # Normalize the profile data
    # Use getattr to safely access columns that might not exist in the database
    profile_dict = {}
    for key in [
        "user_id",
        "age_group",
        "height_feet",
        "height_inches",
        "weight",
        "max_hr",
        "max_hr_source",
        "resting_hr",
        "resting_hr_source",
        "resting_hr_updated_at",
        "hrmax_calculated_at",
        "hrmax_confidence",
        "hrmax_activity_count",
        "last_hrmax_activity_id",
        "unit_system",
    ]:
        # Backward compatibility: Use hasattr to safely access columns
        # Returns None if column doesn't exist yet (during migration)
        if hasattr(profile, key):
            profile_dict[key] = getattr(profile, key)
        else:
            # Safe default for new fields during migration
            profile_dict[key] = None

    # Normalize any enum/array values
    profile_dict = normalize_postgres_row(profile_dict)

    # Note: motivation and training_days columns have been removed from user_profile table
    # They are no longer stored in user_profile

    # No reverse mapping needed - age_group is already a user-friendly string like "30-39"

    return profile_dict


def exists_user_profile(session: Session, user_id: str) -> bool:
    """
    Checks if a user profile exists for given user_id.
    """
    return session.query(UserProfile).filter_by(user_id=user_id).first() is not None
