from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
)
from src.db.db_session import Base


class UserAthlete(Base):
    __tablename__ = "user_athletes"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False, unique=True)
    athlete_id = Column(
        Integer,
        ForeignKey("athletes.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),  # pylint: disable=not-callable
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_athletes_user_id"),
        UniqueConstraint("athlete_id", name="uq_user_athletes_athlete_id"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "athlete_id": self.athlete_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
