# src/db/dao/user_profile_dao.py
from sqlalchemy.orm import Session
from src.db.models.user_profile import UserProfile
from src.utils.normalize import normalize_postgres_row


def save_user_profile(session: Session, profile_data: dict):
    """
    Inserts or updates a user profile record.
    Expects a full row dict when updating (merge patch + existing in the route),
    so nullable fields are not accidentally wiped by None from partial payloads.
    """
    age_group_value = profile_data.get("age_group") or profile_data.get(
        "ageGroup", "30-39"
    )
    user_id = profile_data["user_id"]
    existing_profile = session.query(UserProfile).filter_by(user_id=user_id).first()

    if existing_profile:
        existing_profile.age_group = age_group_value
        existing_profile.height_feet = profile_data.get("height_feet")
        existing_profile.height_inches = profile_data.get("height_inches")
        existing_profile.weight = profile_data.get("weight")
        existing_profile.max_hr_manual = profile_data.get("max_hr_manual")
        existing_profile.max_hr_auto = profile_data.get("max_hr_auto")
        existing_profile.max_hr_active = profile_data.get("max_hr_active")
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

    new_profile = UserProfile(
        user_id=user_id,
        age_group=age_group_value,
        height_feet=profile_data.get("height_feet"),
        height_inches=profile_data.get("height_inches"),
        weight=profile_data.get("weight"),
        max_hr_manual=profile_data.get("max_hr_manual"),
        max_hr_auto=profile_data.get("max_hr_auto"),
        max_hr_active=profile_data.get("max_hr_active"),
        resting_hr=profile_data.get("resting_hr"),
        resting_hr_source=profile_data.get("resting_hr_source"),
        resting_hr_updated_at=profile_data.get("resting_hr_updated_at"),
        hrmax_calculated_at=profile_data.get("hrmax_calculated_at"),
        hrmax_confidence=profile_data.get("hrmax_confidence"),
        hrmax_activity_count=profile_data.get("hrmax_activity_count"),
        last_hrmax_activity_id=profile_data.get("last_hrmax_activity_id"),
        unit_system=profile_data.get("unit_system", "imperial"),
    )
    session.add(new_profile)
    session.commit()
    return session.query(UserProfile).filter_by(user_id=user_id).first()


def get_user_profile(session: Session, user_id: str) -> dict:
    """
    Fetches and normalizes the user profile row by user_id.
    """
    profile = session.query(UserProfile).filter_by(user_id=user_id).first()
    if not profile:
        return None

    profile_dict = {}
    for key in [
        "user_id",
        "age_group",
        "height_feet",
        "height_inches",
        "weight",
        "max_hr_manual",
        "max_hr_auto",
        "max_hr_active",
        "resting_hr",
        "resting_hr_source",
        "resting_hr_updated_at",
        "hrmax_calculated_at",
        "hrmax_confidence",
        "hrmax_activity_count",
        "last_hrmax_activity_id",
        "unit_system",
    ]:
        if hasattr(profile, key):
            profile_dict[key] = getattr(profile, key)
        else:
            profile_dict[key] = None

    profile_dict = normalize_postgres_row(profile_dict)

    return profile_dict


def exists_user_profile(session: Session, user_id: str) -> bool:
    """
    Checks if a user profile exists for given user_id.
    """
    return session.query(UserProfile).filter_by(user_id=user_id).first() is not None
