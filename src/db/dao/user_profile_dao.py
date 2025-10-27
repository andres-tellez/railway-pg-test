# src/db/dao/user_profile_dao.py
from sqlalchemy.orm import Session
from sqlalchemy import text
from src.db.models.user_profile import UserProfile
from src.utils.normalize import normalize_postgres_row
from src.db.enums.user_profile_enums import Motivation, TrainingDay


def _empty_list_to_none(val):
    return val if val else None


def save_user_profile(session: Session, profile_data: dict):
    """
    Inserts or updates a user profile record in the database.
    Uses ORM merge() instead of raw insert/update.
    """
    # Prepare data for ORM
    training_days = _empty_list_to_none(
        [TrainingDay(x) for x in profile_data.get("trainingDays", [])]
    )
    motivation = _empty_list_to_none(
        [Motivation(x) for x in profile_data.get("motivation", [])]
    )

    # ageGroup is now a string (e.g., "30-39") - no enum conversion needed
    age_group_value = profile_data.get("ageGroup", "30-39")

    # Check if profile exists
    user_id = profile_data["user_id"]
    existing_profile = session.query(UserProfile).filter_by(user_id=user_id).first()

    if existing_profile:
        # Update existing profile - bypass ORM enum conversion by using raw SQL
        # Use explicit enum cast to ensure the value is accepted
        session.execute(
            text(
                """
            UPDATE user_profile
            SET age_group = :age_group,
                height_feet = :height_feet,
                height_inches = :height_inches,
                weight = :weight
            WHERE user_id = :user_id
            """
            ),
            {
                "user_id": user_id,
                "age_group": age_group_value,  # This is now a string like "30-39"
                "height_feet": profile_data.get("height_feet"),
                "height_inches": profile_data.get("height_inches"),
                "weight": profile_data.get("weight"),
            },
        )
        # Update the array fields with ORM (they work fine)
        existing_profile.training_days = training_days
        existing_profile.motivation = motivation
        session.commit()
        return session.query(UserProfile).filter_by(user_id=user_id).first()
    else:
        # Create new profile
        new_profile = UserProfile(
            user_id=user_id,
            age_group=age_group_value,  # String like "30-39"
            height_feet=profile_data.get("height_feet"),
            height_inches=profile_data.get("height_inches"),
            weight=profile_data.get("weight"),
            training_days=training_days,
            motivation=motivation,
        )
        session.add(new_profile)
        session.commit()
        return new_profile


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

    # No reverse mapping needed - age_group is already a user-friendly string like "30-39"

    return profile_dict


def exists_user_profile(session: Session, user_id: str) -> bool:
    """
    Checks if a user profile exists for given user_id.
    """
    return session.query(UserProfile).filter_by(user_id=user_id).first() is not None
