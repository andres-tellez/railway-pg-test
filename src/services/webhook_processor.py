"""
webhook_processor.py

Webhook Event Processing Service
=================================

This module processes webhook events stored in the database.
Processing happens asynchronously to keep webhook response times fast.

Processing Logic:
1. Fetch event from database
2. Determine action based on event type
3. Execute action (fetch activity, update, delete)
4. Update event status
5. Handle errors and retries

Supported Events:
- activity.create → Fetch and store new activity
- activity.update → Update existing activity (optional)
- activity.delete → Soft delete activity (optional)
- athlete.* → Log and ignore (for now)
"""

from src.db.models.webhook_events import WebhookEvent, WebhookEventStatus
from src.db.models.user_athletes import UserAthleteLink
from src.db.models.activities import Activity
from src.services.activity_service import (
    ActivityIngestionService,
    enrich_one_activity_with_refresh,
)
from src.db.dao.activity_dao import ActivityDAO
from src.services.strava_access_service import StravaClient
from src.services.token_service import get_valid_token
from sqlalchemy.orm import Session
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def process_webhook_event(session: Session, event_id: int):
    """
    Process a single webhook event.

    Args:
        session: Database session
        event_id: ID of webhook event to process

    Returns:
        bool: True if processed successfully
    """
    try:
        # Fetch event
        event = session.query(WebhookEvent).filter_by(id=event_id).first()

        if not event:
            logger.warning(f"⚠️ Event {event_id} not found")
            return False

        if event.status != WebhookEventStatus.PENDING:
            logger.info(f"ℹ️ Event {event_id} already processed (status={event.status})")
            return False

        # Mark as processing
        event.status = WebhookEventStatus.PROCESSING
        session.commit()

        logger.info(
            f"🔄 Processing event {event_id}: "
            f"{event.object_type}.{event.aspect_type} (object_id={event.object_id})"
        )

        # Route to appropriate handler
        if event.object_type == "activity":
            success = _process_activity_event(session, event)
        elif event.object_type == "athlete":
            success = _process_athlete_event(session, event)
        else:
            logger.warning(
                f"⚠️ Unknown object_type: {event.object_type}, ignoring event"
            )
            event.status = WebhookEventStatus.IGNORED
            session.commit()
            return False

        # Update event status
        if success:
            event.status = WebhookEventStatus.COMPLETED
            event.processed_at = datetime.utcnow()
            logger.info(f"✅ Event {event_id} processed successfully")
        else:
            event.status = WebhookEventStatus.FAILED
            event.retry_count += 1
            logger.error(f"❌ Event {event_id} processing failed")

        session.commit()
        return success

    except Exception as e:
        logger.error(f"❌ Exception processing event {event_id}: {e}", exc_info=True)

        # Update event with error
        try:
            event = session.query(WebhookEvent).filter_by(id=event_id).first()
            if event:
                event.status = WebhookEventStatus.FAILED
                event.error_message = str(e)
                event.retry_count += 1
                session.commit()
        except Exception as nested_error:
            logger.error(
                f"❌ Failed to update event status: {nested_error}", exc_info=True
            )
            session.rollback()

        return False


def _process_activity_event(session: Session, event: WebhookEvent) -> bool:
    """
    Process an activity-related webhook event.

    Args:
        session: Database session
        event: WebhookEvent instance

    Returns:
        bool: True if processed successfully
    """
    activity_id = event.object_id
    athlete_id = event.owner_id
    aspect_type = event.aspect_type

    try:
        # Get user_id from athlete mapping
        mapping = (
            session.query(UserAthleteLink).filter_by(athlete_id=athlete_id).first()
        )

        if not mapping:
            logger.warning(
                f"⚠️ No user mapping found for athlete {athlete_id}, ignoring event"
            )
            event.status = WebhookEventStatus.IGNORED
            event.error_message = "No user mapping found"
            return False

        user_id = mapping.user_id

        if aspect_type == "create":
            return _handle_activity_create(
                session, activity_id, athlete_id, user_id, event
            )
        elif aspect_type == "update":
            return _handle_activity_update(
                session, activity_id, athlete_id, user_id, event
            )
        elif aspect_type == "delete":
            return _handle_activity_delete(session, activity_id, event)
        else:
            logger.warning(f"⚠️ Unknown aspect_type: {aspect_type}")
            event.status = WebhookEventStatus.IGNORED
            return False

    except Exception as e:
        logger.error(f"❌ Activity event processing error: {e}", exc_info=True)
        event.error_message = str(e)
        return False


def _handle_activity_create(
    session: Session,
    activity_id: int,
    athlete_id: int,
    user_id: str,
    event: WebhookEvent,
) -> bool:
    """
    Handle activity.create event - fetch and store new activity.

    This is the main webhook event we care about!
    """
    try:
        logger.info(f"📥 Fetching new activity {activity_id} for athlete {athlete_id}")

        # Check if activity already exists
        existing = session.query(Activity).filter_by(activity_id=activity_id).first()

        if existing:
            logger.info(f"ℹ️ Activity {activity_id} already exists, skipping fetch")
            return True

        # Get valid Strava access token
        access_token = get_valid_token(session, athlete_id)
        client = StravaClient(access_token)

        # Fetch activity details from Strava
        activity_data = client.get_activity(activity_id)

        if not activity_data:
            logger.error(f"❌ Failed to fetch activity {activity_id} from Strava")
            return False

        # Only process runs
        if activity_data.get("type") != "Run":
            logger.info(
                f"ℹ️ Activity {activity_id} is not a run (type={activity_data.get('type')}), ignoring"
            )
            event.status = WebhookEventStatus.IGNORED
            return False

        # Prepare activity data
        activity_data["activity_id"] = activity_data.pop("id", activity_id)
        activity_data["user_id"] = user_id

        # Store activity
        inserted = ActivityDAO.upsert_activities(
            session, athlete_id, [activity_data], user_id=user_id
        )

        if inserted > 0:
            logger.info(
                f"✅ Successfully stored activity {activity_id} for athlete {athlete_id}"
            )

            # Trigger enrichment for the newly stored activity
            try:
                logger.info(f"🔄 Starting enrichment for activity {activity_id}")
                enrich_one_activity_with_refresh(session, athlete_id, activity_id)
                logger.info(f"✅ Successfully enriched activity {activity_id}")
            except Exception as e:
                logger.error(f"❌ Failed to enrich activity {activity_id}: {e}")
                # Don't fail the webhook if enrichment fails - activity is still stored

            return True
        else:
            logger.error(f"❌ Failed to store activity {activity_id}")
            return False

    except Exception as e:
        logger.error(f"❌ Error creating activity {activity_id}: {e}", exc_info=True)
        return False


def _handle_activity_update(
    session: Session,
    activity_id: int,
    athlete_id: int,
    user_id: str,
    event: WebhookEvent,
) -> bool:
    """
    Handle activity.update event - update existing activity.

    Optional: You can implement this to keep activities in sync
    when users edit them in Strava.
    """
    logger.info(f"ℹ️ Activity update for {activity_id} - not yet implemented")

    # For now, we'll ignore update events
    # You can implement this later if you want to keep activities up-to-date
    event.status = WebhookEventStatus.IGNORED
    event.error_message = "Update events not yet implemented"

    return True


def _handle_activity_delete(
    session: Session, activity_id: int, event: WebhookEvent
) -> bool:
    """
    Handle activity.delete event - soft delete or mark as deleted.

    Optional: You can implement this to handle when users delete
    activities in Strava.
    """
    logger.info(f"ℹ️ Activity delete for {activity_id} - not yet implemented")

    # For now, we'll ignore delete events
    # You can implement soft delete later if needed
    event.status = WebhookEventStatus.IGNORED
    event.error_message = "Delete events not yet implemented"

    return True


def _process_athlete_event(session: Session, event: WebhookEvent) -> bool:
    """
    Process an athlete-related webhook event.

    We don't currently handle athlete events, but log them for reference.
    """
    logger.info(
        f"ℹ️ Athlete event: {event.aspect_type} for athlete {event.owner_id} - ignoring"
    )

    event.status = WebhookEventStatus.IGNORED
    event.error_message = "Athlete events not currently processed"

    return True


def retry_failed_events(session: Session, max_retries: int = 3):
    """
    Retry failed webhook events.

    Useful for handling temporary failures (network issues, rate limits, etc.)

    Args:
        session: Database session
        max_retries: Maximum number of retry attempts

    Returns:
        int: Number of events retried
    """
    failed_events = (
        session.query(WebhookEvent)
        .filter(
            WebhookEvent.status == WebhookEventStatus.FAILED,
            WebhookEvent.retry_count < max_retries,
        )
        .all()
    )

    logger.info(f"🔄 Retrying {len(failed_events)} failed events...")

    retried = 0
    for event in failed_events:
        # Reset to pending so it can be reprocessed
        event.status = WebhookEventStatus.PENDING
        session.commit()

        # Try processing again
        if process_webhook_event(session, event.id):
            retried += 1

    logger.info(f"✅ Successfully retried {retried}/{len(failed_events)} events")
    return retried
