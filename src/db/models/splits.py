from sqlalchemy import (
    Column,
    Integer,
    Float,
    ForeignKey,
    TIMESTAMP,
    BigInteger,
    String,
    UniqueConstraint,
    Boolean,  # ✅ Added Boolean
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import insert
from src.db.db_session import Base, get_session


class Split(Base):
    __tablename__ = "splits"

    id = Column(Integer, primary_key=True)
    activity_id = Column(BigInteger, ForeignKey("activities.activity_id", ondelete="CASCADE"), nullable=False)
    lap_index = Column(Integer, nullable=False)
    distance = Column(Float)
    elapsed_time = Column(Integer)
    moving_time = Column(Integer)
    average_speed = Column(Float)
    max_speed = Column(Float)
    start_index = Column(Integer)
    end_index = Column(Integer)
    split = Column(Integer, nullable=True)
    average_heartrate = Column(Float)
    pace_zone = Column(Integer)
    created_at = Column(TIMESTAMP, server_default=func.now())
    conv_distance = Column(Float)
    conv_avg_speed = Column(Float)
    conv_moving_time = Column(String)
    conv_elapsed_time = Column(String)

    __table_args__ = (
        UniqueConstraint("activity_id", "lap_index", name="uq_activity_lap"),
    )


def upsert_splits(session, splits_data: list[dict]):
    if not splits_data:
        return

    stmt = insert(Split).values(splits_data)
    update_cols = {
        c.name: getattr(stmt.excluded, c.name)
        for c in Split.__table__.columns
        if c.name not in {"id", "created_at"}
    }

    stmt = stmt.on_conflict_do_update(
        constraint="uq_activity_lap",
        set_=update_cols
    )

    session.execute(stmt)
    session.commit()
