from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

import src.utils.config as config

# Global declarative base — shared across models
Base = declarative_base()

def get_engine(db_url=None):
    """
    Create a SQLAlchemy engine.
    Allows optional db_url override for tests or special cases.
    """
    db_url = db_url or config.DATABASE_URL
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set in configuration.")
    return create_engine(db_url, echo=False, future=True)

def get_session(engine=None):
    """
    Create a new SQLAlchemy sessionmaker (not a global session).
    Allows optional engine injection for test harnesses.
    """
    engine = engine or get_engine()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return SessionLocal()
