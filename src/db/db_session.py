# src/db/db_session.py

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.utils.config import config


# ✅ SQLAlchemy instance for Flask use
db = SQLAlchemy()

# ✅ Declarative base for non-Flask models
Base = declarative_base()


# ✅ Engine creation with pool_pre_ping and sslmode
def get_engine(db_url=None):
    """
    Create a SQLAlchemy engine.
    Allows optional db_url override for tests or special cases.
    """
    db_url = db_url or config.DATABASE_URL
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set in configuration.")

    return create_engine(
        db_url,
        echo=False,
        future=True,
        pool_pre_ping=True,  # ✅ ensures dead connections are recycled
        connect_args={"sslmode": "require"},  # ✅ especially for Railway
    )


# ✅ Session factory
def get_session(engine=None):
    """
    Create a new SQLAlchemy sessionmaker (not a global session).
    Allows optional engine injection for test harnesses.
    """
    engine = engine or get_engine()
    SessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, future=True
    )
    return SessionLocal()


# ✅ Dependency-style session generator (used in routes)
def get_db():
    """
    Generator that yields a database session and ensures closure.
    Use in routes: `db = next(get_db())` or in context managers.
    """
    SessionLocal = get_session()
    db_session = SessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()


# ✅ Eagerly initialize engine (optional if you use it directly)
engine = get_engine()
