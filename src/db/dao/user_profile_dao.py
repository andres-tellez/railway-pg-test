# src/db/dao/user_profile_dao.py
from sqlalchemy.orm import Session
from sqlalchemy import text
from src.db.models.user_profile import UserProfile
from src.utils.normalize import normalize_postgres_row


def _empty_list_to_none(val):
    return val if val else None


def _map_motivation_to_db_enum(human_readable_value: str) -> str:
    """
    Maps human-readable motivation values to PostgreSQL enum labels.

    Database enum values: 'Health', 'Competition', 'StressRelief', 'Enjoyment', 'Other'
    Frontend sends: 'Health', 'Stress relief', 'Competition', 'Enjoyment', 'Weight loss', 'Other'
    """
    mapping = {
        "Health": "Health",
        "Stress relief": "StressRelief",
        "Competition": "Competition",
        "Enjoyment": "Enjoyment",
        "Weight loss": "Other",  # Map to Other since WeightLoss doesn't exist in DB enum
        "Other": "Other",
    }
    return mapping.get(human_readable_value, "Other")


def _map_db_enum_to_motivation(db_enum_value: str) -> str:
    """
    Maps PostgreSQL enum labels back to human-readable motivation values.

    Database enum values: 'Health', 'Competition', 'StressRelief', 'Enjoyment', 'Other'
    Frontend expects: 'Health', 'Stress relief', 'Competition', 'Enjoyment', 'Weight loss', 'Other'
    """
    mapping = {
        "Health": "Health",
        "StressRelief": "Stress relief",
        "Competition": "Competition",
        "Enjoyment": "Enjoyment",
        "Other": "Other",
    }
    return mapping.get(db_enum_value, "Other")


def save_user_profile(session: Session, profile_data: dict):
    """
    Inserts or updates a user profile record in the database.
    Uses ORM merge() instead of raw insert/update.
    """
    # Prepare motivation data - map human-readable values to database enum labels
    motivation_raw = profile_data.get("motivation", [])
    motivation_values = None
    if motivation_raw:
        # Map human-readable values to database enum labels
        motivation_values = [_map_motivation_to_db_enum(x) for x in motivation_raw]

    # ageGroup is now a string (e.g., "30-39") - no enum conversion needed
    age_group_value = profile_data.get("ageGroup", "30-39")

    # Check if profile exists
    user_id = profile_data["user_id"]
    existing_profile = session.query(UserProfile).filter_by(user_id=user_id).first()

    if existing_profile:
        # Update existing profile - use raw SQL for motivation to handle enum array casting
        # Update other fields with ORM
        existing_profile.age_group = age_group_value
        existing_profile.height_feet = profile_data.get("height_feet")
        existing_profile.height_inches = profile_data.get("height_inches")
        existing_profile.weight = profile_data.get("weight")

        # For motivation, use raw SQL with proper enum casting
        if motivation_values is not None:
            session.execute(
                text(
                    """
                UPDATE user_profile
                SET motivation = CAST(:motivation AS motivation[])
                WHERE user_id = :user_id
                """
                ),
                {
                    "user_id": user_id,
                    "motivation": motivation_values,
                },
            )
        else:
            existing_profile.motivation = None

        session.commit()
        return session.query(UserProfile).filter_by(user_id=user_id).first()
    else:
        # Create new profile - use raw SQL to properly handle enum array
        if motivation_values is not None:
            session.execute(
                text(
                    """
                INSERT INTO user_profile (user_id, age_group, height_feet, height_inches, weight, motivation)
                VALUES (:user_id, :age_group, :height_feet, :height_inches, :weight, CAST(:motivation AS motivation[]))
                """
                ),
                {
                    "user_id": user_id,
                    "age_group": age_group_value,
                    "height_feet": profile_data.get("height_feet"),
                    "height_inches": profile_data.get("height_inches"),
                    "weight": profile_data.get("weight"),
                    "motivation": motivation_values,
                },
            )
        else:
            session.execute(
                text(
                    """
                INSERT INTO user_profile (user_id, age_group, height_feet, height_inches, weight, motivation)
                VALUES (:user_id, :age_group, :height_feet, :height_inches, :weight, NULL)
                """
                ),
                {
                    "user_id": user_id,
                    "age_group": age_group_value,
                    "height_feet": profile_data.get("height_feet"),
                    "height_inches": profile_data.get("height_inches"),
                    "weight": profile_data.get("weight"),
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
    profile_dict = normalize_postgres_row(profile.__dict__)

    # Map motivation database enum labels back to human-readable values
    if profile_dict.get("motivation") and isinstance(profile_dict["motivation"], list):
        profile_dict["motivation"] = [
            _map_db_enum_to_motivation(db_value)
            for db_value in profile_dict["motivation"]
        ]

    # No reverse mapping needed - age_group is already a user-friendly string like "30-39"

    return profile_dict


def exists_user_profile(session: Session, user_id: str) -> bool:
    """
    Checks if a user profile exists for given user_id.
    """
    return session.query(UserProfile).filter_by(user_id=user_id).first() is not None
