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
class Motivation(str, enum.Enum):
    Health = "Health"
    Competition = "Competition"
    StressRelief = "Stress relief"
    Enjoyment = "Enjoyment"
    WeightLoss = "Weight loss"
    Other = "Other"


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

    # Training Schedule
    training_days = Column(
        PGArray(PGEnum(TrainingDay, name="trainingday", create_type=False)),
        nullable=True,
    )

    # Physical Stats
    age_group = Column(
        String, nullable=False
    )  # Changed from enum to string to store user-friendly ranges like "30-39"
    height_feet = Column(Integer, nullable=False)
    height_inches = Column(Integer, nullable=False)
    weight = Column(Float)

    # Motivation
    motivation = Column(
        PGArray(PGEnum(Motivation, name="motivation", create_type=False)), nullable=True
    )
