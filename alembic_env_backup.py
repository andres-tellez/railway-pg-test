# pylint: skip-file
"""Alembic environment configuration."""

import sys
import os
from dotenv import load_dotenv
from logging.config import fileConfig
from sqlalchemy import create_engine, pool, MetaData
from alembic import context  # type: ignore[import]

# --- Add project root & src folder to sys.path ---
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "src"))

# --- Load the appropriate .env file based on environment ---
env_mode = os.getenv("FLASK_ENV") or os.getenv("RAILWAY_ENVIRONMENT") or "development"

if env_mode == "testing":
    env_file = ".env.test"
elif env_mode == "production":
    env_file = ".env.prod"
elif env_mode == "staging":
    env_file = ".env.staging"
else:
    env_file = ".env.local"

dotenv_path = os.path.join(project_root, env_file)
load_dotenv(dotenv_path, override=True)

print(f"✅ [Alembic] Loaded environment: {env_file}")
print("🚨 DATABASE_URL =", os.getenv("DATABASE_URL"))

# --- Database URL ---
DATABASE_URL = os.getenv("DATABASE_URL")
print(f"DEBUG: Using DATABASE_URL = {DATABASE_URL}")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set. Alembic cannot continue."
    )

# --- Import SQLAlchemy Base AFTER sys.path patching ---
from src.db.db_session import Base

# --- Import all models so Alembic can detect them ---
import src.db.models.activities
import src.db.models.tokens
import src.db.models.splits
import src.db.models.athletes
import src.db.models.user_profile
from src.db.models.user_profile import metadata as user_profile_metadata
import src.db.models.user_identity

# --- Merge ORM and Core metadata ---
TARGET_METADATA = MetaData()
for m in [Base.metadata, user_profile_metadata]:
    for table in m.tables.values():
        TARGET_METADATA._add_table(table.name, table.schema, table)

# --- Alembic Config ---
config = context.config  # type: ignore[attr-defined]
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", DATABASE_URL)  # type: ignore[attr-defined]


def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")  # type: ignore[attr-defined]
    context.configure(  # type: ignore[attr-defined]
        url=url,
        target_metadata=TARGET_METADATA,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():  # type: ignore[attr-defined]
        context.run_migrations()  # type: ignore[attr-defined]


def run_migrations_online():
    """Run migrations in 'online' mode."""
    connectable = create_engine(
        DATABASE_URL,
        echo=True,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(  # type: ignore[attr-defined]
            connection=connection,
            target_metadata=TARGET_METADATA,
            compare_type=True,
        )

        with context.begin_transaction():  # type: ignore[attr-defined]
            context.run_migrations()  # type: ignore[attr-defined]


if context.is_offline_mode():  # type: ignore[attr-defined]
    run_migrations_offline()
else:
    run_migrations_online()
