#models/tokens.py

from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, BigInteger, String

Base = declarative_base()

class Token(Base):
    __tablename__ = "tokens"

    athlete_id = Column(BigInteger, primary_key=True)
    access_token = Column(String)
    refresh_token = Column(String)
    expires_at = Column(BigInteger)
