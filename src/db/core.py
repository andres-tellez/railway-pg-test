# src/db/core.py

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from flask import current_app, has_app_context

Base = declarative_base()


def resolve_db_url():
    if has_app_context():
        return current_app.config.get("DATABASE_URL") or os.getenv("DATABASE_URL")
    return os.getenv("DATABASE_URL")


def get_engine():
    db_url = resolve_db_url()
    if not db_url:
        raise RuntimeError("DATABASE_URL not set in environment or app config.")
    return create_engine(db_url, echo=False, future=True)


def get_session():
    engine = get_engine()
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
