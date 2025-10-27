#!/usr/bin/env python
"""
Scheduled metrics refresh script for Railway cron jobs.

This script runs every Monday at 4AM to refresh all metrics data:
- Refreshes materialized views
- Invalidates caches
- Recalculates weekly metrics

Usage:
    python src/scripts/refresh_metrics_cron.py
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Add project root to path so we can import our modules
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def refresh_materialized_views():
    """Refresh all materialized views."""
    try:
        from src.db.db_session import get_session
        from sqlalchemy import text

        session = get_session()
        logger.info("🔄 Refreshing materialized views...")

        # Check what data exists BEFORE refresh
        logger.info("📊 Checking data before refresh...")
        before_data = session.execute(
            text(
                """
                SELECT athlete_id, week_commencing, total_miles, longest_run
                FROM mv_athlete_metrics
                ORDER BY week_commencing DESC
                LIMIT 5
            """
            )
        ).fetchall()
        logger.info(f"📊 Latest 5 weeks BEFORE refresh: {before_data}")

        # Refresh the main metrics view (non-concurrent to avoid index requirement)
        logger.info("🔄 Executing REFRESH...")
        session.execute(text("REFRESH MATERIALIZED VIEW mv_athlete_metrics;"))
        session.commit()

        # Check what data exists AFTER refresh
        logger.info("📊 Checking data after refresh...")
        after_data = session.execute(
            text(
                """
                SELECT athlete_id, week_commencing, total_miles, longest_run
                FROM mv_athlete_metrics
                ORDER BY week_commencing DESC
                LIMIT 5
            """
            )
        ).fetchall()
        logger.info(f"📊 Latest 5 weeks AFTER refresh: {after_data}")

        logger.info("✅ Materialized views refreshed successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to refresh materialized views: {e}")
        import traceback

        logger.error(traceback.format_exc())
        if "session" in locals():
            session.rollback()
            session.close()
        return False


def invalidate_all_caches():
    """Invalidate metrics caches for all athletes."""
    try:
        logger.info("🗑️ Invalidating metrics caches...")

        # Import cache service
        from src.services.metrics_cache_service import invalidate_all_caches

        # Check cache state before invalidation
        logger.info("📊 Checking cache state before invalidation...")

        # Invalidate all caches
        invalidate_all_caches()

        logger.info("✅ All caches invalidated successfully")
        logger.info(
            "📊 Cache cleared - next request will fetch fresh data from database"
        )
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
