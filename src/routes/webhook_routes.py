"""
webhook_routes.py

Strava Webhook Event Handling
==============================

This module handles incoming webhook events from Strava for real-time
activity synchronization.

Strava Webhook Flow:
1. Verification (GET): Strava sends a challenge, we echo it back
2. Events (POST): Strava notifies us of activity changes
3. Processing: We fetch and store the activity asynchronously

Webhook Events We Handle:
- activity.create → Automatically fetch and store new activity
- activity.update → Update existing activity (optional)
- activity.delete → Mark activity as deleted (optional)

Security:
- Webhook verification via verify_token
- HTTPS required (Railway provides this)
- Event deduplication via database constraints

References:
- https://developers.strava.com/docs/webhooks/
"""

from flask import Blueprint, request, jsonify
from src.db.db_session import get_session
from src.db.models.webhook_events import WebhookEvent, WebhookEventStatus
from src.db.models.user_athletes import UserAthleteLink
from src.services.webhook_processor import process_webhook_event
import os
import logging
import threading

webhook_bp = Blueprint("webhooks", __name__)
logger = logging.getLogger(__name__)

# Get webhook verification token from environment
WEBHOOK_VERIFY_TOKEN = os.getenv("STRAVA_WEBHOOK_VERIFY_TOKEN")


@webhook_bp.route("/strava", methods=["GET"])
def verify_webhook():
    """
    Handle Strava webhook verification challenge.

    When you create a webhook subscription, Strava sends a GET request
    with a challenge code. We must echo it back to prove we control the endpoint.

    Query Parameters:
    - hub.mode: "subscribe"
    - hub.challenge: Random string to echo back
    - hub.verify_token: Our secret token

    Returns:
    - {"hub.challenge": "<challenge>"} with 200 OK
    """
    mode = request.args.get("hub.mode")
    challenge = request.args.get("hub.challenge")
    verify_token = request.args.get("hub.verify_token")

    logger.info(
        f"🔐 Webhook verification request: mode={mode}, token={verify_token[:10]}..."
    )

    # Verify the request is legitimate
    if mode == "subscribe" and verify_token == WEBHOOK_VERIFY_TOKEN:
        logger.info("✅ Webhook verification successful!")
        return jsonify({"hub.challenge": challenge}), 200
    else:
        logger.warning("❌ Webhook verification failed - invalid token")
        return jsonify({"error": "Verification failed"}), 403


@webhook_bp.route("/strava", methods=["POST"])
def receive_webhook():
    """
    Receive webhook events from Strava.

    Strava sends POST requests when activities change:
    {
        "object_type": "activity",
        "object_id": 123456789,
        "aspect_type": "create",
        "owner_id": 347085,
        "subscription_id": 12345,
        "event_time": 1234567890,
        "updates": {}
    }

    Flow:
    1. Validate request
    2. Store event in database (fast response)
    3. Process asynchronously in background
    4. Return 200 OK immediately

    Returns:
    - {"status": "received"} with 200 OK
    """
    try:
        # Get event data
        event_data = request.get_json()

        if not event_data:
            logger.warning("⚠️ Received webhook with no JSON body")
            return jsonify({"error": "No data provided"}), 400

        object_type = event_data.get("object_type")
        object_id = event_data.get("object_id")
        aspect_type = event_data.get("aspect_type")
        owner_id = event_data.get("owner_id")

        logger.info(
            f"📬 Webhook received: {object_type}.{aspect_type} "
            f"(object_id={object_id}, owner_id={owner_id})"
        )

        # Quick validation
        if not all([object_type, object_id, aspect_type, owner_id]):
            logger.warning("⚠️ Webhook missing required fields")
            return jsonify({"error": "Missing required fields"}), 400

        # Store event in database (fast!)
        session = get_session()
        try:
            webhook_event = WebhookEvent(
                object_type=object_type,
                object_id=object_id,
                aspect_type=aspect_type,
                owner_id=owner_id,
                subscription_id=event_data.get("subscription_id"),
                event_time=event_data.get("event_time"),
                updates=event_data.get("updates", {}),
                status=WebhookEventStatus.PENDING,
            )

            session.add(webhook_event)
            session.commit()

            event_id = webhook_event.id
            logger.info(f"✅ Webhook event stored: ID={event_id}")

        except Exception as e:
            session.rollback()
            logger.error(f"❌ Failed to store webhook event: {e}", exc_info=True)
            return jsonify({"error": "Database error"}), 500
        finally:
            session.close()

        # Process asynchronously (don't block Strava's webhook)
        def background_processing():
            """Process webhook event in background thread"""
            process_session = get_session()
            try:
                process_webhook_event(process_session, event_id)
            except Exception as e:
                logger.error(
                    f"❌ Background processing failed for event {event_id}: {e}",
                    exc_info=True,
                )
            finally:
                process_session.close()

        # Start background thread
        threading.Thread(target=background_processing, daemon=True).start()

        # Respond immediately to Strava (they want fast 200 OK)
        return jsonify({"status": "received", "event_id": event_id}), 200

    except Exception as e:
        logger.error(f"❌ Webhook handling error: {e}", exc_info=True)
        # Still return 200 to avoid Strava retrying
        return jsonify({"status": "error", "message": str(e)}), 200


@webhook_bp.route("/strava/status", methods=["GET"])
def webhook_status():
    """
    Get webhook processing status and statistics.

    Returns:
    - Event counts by status
    - Recent events
    - Processing health
    """
    session = get_session()
    try:
        from sqlalchemy import func

        # Count events by status
        stats = (
            session.query(WebhookEvent.status, func.count(WebhookEvent.id))
            .group_by(WebhookEvent.status)
            .all()
        )

        status_counts = {
            status.value: count for status, count in stats if status is not None
        }

        # Get recent events
        recent_events = (
            session.query(WebhookEvent)
            .order_by(WebhookEvent.received_at.desc())
            .limit(10)
            .all()
        )

        return (
            jsonify(
                {
                    "status": "ok",
                    "verify_token_configured": bool(WEBHOOK_VERIFY_TOKEN),
                    "stats": status_counts,
                    "recent_events": [event.to_dict() for event in recent_events],
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"❌ Status check failed: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        session.close()
