# src/db/core.py

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from flask import current_app, has_app_context

Base = declarative_base()


def resolve_db_url():
    """Resolve the database URL from Flask config or environment."""
    if has_app_context():
        return current_app.config.get("DATABASE_URL") or os.getenv("DATABASE_URL")
    return os.getenv("DATABASE_URL")


def get_engine():
    """Create a new SQLAlchemy engine per process (lazy singleton)."""
    db_url = resolve_db_url()
    if not db_url:
        raise RuntimeError("DATABASE_URL not set in environment or app config.")
    return create_engine(db_url, echo=False, future=True)


def get_session():
    """Create a new sessionmaker on each call (no global shared session)."""
    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return SessionLocal()
