import sys
import os

# --- Add project root to sys.path ---
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# --- Add 'src' folder to sys.path so Alembic can find env_loader ---
sys.path.insert(0, os.path.join(project_root, "src"))

# --- Now safe to import env_loader ---
import env_loader  # <-- This will correctly apply DATABASE_URL patches

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# DATABASE_URL after env_loader patched it
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set. Alembic cannot continue.")

# Import SQLAlchemy Base AFTER sys.path is fully patched
from src.db.models.base import Base

# ✅ Import all models so that Alembic can detect them
import src.db.models.activities
import src.db.models.tokens
import src.db.models.splits

# Alembic Config object
config = context.config

# Configure logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for autogenerate
target_metadata = Base.metadata

# Inject DATABASE_URL dynamically for Alembic migrations
config.set_main_option("sqlalchemy.url", DATABASE_URL)


def run_migrations_offline():
    """Run migrations in 'offline' mode (no DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode (DB connection active)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
