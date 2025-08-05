from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select
from src.db.db_session import get_engine
from src.db.models.user_profile import user_profile_table
from src.utils.normalize import normalize_postgres_row


def _empty_list_to_none(val):
    return val if val else None


def _enum_to_str_list(items):
    return _empty_list_to_none([str(x).split(".")[-1] for x in items])


def save_user_profile(profile_data: dict):
    """
    Inserts or updates a user profile record in the database.
    Strips enum prefixes and converts empty arrays to NULL before saving.
    """

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
        "longest_run": profile_data.get("longestRun"),
        "run_preference": profile_data["runPreference"],
        # ✅ store natively as boolean
        "has_injury": profile_data["hasInjury"],
        "injury_details": profile_data.get("injuryDetails"),
    }

    engine = get_engine()
    with engine.begin() as conn:
        stmt = (
            insert(user_profile_table)
            .values(**db_data)
            .on_conflict_do_update(index_elements=["user_id"], set_=db_data)
        )
        conn.execute(stmt)


def get_user_profile(user_id: str) -> dict:
    """
    Fetches and normalizes the user profile row by user_id.
    Converts DB-native types (arrays/enums) to clean JSON-safe values.
    """
    engine = get_engine()
    with engine.begin() as conn:
        stmt = select(user_profile_table).where(user_profile_table.c.user_id == user_id)
        result = conn.execute(stmt).mappings().fetchone()
        profile = normalize_postgres_row(result) if result else None

        # ✅ defensive check (optional)
        if profile is not None:
            profile["hasInjury"] = bool(profile["hasInjury"])

        return profile
