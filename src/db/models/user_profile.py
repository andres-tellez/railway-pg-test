# src/db/models/user_profile.py
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Enum,
    Float,
    Text,
    DateTime,
    BigInteger,
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


class SqliteJSONB(TypeDecorator):
    """
    Emulate PostgreSQL JSONB in SQLite by storing as TEXT (JSON string).
    In PostgreSQL, uses native JSONB type.
    """

    impl = Text

    def load_dialect_impl(self, dialect):
        """Use native JSONB in PostgreSQL, Text in SQLite."""
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB

            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if dialect.name == "sqlite":
            return json.dumps(value) if value is not None else None
        return value

    def process_result_value(self, value, dialect):
        if dialect.name == "sqlite":
            return json.loads(value) if value is not None else None
        return value


class SqliteUUID(TypeDecorator):
    """
    Emulate PostgreSQL UUID in SQLite by storing as TEXT.
    """

    impl = String(36)  # UUIDs are 36 characters with hyphens
    cache_ok = True  # Safe to cache - behavior is deterministic

    def process_bind_param(self, value, dialect):
        """Convert UUID to string for SQLite, pass through for PostgreSQL."""
        if value is None:
            return None
        if dialect.name == "sqlite":
            # Convert UUID to string for SQLite
            return str(value) if hasattr(value, "hex") else value
        return value

    def process_result_value(self, value, dialect):
        """Convert string back to UUID for SQLite, pass through for PostgreSQL."""
        if value is None:
            return None
        if dialect.name == "sqlite":
            # Convert string back to UUID for SQLite
            import uuid as uuid_module

            return uuid_module.UUID(value) if isinstance(value, str) else value
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

    # Physical Stats
    age_group = Column(
        String, nullable=False
    )  # Changed from enum to string to store user-friendly ranges like "30-39"
    height_feet = Column(Integer, nullable=False)
    height_inches = Column(Integer, nullable=False)
    weight = Column(Float)
    # Max HR: user-entered vs activity-estimated; max_hr_active = which drives zones ('manual'|'auto')
    max_hr_manual = Column(Integer, nullable=True)
    max_hr_auto = Column(Integer, nullable=True)
    max_hr_active = Column(String(16), nullable=True)
    resting_hr = Column(Integer, nullable=True)  # Resting heart rate
    resting_hr_source = Column(
        String, nullable=True
    )  # Source of resting_hr: "USER"|"ESTIMATED"
    resting_hr_updated_at = Column(
        DateTime, nullable=True
    )  # When resting_hr was last updated
    hrmax_calculated_at = Column(
        DateTime, nullable=True
    )  # When max_hr_auto was last estimated from activities
    hrmax_confidence = Column(
        String, nullable=True
    )  # Confidence level: "LOW"|"MEDIUM"|"HIGH"
    hrmax_activity_count = Column(
        Integer, nullable=True
    )  # Number of activities used for estimation
    last_hrmax_activity_id = Column(
        BigInteger, nullable=True
    )  # Last activity ID processed for HRmax calculation

    # Display Preferences
    unit_system = Column(
        String(10), nullable=True, default="imperial"
    )  # 'imperial' or 'metric'

    # Note: motivation and training_days columns have been removed from user_profile table
    # They are no longer stored in user_profile
