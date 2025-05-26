# src/db/core.py

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from flask import current_app, has_app_context

Base = declarative_base()

_engine = None
_SessionLocal = None


def resolve_db_url():
    if has_app_context():
        return current_app.config.get("DATABASE_URL") or os.getenv("DATABASE_URL")
    return os.getenv("DATABASE_URL")


def get_engine():
    global _engine
    if _engine is None:
        db_url = resolve_db_url()
        if not db_url:
            raise RuntimeError("DATABASE_URL not set.")
        _engine = create_engine(db_url, echo=False, future=True)
    return _engine


def get_session():
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return _SessionLocal()
