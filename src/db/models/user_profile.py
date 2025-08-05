from sqlalchemy import (
    Table,
    Column,
    Integer,
    String,
    Boolean,
    Enum,
    Float,
    MetaData,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY
import enum

metadata = MetaData()


# Enumerations
class RunnerLevel(str, enum.Enum):
    Beginner = "Beginner"
    Intermediate = "Intermediate"
    Expert = "Expert"


class RaceDistance(str, enum.Enum):
    _5K = "5K"
    _10K = "10K"
    Half = "Half Marathon"
    Marathon = "Marathon"
    Ultra = "Ultra"
    Other = "Other"


class PastRace(str, enum.Enum):
    _5K = "5K"
    _10K = "10K"
    Half = "Half Marathon"
    Marathon = "Marathon"
    Ultra = "Ultra"
    NoneYet = "Haven't raced yet"


class Goal(str, enum.Enum):
    Fitness = "General fitness"
    Race = "Run a race"
    LoseWeight = "Lose weight"
    Faster = "Run faster"
    Other = "Other"


class Motivation(str, enum.Enum):
    Health = "Health"
    Competition = "Competition"
    StressRelief = "Stress relief"
    Enjoyment = "Enjoyment"
    Other = "Other"


class AgeGroup(str, enum.Enum):
    Under18 = "Under 18"
    Age18_24 = "18-24"
    Age25_34 = "25-34"
    Age35_44 = "35-44"
    Age45_54 = "45-54"
    Age55Plus = "55+"


class RunPreference(str, enum.Enum):
    Distance = "Distance"
    Time = "Time"
    NonePref = "No preference"


# ✅ NEW ENUM for has_injury
class HasInjury(str, enum.Enum):
    Yes = "Yes"
    No = "No"


# SQLAlchemy Core Table
user_profile_table = Table(
    "user_profile",
    metadata,
    Column("user_id", String, primary_key=True),
    Column("runner_level", Enum(RunnerLevel), nullable=False),
    Column("race_history", Boolean, nullable=False),
    Column("race_date", String),
    Column("race_distance", Enum(RaceDistance)),
    Column("past_races", ARRAY(Enum(PastRace))),
    Column("height_feet", Integer, nullable=False),
    Column("height_inches", Integer, nullable=False),
    Column("weight", Float, nullable=False),
    Column("training_days", ARRAY(String)),
    Column("main_goal", Enum(Goal), nullable=False),
    Column("motivation", ARRAY(Enum(Motivation)), nullable=False),
    Column("age_group", Enum(AgeGroup), nullable=False),
    Column("longest_run", Float),
    Column("run_preference", Enum(RunPreference), nullable=False),
    # ✅ CHANGED: from Boolean → Enum(HasInjury)
    Column("has_injury", Enum(HasInjury), nullable=False),
    Column("injury_details", Text),
)

__all__ = ["user_profile_table"]
