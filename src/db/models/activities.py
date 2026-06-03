from sqlalchemy import (
    Column,
    BigInteger,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
)
from src.db.db_session import Base
from src.db.models.user_profile import (
    SqliteUUID,
    SqliteJSONB,
)  # Import SQLite-compatible types


class Activity(Base):
    __tablename__ = "activities"

    activity_id = Column(
        BigInteger, primary_key=True, index=True
    )  # Strava’s activity ID
    athlete_id = Column(
        BigInteger, ForeignKey("user_athletes.athlete_id"), nullable=False, index=True
    )
    user_id = Column(
        SqliteUUID(),  # SQLite-compatible UUID type
        ForeignKey("user_identity.user_id"),
        nullable=True,  # NULL = not linked to an app account (e.g. wrong-athlete cleanup f013)
        index=True,
    )

    name = Column(String)
    type = Column(String)
    start_date = Column(DateTime)
    distance = Column(Float)
    elapsed_time = Column(Integer)
    moving_time = Column(Integer)
    total_elevation_gain = Column(Float)
    external_id = Column(String)
    timezone = Column(String)

    average_speed = Column(Float)
    max_speed = Column(Float)
    suffer_score = Column(Float)
    average_heartrate = Column(Float)
    max_heartrate = Column(Float)
    calories = Column(Float)

    conv_distance = Column(Float)
    conv_elevation_feet = Column(Float)
    conv_avg_speed = Column(Float)
    conv_max_speed = Column(Float)
    conv_moving_time = Column(String)
    conv_elapsed_time = Column(String)

    # HR Zone enrichment
    hr_zone_1 = Column(Float)
    hr_zone_2 = Column(Float)
    hr_zone_3 = Column(Float)
    hr_zone_4 = Column(Float)
    hr_zone_5 = Column(Float)

    # Phase 1: planned vs executed classification + scoring
    matched_plan_workout_id = Column(
        Integer, ForeignKey("plan_workouts.id"), nullable=True, index=True
    )
    planned_type = Column(String(32), nullable=True)
    executed_type = Column(String(32), nullable=True)
    zone_compliance_pct = Column(Float, nullable=True)
    pct_above_zone = Column(Float, nullable=True)
    pct_below_zone = Column(Float, nullable=True)
    run_score = Column(String(16), nullable=True)
    scoring_detail = Column(SqliteJSONB(), nullable=True)
    planned_miles = Column(Float, nullable=True)
    actual_miles = Column(Float, nullable=True)
    completion_pct = Column(Float, nullable=True)

    # Strava detail API + zones applied (enrichment pass completed)
    detail_enriched_at = Column(DateTime(timezone=True), nullable=True)

    # Tier 2: execution_analytics (Insights classification + KPIs + tempo segment)
    insights_system = Column(String(16), nullable=True)
    easy_pct = Column(Float, nullable=True)
    z2_band_pct = Column(Float, nullable=True)
    hr_drift_pct = Column(Float, nullable=True)
    pace_spread = Column(Float, nullable=True)
    tempo_segment_pace_min_per_mi = Column(Float, nullable=True)
    tempo_segment_avg_hr_bpm = Column(Float, nullable=True)
    tempo_segment_pace_source = Column(String(32), nullable=True)
    tempo_segment_split_count = Column(Integer, nullable=True)
    tempo_segment_confidence = Column(String(8), nullable=True)
    tempo_qualifying_distance_mi = Column(Float, nullable=True)
    threshold_segment_pace_min_per_mi = Column(Float, nullable=True)
    threshold_segment_avg_hr_bpm = Column(Float, nullable=True)
    threshold_segment_pace_source = Column(String(32), nullable=True)
    threshold_segment_split_count = Column(Integer, nullable=True)
    threshold_segment_confidence = Column(String(8), nullable=True)
    threshold_qualifying_distance_mi = Column(Float, nullable=True)
    execution_kpis_computed_at = Column(DateTime(timezone=True), nullable=True)
    execution_zone_profile_at = Column(DateTime(timezone=True), nullable=True)
    execution_analytics_version = Column(String(8), nullable=True)
    execution_compute_status = Column(String(24), nullable=True)
