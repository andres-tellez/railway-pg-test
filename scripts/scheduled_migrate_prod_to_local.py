#!/usr/bin/env python3
"""
Scheduled migration script: Copy data from production to local database.

This script is designed to run as a scheduled job (cron/Task Scheduler) to
automatically sync production data to the local development database.

Usage:
    # Run once (for cron jobs)
    RUN_ONCE=true python scripts/scheduled_migrate_prod_to_local.py

    # Or run directly
    python scripts/scheduled_migrate_prod_to_local.py
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import traceback

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Load environment
env_local = Path(".env.local")
if env_local.exists():
    load_dotenv(env_local, override=False)

# Load production database URL
prod_db_url = os.getenv("PROD_DATABASE_URL")
local_db_url = os.getenv("DATABASE_URL")

if not prod_db_url:
    print("❌ PROD_DATABASE_URL not set")
    sys.exit(1)

if not local_db_url:
    print("❌ DATABASE_URL (local) not set")
    sys.exit(1)

# Athlete IDs - MUST be provided via environment to prevent copying others
if not os.getenv("SOURCE_ATHLETE_ID") or not os.getenv("TARGET_ATHLETE_ID"):
    print(
        "❌ SOURCE_ATHLETE_ID and TARGET_ATHLETE_ID are required environment variables"
    )
    sys.exit(1)
try:
    source_athlete_id = int(os.getenv("SOURCE_ATHLETE_ID"))
    target_athlete_id = int(os.getenv("TARGET_ATHLETE_ID"))
except ValueError:
    print("❌ Invalid SOURCE_ATHLETE_ID or TARGET_ATHLETE_ID (must be integers)")
    sys.exit(1)

# Logging setup
log_file = Path("logs") / "migration.log"
log_file.parent.mkdir(exist_ok=True)


def log(message):
    """Log message to both console and file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {message}"
    print(log_message)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(log_message + "\n")


def main():
    """Main migration function."""
    log("=" * 60)
    log(f"🔄 Scheduled Migration: athlete_id {source_athlete_id} → {target_athlete_id}")
    log("=" * 60)

    try:
        prod_engine = create_engine(prod_db_url, echo=False)
        local_engine = create_engine(local_db_url, echo=False)
        prod_session = sessionmaker(bind=prod_engine)()
        local_session = sessionmaker(bind=local_engine)()

        # Get source user_id
        log("\n1. Finding source user_id...")
        result = prod_session.execute(
            text("SELECT user_id FROM user_athletes WHERE athlete_id = :athlete_id"),
            {"athlete_id": source_athlete_id},
        )
        source_user_row = result.fetchone()
        if not source_user_row:
            log(f"❌ No user_athletes record found for athlete_id {source_athlete_id}")
            sys.exit(1)
        source_user_id = str(source_user_row[0])
        log(f"   ✅ Found user_id: {source_user_id}")

        # Get target user_id
        log("\n2. Finding target user_id...")
        result = local_session.execute(
            text("SELECT user_id FROM user_athletes WHERE athlete_id = :athlete_id"),
            {"athlete_id": target_athlete_id},
        )
        target_user_row = result.fetchone()
        if not target_user_row:
            log(f"❌ No user_athletes record found for athlete_id {target_athlete_id}")
            log("   Make sure your test account is connected in local database")
            sys.exit(1)
        target_user_id = str(target_user_row[0])
        log(f"   ✅ Found user_id: {target_user_id}")

        # Import and run the migration
        log("\n3. Running migration...")
        # Import the migration function from the existing script
        # We'll call the migrate_athlete_155302.py script as a subprocess
        # or refactor it to be importable
        import subprocess

        migration_script = project_root / "scripts" / "migrate_athlete_155302.py"
        if not migration_script.exists():
            log(f"❌ Migration script not found: {migration_script}")
            sys.exit(1)

        # Set environment variables for the migration script
        env = os.environ.copy()
        env["PROD_DATABASE_URL"] = prod_db_url
        env["DATABASE_URL"] = local_db_url
        env["SOURCE_ATHLETE_ID"] = str(source_athlete_id)
        env["TARGET_ATHLETE_ID"] = str(target_athlete_id)

        # Extra safety: log current env used
        log(
            f"   Using SOURCE_ATHLETE_ID={env['SOURCE_ATHLETE_ID']} TARGET_ATHLETE_ID={env['TARGET_ATHLETE_ID']}"
        )

        # Run the migration script
        result = subprocess.run(
            [sys.executable, str(migration_script)],
            env=env,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            log(f"❌ Migration failed with exit code {result.returncode}")
            log(f"STDOUT: {result.stdout}")
            log(f"STDERR: {result.stderr}")
            sys.exit(result.returncode)

        log(result.stdout)
        if result.stderr:
            log(f"Warnings: {result.stderr}")

        log("\n" + "=" * 60)
        log("✅ Scheduled migration complete!")
        log("=" * 60)

        prod_session.close()
        local_session.close()
        prod_engine.dispose()
        local_engine.dispose()

    except Exception as e:
        log(f"\n❌ Error: {e}")
        log(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
