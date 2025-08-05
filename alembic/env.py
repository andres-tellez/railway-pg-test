import sys
import os

from dotenv import load_dotenv

# --- Add project root to sys.path ---
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# --- Add 'src' folder to sys.path ---
sys.path.insert(0, os.path.join(project_root, "src"))

# ✅ Load environment variables from explicit .env path with override
# ✅ Load the appropriate .env file based on FLASK_ENV
# Use FLASK_ENV or fallback to RAILWAY_ENVIRONMENT or default to "development"
env_mode = os.getenv("FLASK_ENV") or os.getenv("RAILWAY_ENVIRONMENT") or "development"

if env_mode == "testing":
    env_file = ".env.test"
elif env_mode == "production":
    env_file = ".env.prod"
else:
    env_file = ".env.local"

dotenv_path = os.path.join(project_root, env_file)
load_dotenv(dotenv_path, override=True)

print(f"✅ [Alembic] Loaded environment: {env_file}")

print("🚨 DATABASE_URL =", os.getenv("DATABASE_URL"))

from logging.config import fileConfig
from sqlalchemy import engine_from_config, create_engine, pool, MetaData
from alembic import context

# DATABASE_URL after .env is loaded
DATABASE_URL = os.getenv("DATABASE_URL")
print(f"DEBUG: Using DATABASE_URL = {DATABASE_URL}")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set. Alembic cannot continue."
    )

# Import SQLAlchemy Base AFTER sys.path is fully patched
from src.db.db_session import Base

# ✅ Import all models so Alembic can detect schema
import src.db.models.activities
import src.db.models.tokens
import src.db.models.splits
import src.db.models.athletes
import src.db.models.user_profile  # Core table import
from src.db.models.user_profile import metadata as user_profile_metadata  # ✅

# ✅ Merge ORM and Core metadata
target_metadata = MetaData()
for m in [Base.metadata, user_profile_metadata]:
    for table in m.tables.values():
        target_metadata._add_table(table.name, table.schema, table)

# Alembic Config object
config = context.config

# Configure logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

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
    # ✅ Replace with explicit engine creation and echo enabled
    connectable = create_engine(
        DATABASE_URL,
        echo=True,  # 🔍 Enable SQL echoing
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
