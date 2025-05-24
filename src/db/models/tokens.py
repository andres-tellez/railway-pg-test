# src/models/tokens.py

from sqlalchemy import Column, BigInteger, Text
from src.db_core import Base

class Token(Base):
    __tablename__ = "tokens"

    athlete_id = Column(BigInteger, primary_key=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    expires_at = Column(BigInteger, nullable=False)
