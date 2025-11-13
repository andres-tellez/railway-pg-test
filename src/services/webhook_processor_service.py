"""
Webhook Processor Service
==========================

Webhook Event Processing Service
==================================

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
from src.services.activity_service import enrich_one_activity_with_refresh
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
    event = session.query(WebhookEvent).filter_by(id=event_id).first()

    if not event:
        logger.error(f"Webhook event {event_id} not found")
        return False

    if event.status == WebhookEventStatus.COMPLETED:
        logger.info(f"Event {event_id} already processed")
        return True

    try:
        event.status = WebhookEventStatus.PROCESSING
        event.processed_at = datetime.utcnow()
        session.commit()

        logger.info(
            f"Processing webhook event {event_id}: {event.object_type}.{event.aspect_type}"
        )

        # Get user-athlete mapping
        athlete_link = (
            session.query(UserAthleteLink).filter_by(athlete_id=event.owner_id).first()
        )

        if not athlete_link:
            logger.warning(
                f"No user-athlete link found for athlete {event.owner_id}, skipping event {event_id}"
            )
            event.status = WebhookEventStatus.FAILED
            event.error_message = "No user-athlete link found"
            session.commit()
            return False

        user_id = athlete_link.user_id

        # Handle different event types
        if event.object_type == "activity":
            if event.aspect_type == "create":
                _handle_activity_create(session, event, user_id)
            elif event.aspect_type == "update":
                _handle_activity_update(session, event, user_id)
            elif event.aspect_type == "delete":
                _handle_activity_delete(session, event, user_id)
            else:
                logger.warning(
                    f"Unknown aspect type: {event.aspect_type} for activity event {event_id}"
                )
                event.status = WebhookEventStatus.FAILED
                event.error_message = f"Unknown aspect type: {event.aspect_type}"
                session.commit()
                return False

        elif event.object_type == "athlete":
            # For now, just log athlete events
            logger.info(f"Athlete event {event_id}: {event.aspect_type}")
            event.status = WebhookEventStatus.COMPLETED
            session.commit()
            return True

        else:
            logger.warning(
                f"Unknown object type: {event.object_type} for event {event_id}"
            )
            event.status = WebhookEventStatus.FAILED
            event.error_message = f"Unknown object type: {event.object_type}"
            session.commit()
            return False

        # Mark as completed
        event.status = WebhookEventStatus.COMPLETED
        session.commit()

        logger.info(f"Successfully processed webhook event {event_id}")
        return True

    except Exception as e:
        logger.exception(f"Error processing webhook event {event_id}: {e}")
        event.status = WebhookEventStatus.FAILED
        event.error_message = str(e)[:500]  # Truncate error message
        event.processed_at = datetime.utcnow()
        session.rollback()
        session.commit()
        return False


def _handle_activity_create(session: Session, event: WebhookEvent, user_id):
    """Handle activity.create webhook event."""
    # Convert user_id to string if it's a UUID object
    if user_id is not None:
        user_id = str(user_id) if not isinstance(user_id, str) else user_id

        # Validate UUID format (simple check, no Flask responses)
        import re
        import uuid as uuid_lib

        uuid_pattern = re.compile(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
        )
        if not uuid_pattern.match(user_id):
            try:
                # Try to parse as UUID to validate format
                uuid_lib.UUID(user_id)
            except (ValueError, AttributeError):
                logger.warning(
                    f"Invalid user_id format: {user_id}, continuing without user_id"
                )
                user_id = None  # Continue without user_id rather than failing

    activity_id = event.object_id

    logger.info(f"Fetching new activity {activity_id} from Strava")

    # Get athlete_id
    athlete_id = event.owner_id

    # Get valid Strava access token
    access_token = get_valid_token(session, athlete_id)
    if not access_token:
        raise ValueError(f"No valid token for athlete {athlete_id}")

    # Fetch activity from Strava
    client = StravaClient(access_token)
    activity_data = client.get_activity(activity_id)

    if not activity_data:
        raise ValueError(f"Failed to fetch activity {activity_id} from Strava")

    # Check if it's a run
    activity_type = activity_data.get("type")
    if activity_type != "Run":
        logger.info(
            f"Activity {activity_id} is type '{activity_type}', not a run - skipping"
        )
        return

    # Prepare activity data
    activity_data["activity_id"] = activity_data.pop("id", activity_id)
    activity_data["user_id"] = user_id

    # Store activity
    inserted = ActivityDAO.upsert_activities(
        session, athlete_id, [activity_data], user_id=user_id
    )

    if inserted > 0:
        logger.info(f"Successfully stored new activity {activity_id}")

        # Enrich the activity
        try:
            enrich_one_activity_with_refresh(session, athlete_id, activity_id)
            logger.info(f"Successfully enriched activity {activity_id}")
        except Exception as e:
            logger.warning(f"Failed to enrich activity {activity_id}: {e}")
            # Don't fail the webhook processing if enrichment fails
    else:
        logger.warning(f"Activity {activity_id} not inserted (may already exist)")


def _handle_activity_update(session: Session, event: WebhookEvent, user_id):
    """Handle activity.update webhook event."""
    # Convert user_id to string if it's a UUID object
    if user_id is not None:
        user_id = str(user_id) if not isinstance(user_id, str) else user_id

        # Validate UUID format (simple check, no Flask responses)
        import re
        import uuid as uuid_lib

        uuid_pattern = re.compile(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
        )
        if not uuid_pattern.match(user_id):
            try:
                # Try to parse as UUID to validate format
                uuid_lib.UUID(user_id)
            except (ValueError, AttributeError):
                logger.warning(
                    f"Invalid user_id format: {user_id}, continuing without user_id"
                )
                user_id = None  # Continue without user_id rather than failing

    activity_id = event.object_id

    logger.info(f"Updating activity {activity_id} from Strava")

    # Get athlete_id
    athlete_id = event.owner_id

    # Get valid Strava access token
    access_token = get_valid_token(session, athlete_id)
    if not access_token:
        raise ValueError(f"No valid token for athlete {athlete_id}")

    # Fetch updated activity from Strava
    client = StravaClient(access_token)
    activity_data = client.get_activity(activity_id)

    if not activity_data:
        raise ValueError(f"Failed to fetch updated activity {activity_id} from Strava")

    # Check if it's a run
    activity_type = activity_data.get("type")
    if activity_type != "Run":
        logger.info(
            f"Activity {activity_id} is type '{activity_type}', not a run - skipping update"
        )
        return

    # Prepare activity data
    activity_data["activity_id"] = activity_data.pop("id", activity_id)
    activity_data["user_id"] = user_id

    # Update activity
    updated = ActivityDAO.upsert_activities(
        session, athlete_id, [activity_data], user_id=user_id
    )

    if updated > 0:
        logger.info(f"Successfully updated activity {activity_id}")

        # Re-enrich the activity
        try:
            enrich_one_activity_with_refresh(session, athlete_id, activity_id)
            logger.info(f"Successfully re-enriched activity {activity_id}")
        except Exception as e:
            logger.warning(f"Failed to re-enrich activity {activity_id}: {e}")
            # Don't fail the webhook processing if enrichment fails
    else:
        logger.warning(f"Activity {activity_id} not updated")


def _handle_activity_delete(session: Session, event: WebhookEvent, user_id):
    """Handle activity.delete webhook event."""
    activity_id = event.object_id

    logger.info(f"Deleting activity {activity_id}")

    # Soft delete: mark as deleted in database
    activity = session.query(Activity).filter_by(activity_id=activity_id).first()

    if activity:
        # For now, we'll keep the activity but could mark it as deleted
        # This allows users to see their historical data
        logger.info(
            f"Activity {activity_id} exists but will be kept (soft delete not implemented)"
        )
    else:
        logger.info(f"Activity {activity_id} not found in database")
