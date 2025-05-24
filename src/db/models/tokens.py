# src/models/tokens.py
from sqlalchemy import Column, Integer, String
from src.db_core import Base

class Token(Base):
    __tablename__ = "tokens"

    athlete_id = Column(Integer, primary_key=True)
    access_token = Column(String)
    refresh_token = Column(String)
