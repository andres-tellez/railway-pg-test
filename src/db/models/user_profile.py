# src/db/models/user_profile.py
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Enum,
    Float,
    Text,
)
from sqlalchemy.dialects.postgresql import ENUM as PGEnum, ARRAY as PGArray
from sqlalchemy.types import TypeDecorator
from sqlalchemy.ext.declarative import declarative_base
import enum
import json
from src.db.db_session import Base


# ---------------------------
# Cross-database compatibility
# ---------------------------
class SqliteArray(TypeDecorator):
    """
    Emulate PostgreSQL ARRAY in SQLite by storing as JSON.
    """

    impl = Text

    def process_bind_param(self, value, dialect):
        if dialect.name == "sqlite":
            return json.dumps(value) if value is not None else None
        return value

    def process_result_value(self, value, dialect):
        if dialect.name == "sqlite":
            return json.loads(value) if value is not None else None
        return value


def ArrayType(base_type):
    """Return ARRAY for Postgres, SqliteArray otherwise."""

    def _factory():
        from sqlalchemy import inspect

        return (
            ARRAY(base_type)
            if base_type
            and Base.metadata.bind
            and Base.metadata.bind.dialect.name == "postgresql"
            else SqliteArray()
        )

    return SqliteArray()  # default fallback; we’ll override properly in columns


# ---------------------------
# Enumerations
# ---------------------------
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


class TrainingDay(str, enum.Enum):
    MON = "Mon"
    TUE = "Tue"
    WED = "Wed"
    THU = "Thu"
    FRI = "Fri"
    SAT = "Sat"
    SUN = "Sun"


# ---------------------------
# ORM Model
# ---------------------------
class UserProfile(Base):
    __tablename__ = "user_profile"

    user_id = Column(String, primary_key=True)
    runner_level = Column(Enum(RunnerLevel), nullable=False)
    race_history = Column(Boolean, nullable=False)
    race_date = Column(String)
    race_distance = Column(Enum(RaceDistance))
    past_races = Column(
        PGArray(PGEnum(PastRace, name="pastrace", create_type=False)), nullable=True
    )
    height_feet = Column(Integer, nullable=False)
    height_inches = Column(Integer, nullable=False)
    weight = Column(Float, nullable=False)
    training_days = Column(
        PGArray(PGEnum(TrainingDay, name="trainingday", create_type=True)),
        nullable=True,
    )

    main_goal = Column(Enum(Goal), nullable=False)
    motivation = Column(
        PGArray(PGEnum(Motivation, name="motivation", create_type=False)), nullable=True
    )
    age_group = Column(Enum(AgeGroup), nullable=False)
    longest_run = Column(Float)
    run_preference = Column(Enum(RunPreference), nullable=False)
