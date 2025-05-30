# src/db/db_session.py

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from flask import current_app, has_app_context

# Global declarative base — shared across models
Base = declarative_base()

def resolve_db_url():
    """
    Resolve DATABASE_URL from Flask config or environment variables.
    """
    if has_app_context():
        # Use Flask app config if inside app context
        return current_app.config.get("DATABASE_URL") or os.getenv("DATABASE_URL")
    return os.getenv("DATABASE_URL")

def get_engine():
    """
    Create a SQLAlchemy engine. Should be called once per process.
    """
    db_url = resolve_db_url()
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set in environment or app config.")
    return create_engine(db_url, echo=False, future=True)

def get_session():
    """
    Create a new SQLAlchemy sessionmaker (not a global session).
    """
    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return SessionLocal()
