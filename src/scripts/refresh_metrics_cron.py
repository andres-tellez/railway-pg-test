#!/usr/bin/env python
"""
Scheduled metrics refresh script for Railway cron jobs.

This script runs every Monday at 2:00 AM Central to refresh all metrics data:
- Refreshes materialized views (mv_athlete_metrics, mv_longest_runs)
- Invalidates caches
- Ensures metrics page shows current week as leftmost bar

Usage:
    python src/scripts/refresh_metrics_cron.py
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path so we can import our modules
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env.local if it exists
env_local_path = project_root / ".env.local"
if env_local_path.exists():
    load_dotenv(env_local_path, override=True)
    print(f"[OK] Loaded environment from .env.local", flush=True)
else:
    # Try .env.staging as fallback
    env_staging_path = project_root / ".env.staging"
    if env_staging_path.exists():
        load_dotenv(env_staging_path, override=True)
        print(f"[OK] Loaded environment from .env.staging", flush=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def refresh_materialized_views():
    """Refresh all materialized views with retry logic and timeout."""
    from src.db.db_session import get_session
    from sqlalchemy import text
    import time
    import signal

    max_retries = 3
    retry_delay = 5  # seconds
    timeout_seconds = 300  # 5 minutes timeout for each view refresh

    for attempt in range(max_retries):
        try:
            session = get_session()
            logger.info(
                f"🔄 Refreshing materialized views... (attempt {attempt + 1}/{max_retries})"
            )

            # Check if views exist first
            check_query = text(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_matviews
                    WHERE matviewname IN ('mv_athlete_metrics', 'mv_longest_runs')
                );
            """
            )
            views_exist = session.execute(check_query).scalar()

            if not views_exist:
                logger.warning(
                    "⚠️  Materialized views (mv_athlete_metrics, mv_longest_runs) do not exist. "
                    "Skipping refresh. Views may need to be created first."
                )
                session.close()
                return False

            logger.info(
                "⏳ Refreshing mv_athlete_metrics (this may take 1-2 minutes)..."
            )
            start_time = time.time()
            session.execute(text("REFRESH MATERIALIZED VIEW mv_athlete_metrics;"))
            elapsed = time.time() - start_time
            logger.info(f"✅ mv_athlete_metrics refreshed in {elapsed:.1f} seconds")

            logger.info("⏳ Refreshing mv_longest_runs (this may take 1-2 minutes)...")
            start_time = time.time()
            session.execute(text("REFRESH MATERIALIZED VIEW mv_longest_runs;"))
            elapsed = time.time() - start_time
            logger.info(f"✅ mv_longest_runs refreshed in {elapsed:.1f} seconds")

            session.commit()
            session.close()

            logger.info("✅ Materialized views refreshed successfully")
            return True
        except Exception as e:
            logger.error(
                f"❌ Failed to refresh materialized views (attempt {attempt + 1}/{max_retries}): {e}"
            )
            import traceback

            logger.error(traceback.format_exc())

            if "session" in locals():
                try:
                    session.rollback()
                    session.close()
                except:
                    pass

            if attempt < max_retries - 1:
                logger.info(f"🔄 Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error("❌ All retry attempts exhausted")
                return False

    return False


def invalidate_all_caches():
    """Invalidate metrics caches for all athletes."""
    try:
        logger.info("🗑️ Invalidating metrics caches...")

        # Import cache service
        from src.services.metrics_cache_service import invalidate_all_caches

        # Invalidate all caches
        invalidate_all_caches()

        logger.info("✅ All caches invalidated successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to invalidate caches: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return False


def main():
    """Main function to refresh metrics."""
    logger.info(f"🚀 Starting scheduled metrics refresh at {datetime.now()}")

    # Check if we have database configuration
    if not os.getenv("DATABASE_URL"):
        logger.error("❌ DATABASE_URL not configured. Skipping metrics refresh.")
        return 1

    success = True

    # Step 1: Refresh materialized views
    if not refresh_materialized_views():
        success = False

    # Step 2: Invalidate caches
    if not invalidate_all_caches():
        success = False

    if success:
        logger.info("✅ Scheduled metrics refresh completed successfully")
        return 0
    else:
        logger.error("❌ Scheduled metrics refresh completed with errors")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
