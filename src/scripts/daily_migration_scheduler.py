#!/usr/bin/env python
"""
Daily migration scheduler: Copy data from production to local database.

This script runs the migration from production to local database on a daily schedule.
Designed to run via Railway cron jobs or as a standalone script.

Usage:
    # Run once (for Railway cron jobs)
    RUN_ONCE=true python src/scripts/daily_migration_scheduler.py

    # Or run directly
    python src/scripts/daily_migration_scheduler.py
"""

import os
import sys
import subprocess
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Immediate startup output for Railway
print("=" * 80, flush=True)
print("[MIGRATION SCHEDULER] Daily Migration Scheduler Starting...", flush=True)
print(f"[MIGRATION SCHEDULER] Project root: {project_root}", flush=True)
print("=" * 80, flush=True)

# Load environment variables from .env.local if it exists
env_local_path = project_root / ".env.local"
if env_local_path.exists():
    load_dotenv(env_local_path, override=True)
    print(f"[MIGRATION SCHEDULER] Loaded environment from .env.local", flush=True)
else:
    # Try .env.staging as fallback
    env_staging_path = project_root / ".env.staging"
    if env_staging_path.exists():
        load_dotenv(env_staging_path, override=True)
        print(f"[MIGRATION SCHEDULER] Loaded environment from .env.staging", flush=True)
    else:
        print(
            f"[MIGRATION SCHEDULER] No .env.local or .env.staging found - using system environment",
            flush=True,
        )

# Configure logging
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run_prod_to_local_migration():
    """Run the production to local database migration."""
    import time

    start_time = time.time()

    try:
        logger.info("🔄 Starting production to local migration...")
        logger.info("   [This may take 5-15 minutes depending on data size]")

        # Check if migration is enabled
        if not os.getenv("ENABLE_PROD_TO_LOCAL_MIGRATION", "").lower() == "true":
            logger.warning(
                "⚠️  Migration disabled: ENABLE_PROD_TO_LOCAL_MIGRATION not set to 'true'"
            )
            return False, "Migration disabled via environment variable"

        # Check required environment variables
        prod_db_url = os.getenv("PROD_DATABASE_URL")
        local_db_url = os.getenv("DATABASE_URL")

        if not prod_db_url:
            logger.error("❌ PROD_DATABASE_URL not configured")
            return False, "PROD_DATABASE_URL not configured"

        if not local_db_url:
            logger.error("❌ DATABASE_URL (local) not configured")
            return False, "DATABASE_URL not configured"

        # Get athlete IDs from environment (with defaults)
        source_athlete_id = os.getenv("SOURCE_ATHLETE_ID", "347085")
        target_athlete_id = os.getenv("TARGET_ATHLETE_ID", "347085")

        logger.info(f"   Source athlete_id: {source_athlete_id}")
        logger.info(f"   Target athlete_id: {target_athlete_id}")

        # Find the migration script
        migration_script = project_root / "scripts" / "migrate_athlete_155302.py"
        if not migration_script.exists():
            logger.error(f"❌ Migration script not found: {migration_script}")
            return False, f"Migration script not found: {migration_script}"

        # Set up environment for the migration script
        env = os.environ.copy()
        env["PROD_DATABASE_URL"] = prod_db_url
        env["DATABASE_URL"] = local_db_url
        # Set UTF-8 encoding for Windows compatibility (handles emoji characters)
        env["PYTHONIOENCODING"] = "utf-8"

        # Run the migration script
        logger.info(f"   [Calling {migration_script}...]")
        result = subprocess.run(
            [sys.executable, str(migration_script)],
            env=env,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minute timeout
        )

        elapsed = time.time() - start_time
        logger.info(f"   [Migration took {elapsed:.1f} seconds]")

        if result.returncode != 0:
            logger.error("❌ Migration completed with errors")
            logger.error(f"STDOUT: {result.stdout}")
            logger.error(f"STDERR: {result.stderr}")
            return (
                False,
                f"Migration failed with exit code {result.returncode}. Check logs for details.",
            )

        # Log output
        if result.stdout:
            # Log important lines from stdout
            for line in result.stdout.split("\n"):
                if line.strip() and (
                    "✅" in line or "❌" in line or "🔄" in line or "Summary:" in line
                ):
                    logger.info(f"   {line}")

        if result.stderr:
            logger.warning(f"   Warnings: {result.stderr}")

        logger.info("✅ Migration completed successfully")
        return (
            True,
            "Production to local migration completed successfully. Local database updated with latest data.",
        )

    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        logger.error(f"❌ Migration timed out after {elapsed:.1f} seconds")
        return False, "Migration timed out after 30 minutes"

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"❌ Error running migration after {elapsed:.1f} seconds: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return False, f"Migration failed: {str(e)}"


def main():
    """Main scheduler - supports both worker mode (long-running) and cron mode (run once)."""
    # Immediate output before logging setup
    print("[MIGRATION SCHEDULER] Initializing scheduler...", flush=True)

    # Check if running in "run once" mode (for Railway cron jobs)
    run_once = os.getenv("RUN_ONCE", "false").lower() == "true"

    if run_once:
        # Cron mode: run once and exit
        print("[MIGRATION SCHEDULER] Running in cron mode (run once)...", flush=True)
        logger.info("🚀 Running daily migration (cron mode)...")

        if not os.getenv("DATABASE_URL"):
            print(
                "[MIGRATION SCHEDULER] ERROR: DATABASE_URL not configured. Exiting.",
                flush=True,
            )
            logger.error("❌ DATABASE_URL not configured. Exiting.")
            sys.exit(1)

        if not os.getenv("PROD_DATABASE_URL"):
            print(
                "[MIGRATION SCHEDULER] ERROR: PROD_DATABASE_URL not configured. Exiting.",
                flush=True,
            )
            logger.error("❌ PROD_DATABASE_URL not configured. Exiting.")
            sys.exit(1)

        success, message = run_prod_to_local_migration()
        exit_code = 0 if success else 1
        sys.exit(exit_code)

    # Worker mode: long-running loop (for local development/testing)
    print(
        "[MIGRATION SCHEDULER] Running in worker mode (not recommended for production)",
        flush=True,
    )
    logger.warning(
        "⚠️  Worker mode is not recommended. Use RUN_ONCE=true for Railway cron jobs."
    )
    logger.info("💡 Migration will run once immediately, then exit")
    logger.info("💡 For scheduled runs, use Railway cron jobs with RUN_ONCE=true")

    # Run once and exit (worker mode is not really needed for daily migration)
    success, message = run_prod_to_local_migration()
    exit_code = 0 if success else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
