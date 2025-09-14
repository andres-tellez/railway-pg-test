# src/db/dao/user_profile_dao.py
from sqlalchemy.orm import Session
from src.db.models.user_profile import UserProfile
from src.utils.normalize import normalize_postgres_row


def _empty_list_to_none(val):
    return val if val else None


def _enum_to_str_list(items):
    return _empty_list_to_none([str(x).split(".")[-1] for x in items])


def save_user_profile(session: Session, profile_data: dict):
    """
    Inserts or updates a user profile record in the database.
    Uses ORM merge() instead of raw insert/update.
    """
    longest_run = profile_data.get("longestRun")

    db_data = {
        "user_id": profile_data["user_id"],
        "runner_level": profile_data["runnerLevel"],
        "race_history": profile_data["raceHistory"],
        "race_date": profile_data.get("raceDate"),
        "race_distance": profile_data.get("raceDistance"),
        "past_races": _enum_to_str_list(profile_data.get("pastRaces", [])),
        "height_feet": profile_data.get("height_feet"),
        "height_inches": profile_data.get("height_inches"),
        "weight": profile_data["weight"],
        "training_days": _empty_list_to_none(
            [str(x).strip() for x in profile_data.get("trainingDays", [])]
        ),
        "main_goal": profile_data["mainGoal"],
        "motivation": _enum_to_str_list(profile_data.get("motivation", [])),
        "age_group": profile_data["ageGroup"],
        "run_preference": profile_data["runPreference"],
    }

    if longest_run is not None:
        db_data["longest_run"] = longest_run

    profile = UserProfile(**db_data)
    session.merge(profile)
    session.commit()
    return profile


def get_user_profile(session: Session, user_id: str) -> dict:
    """
    Fetches and normalizes the user profile row by user_id.
    """
    profile = session.query(UserProfile).filter_by(user_id=user_id).first()
    return normalize_postgres_row(profile.__dict__) if profile else None


def exists_user_profile(session: Session, user_id: str) -> bool:
    """
    Checks if a user profile exists for given user_id.
    """
    return session.query(UserProfile).filter_by(user_id=user_id).first() is not None
