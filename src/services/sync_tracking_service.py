"""
sync_tracking_service.py

Sync Tracking Service - Webhooks-First Strategy
================================================

Tracks when athletes were last synced and minimizes polling by:
1. Using webhooks for real-time sync (primary method)
2. Only polling for activities after last_sync_at when needed
3. Tracking webhook subscription status

Strategy:
- Webhooks-first: If webhooks are active, rely on them for new activities
- Incremental polling: Only fetch activities after last_sync_at
- Full polling: Only on initial sync or when webhooks are inactive
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.db.models.user_athletes import UserAthleteLink
from src.db.models.activities import Activity
from src.db.models.webhook_events import WebhookEvent, WebhookEventStatus

logger = logging.getLogger(__name__)


def get_last_sync_timestamp(session: Session, athlete_id: int) -> Optional[datetime]:
    """
    Get the timestamp of the most recent activity for an athlete.

    This represents when we last had data synced (either via webhook or polling).

    Args:
        session: Database session
        athlete_id: Strava athlete ID

    Returns:
        datetime of most recent activity, or None if no activities
    """
    try:
        latest = (
            session.query(Activity.start_date)
            .filter_by(athlete_id=athlete_id)
            .order_by(Activity.start_date.desc())
            .first()
        )

        if latest:
            return latest[0]
        return None
    except Exception as e:
        logger.error(f"Error getting last sync timestamp for athlete {athlete_id}: {e}")
        return None


def has_recent_webhook_activity(
    session: Session, athlete_id: int, hours: int = 24
) -> bool:
    """
    Check if athlete has received webhook events recently.

    This indicates webhooks are active and working for this athlete.

    Args:
        session: Database session
        athlete_id: Strava athlete ID
        hours: Time window to check (default: 24 hours)

    Returns:
        True if webhook events exist in the time window
    """
    try:
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        count = (
            session.query(WebhookEvent)
            .filter(
                WebhookEvent.owner_id == athlete_id,
                WebhookEvent.object_type == "activity",
                WebhookEvent.aspect_type == "create",
                WebhookEvent.received_at >= cutoff,
            )
            .count()
        )

        return count > 0
    except Exception as e:
        logger.error(f"Error checking webhook activity for athlete {athlete_id}: {e}")
        return False


def is_webhook_active(session: Session) -> bool:
    """
    Check if webhook subscription is active globally.

    Looks for any recent webhook events (any athlete) to indicate
    the subscription is working.

    Args:
        session: Database session

    Returns:
        True if webhooks are active (recent events exist)
    """
    try:
        # Check if any webhook events exist in last 7 days
        cutoff = datetime.utcnow() - timedelta(days=7)

        count = (
            session.query(WebhookEvent)
            .filter(WebhookEvent.received_at >= cutoff)
            .count()
        )

        return count > 0
    except Exception as e:
        logger.error(f"Error checking webhook subscription status: {e}")
        return False


def should_use_incremental_sync(
    session: Session, athlete_id: int, force_full: bool = False
) -> tuple[bool, Optional[datetime]]:
    """
    Determine if we should use incremental sync (only fetch after last_sync_at).

    Strategy:
    - Use incremental if: webhooks are active AND athlete has recent webhook activity
    - Use full sync if: initial sync, webhooks inactive, or force_full=True

    Args:
        session: Database session
        athlete_id: Strava athlete ID
        force_full: Force full sync regardless of webhook status

    Returns:
        Tuple of (use_incremental, last_sync_at)
        - use_incremental: True to only fetch after last_sync_at
        - last_sync_at: Timestamp to use for incremental sync, or None
    """
    if force_full:
        logger.info(f"🔄 Force full sync requested for athlete {athlete_id}")
        return False, None

    # Check if webhooks are active globally
    webhooks_active = is_webhook_active(session)

    if not webhooks_active:
        logger.info(f"🔄 Webhooks not active, using full sync for athlete {athlete_id}")
        return False, None

    # Check if this athlete has recent webhook activity
    has_webhooks = has_recent_webhook_activity(session, athlete_id, hours=24)

    if not has_webhooks:
        logger.info(
            f"🔄 No recent webhook activity for athlete {athlete_id}, "
            f"using full sync (may be new user)"
        )
        return False, None

    # Get last sync timestamp
    last_sync_at = get_last_sync_timestamp(session, athlete_id)

    if not last_sync_at:
        logger.info(
            f"🔄 No previous sync found for athlete {athlete_id}, using full sync"
        )
        return False, None

    # Use incremental sync (only fetch after last_sync_at)
    logger.info(
        f"✅ Using incremental sync for athlete {athlete_id} "
        f"(last sync: {last_sync_at.isoformat()})"
    )
    return True, last_sync_at


def update_last_sync_timestamp(session: Session, athlete_id: int):
    """
    Update last sync timestamp after successful sync.

    This is automatically done by using get_last_sync_timestamp() which
    queries the most recent activity, so we don't need a separate column.

    However, we can log the sync for tracking purposes.

    Args:
        session: Database session
        athlete_id: Strava athlete ID
    """
    last_sync = get_last_sync_timestamp(session, athlete_id)
    if last_sync:
        logger.info(
            f"📊 Last sync timestamp for athlete {athlete_id}: {last_sync.isoformat()}"
        )
