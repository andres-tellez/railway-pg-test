"""
sync_queue_service.py

Sync Queue Service for Serialized Per-Athlete Syncing
=======================================================

This service ensures that when multiple athletes need to sync, we:
1. Queue them up (one at a time)
2. Respect rate limits (100/15m, 1000/day)
3. Process sequentially to avoid overwhelming Strava API

Usage:
    # Queue a sync for an athlete
    queue_athlete_sync(athlete_id, user_id)

    # Process all queued syncs (respecting rate limits)
    process_sync_queue()
"""

import logging
import time
from typing import List, Dict, Optional
from datetime import datetime

from src.db.db_session import get_session
from src.services.ingestion_orchestrator_service import (
    run_full_ingestion_and_enrichment,
)
from src.utils.rate_limiter import get_rate_limiter
from src.db.models.user_athletes import UserAthleteLink
from src.db.dao import user_athletes_dao

logger = logging.getLogger(__name__)


class SyncQueue:
    """
    In-memory queue for athlete syncs.

    In production, you might want to use Redis or a database-backed queue.
    For now, this is a simple in-memory queue that processes sequentially.
    """

    def __init__(self):
        self._queue: List[Dict] = []  # List of {athlete_id, user_id, queued_at}

    def add(self, athlete_id: int, user_id: Optional[str] = None):
        """
        Add an athlete to the sync queue.

        Args:
            athlete_id: Strava athlete ID
            user_id: Internal user ID (optional)
        """
        self._queue.append(
            {
                "athlete_id": athlete_id,
                "user_id": user_id,
                "queued_at": datetime.utcnow(),
            }
        )
        logger.info(f"📋 Queued sync for athlete_id={athlete_id}, user_id={user_id}")

    def pop(self) -> Optional[Dict]:
        """
        Get next athlete from queue.

        Returns:
            Dict with athlete_id and user_id, or None if queue is empty
        """
        if self._queue:
            return self._queue.pop(0)
        return None

    def size(self) -> int:
        """Get current queue size."""
        return len(self._queue)

    def clear(self):
        """Clear the queue (useful for testing)."""
        self._queue.clear()


# Global sync queue instance
_global_sync_queue: Optional[SyncQueue] = None


def get_sync_queue() -> SyncQueue:
    """
    Get the global sync queue instance.

    Returns:
        SyncQueue instance (singleton)
    """
    global _global_sync_queue
    if _global_sync_queue is None:
        _global_sync_queue = SyncQueue()
    return _global_sync_queue


def queue_athlete_sync(athlete_id: int, user_id: Optional[str] = None):
    """
    Queue an athlete for syncing.

    This adds the athlete to the queue but doesn't process immediately.
    Call process_sync_queue() to process all queued syncs.

    Args:
        athlete_id: Strava athlete ID
        user_id: Internal user ID (optional, will be looked up if not provided)
    """
    queue = get_sync_queue()

    # Look up user_id if not provided
    if not user_id:
        session = get_session()
        try:
            link = user_athletes_dao.get_by_athlete_id(session, athlete_id)
            if link:
                user_id = link.user_id
            else:
                logger.warning(
                    f"⚠️ No user found for athlete_id={athlete_id}, queuing without user_id"
                )
        finally:
            session.close()

    queue.add(athlete_id, user_id)


def process_sync_queue(max_syncs: Optional[int] = None) -> Dict[str, int]:
    """
    Process all queued athlete syncs, respecting rate limits.

    This function:
    1. Takes syncs from queue one at a time
    2. Checks rate limits before each sync
    3. Waits if necessary to respect limits
    4. Processes the sync
    5. Records API usage

    Args:
        max_syncs: Maximum number of syncs to process (None = process all)

    Returns:
        Dict with statistics: {processed, skipped, failed}
    """
    queue = get_sync_queue()
    rate_limiter = get_rate_limiter()

    stats = {"processed": 0, "skipped": 0, "failed": 0}

    logger.info(f"🚀 Processing sync queue (size={queue.size()})")

    while queue.size() > 0:
        # Check if we've hit max_syncs limit
        if max_syncs is not None and stats["processed"] >= max_syncs:
            logger.info(f"⏸️ Reached max_syncs limit ({max_syncs}), stopping")
            break

        # Check rate limits and wait if needed
        rate_limiter.wait_if_needed()

        if not rate_limiter.can_make_request():
            logger.warning(
                "⚠️ Rate limit reached, stopping queue processing. "
                "Will resume when limits reset."
            )
            break

        # Get next athlete from queue
        sync_item = queue.pop()
        if not sync_item:
            break

        athlete_id = sync_item["athlete_id"]
        user_id = sync_item["user_id"]

        logger.info(
            f"🔄 Processing sync for athlete_id={athlete_id}, "
            f"user_id={user_id} (queue remaining: {queue.size()})"
        )

        # Get rate limit stats before sync
        stats_before = rate_limiter.get_stats()

        try:
            # Run the sync (this will make API calls)
            # Note: We rely on the ingestion service to call rate_limiter.record_request()
            # after each API call. For now, we'll estimate requests.
            session = get_session()
            try:
                result = run_full_ingestion_and_enrichment(
                    session,
                    athlete_id,
                    user_id=user_id,
                    max_activities=50,  # Limit initial sync to avoid too many requests
                )

                # Estimate API calls made (roughly: 1 per activity page + enrichment calls)
                # This is approximate - ideally we'd track this in the ingestion service
                estimated_calls = 2 + (
                    result.get("synced", 0) // 50
                )  # 2 base + ~1 per 50 activities

                # Record estimated requests
                for _ in range(min(estimated_calls, 10)):  # Cap at 10 to be safe
                    rate_limiter.record_request()

                stats["processed"] += 1
                logger.info(
                    f"✅ Sync completed for athlete_id={athlete_id}: "
                    f"synced={result.get('synced', 0)}, enriched={result.get('enriched', 0)}"
                )

            except Exception as e:
                logger.error(
                    f"❌ Sync failed for athlete_id={athlete_id}: {e}",
                    exc_info=True,
                )
                stats["failed"] += 1
            finally:
                session.close()

        except Exception as e:
            logger.error(
                f"❌ Unexpected error processing sync for athlete_id={athlete_id}: {e}",
                exc_info=True,
            )
            stats["failed"] += 1

        # Log rate limit status after sync
        stats_after = rate_limiter.get_stats()
        logger.info(
            f"📊 Rate limit status: 15min={stats_after['requests_15min']}/{stats_after['limit_15min']}, "
            f"24h={stats_after['requests_24h']}/{stats_after['limit_24h']}"
        )

        # Small delay between syncs to avoid hammering
        time.sleep(1)

    logger.info(
        f"✅ Queue processing complete: processed={stats['processed']}, "
        f"failed={stats['failed']}, remaining={queue.size()}"
    )

    return stats


def queue_all_athletes():
    """
    Queue syncs for all athletes in the system.

    Useful for batch processing or initial setup.
    """
    session = get_session()
    try:
        links = session.query(UserAthleteLink).all()
        logger.info(f"📋 Queuing syncs for {len(links)} athletes")

        for link in links:
            queue_athlete_sync(link.athlete_id, link.user_id)

        logger.info(f"✅ Queued {len(links)} athlete syncs")
    finally:
        session.close()
