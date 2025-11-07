# src/db/db_session.py

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from src.utils.config import config

# ✅ SQLAlchemy instance for Flask integration (if you use db.Model elsewhere)
db = SQLAlchemy()

# ✅ Declarative base for models
Base = declarative_base()

# ✅ Global engine
DATABASE_URL = config.DATABASE_URL
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set in configuration.")

engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,  # ✅ ensures dead connections are recycled
    connect_args={"sslmode": "require"},  # ✅ important for Railway
)

# ✅ Global session factory
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)

# -------------------------
# 🔧 Session helpers
# -------------------------


def get_engine():
    """Return the global engine (backward compatibility)."""
    return engine


def get_session():
    """
    Return a new SQLAlchemy session from the global SessionLocal.
    Usage:
        session = get_session()
    """
    return SessionLocal()


def get_db():
    """
    Dependency-style generator that yields a session and ensures closure.
    Useful in routes or background tasks.
    Usage:
        for db in get_db():
            ...
    """
    db_session = SessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()
