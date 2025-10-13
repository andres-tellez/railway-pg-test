"""
Materialized View Refresh Utility
================================

This module provides utilities to refresh materialized views after data changes.
Used to ensure metrics dashboards show fresh data immediately after activity sync.

Author: SmartCoach Development Team
Last Updated: October 13, 2025
"""

from sqlalchemy import text
from src.utils.logger import get_logger

logger = get_logger(__name__)


def refresh_materialized_views(session, athlete_id=None):
    """
    Refresh materialized views to ensure fresh metrics data.

    This function refreshes the materialized views that power the metrics dashboard
    to ensure users see their latest activity data immediately.

    Args:
        session: SQLAlchemy database session
        athlete_id: Optional athlete_id to log for debugging (not used in refresh)

    Returns:
        dict: Results of the refresh operations
    """
    logger.info("🔄 Starting materialized view refresh...")

    results = {
        "mv_athlete_metrics": {"status": "pending", "error": None},
        "mv_longest_runs": {"status": "pending", "error": None},
    }

    try:
        # Refresh mv_athlete_metrics (powers main dashboard metrics)
        logger.info("📊 Refreshing mv_athlete_metrics...")
        session.execute(
            text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_athlete_metrics")
        )
        results["mv_athlete_metrics"]["status"] = "success"
        logger.info("✅ mv_athlete_metrics refreshed successfully")

    except Exception as e:
        logger.error(f"❌ Failed to refresh mv_athlete_metrics: {e}")
        results["mv_athlete_metrics"]["status"] = "error"
        results["mv_athlete_metrics"]["error"] = str(e)

    try:
        # Refresh mv_longest_runs (powers longest runs chart)
        logger.info("🏃 Refreshing mv_longest_runs...")
        session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_longest_runs"))
        results["mv_longest_runs"]["status"] = "success"
        logger.info("✅ mv_longest_runs refreshed successfully")

    except Exception as e:
        logger.error(f"❌ Failed to refresh mv_longest_runs: {e}")
        results["mv_longest_runs"]["status"] = "error"
        results["mv_longest_runs"]["error"] = str(e)

    # Commit the session to ensure changes are persisted
    session.commit()

    # Log summary
    success_count = sum(
        1 for result in results.values() if result["status"] == "success"
    )
    total_count = len(results)

    if success_count == total_count:
        logger.info(
            f"🎉 All materialized views refreshed successfully ({success_count}/{total_count})"
        )
    else:
        logger.warning(f"⚠️ Partial refresh success ({success_count}/{total_count})")
        for view_name, result in results.items():
            if result["status"] == "error":
                logger.error(f"   - {view_name}: {result['error']}")

    return results


def refresh_views_after_activity_sync(session, athlete_id, activities_synced=0):
    """
    Convenience function to refresh views after activity sync.

    Args:
        session: SQLAlchemy database session
        athlete_id: Athlete ID for logging purposes
        activities_synced: Number of activities that were synced

    Returns:
        dict: Results of the refresh operations
    """
    if activities_synced > 0:
        logger.info(
            f"🔄 Refreshing materialized views after syncing {activities_synced} activities for athlete {athlete_id}"
        )
        return refresh_materialized_views(session, athlete_id)
    else:
        logger.info(
            f"⏭️ Skipping materialized view refresh - no new activities synced for athlete {athlete_id}"
        )
        return {"skipped": True, "reason": "no_new_activities"}
