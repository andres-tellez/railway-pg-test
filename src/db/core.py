# src/db/core.py

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Load from environment or .env
DATABASE_URL = os.getenv("DATABASE_URL")

# SQLAlchemy base model
Base = declarative_base()

# Engine and session factory
engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_engine():
    """Returns the SQLAlchemy engine."""
    return engine

def get_session():
    """Creates a new session for DB operations."""
    return SessionLocal()
