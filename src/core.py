# src/core.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

Base = declarative_base()

_engine = None

def get_engine(db_url=None):
    global _engine
    if _engine:
        return _engine

    db_url = db_url or os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set")

    _engine = create_engine(db_url, future=True)
    return _engine

def set_engine_for_testing(engine):
    global _engine
    _engine = engine

def get_session(engine=None):
    if engine is None:
        engine = get_engine()
    return sessionmaker(bind=engine, future=True)()
