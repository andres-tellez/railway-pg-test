from sqlalchemy import Column, BigInteger, String
from src.db.db_session import Base  # ✅ use shared Base


class Token(Base):
    __tablename__ = "tokens"

    athlete_id = Column(BigInteger, primary_key=True)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)
    expires_at = Column(BigInteger, nullable=False)
