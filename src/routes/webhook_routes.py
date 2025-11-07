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

from flask import Blueprint, request
from src.utils.response_utils import (
    success_response,
    error_response,
    validation_error_response,
    internal_error_response,
)
from src.utils.strava_validators import validate_webhook_event
from src.utils.auth_rate_limiter import rate_limit_auth
from src.db.db_session import get_session
from src.db.models.webhook_events import WebhookEvent, WebhookEventStatus
from src.db.models.user_athletes import UserAthleteLink
from src.services.webhook_processor_service import process_webhook_event
import os
import logging
import threading

webhook_bp = Blueprint("webhooks", __name__, url_prefix="/webhooks")
logger = logging.getLogger(__name__)

# Get webhook verification token from environment
WEBHOOK_VERIFY_TOKEN = os.getenv("STRAVA_WEBHOOK_VERIFY_TOKEN")


@webhook_bp.route("/strava", methods=["GET"])
@rate_limit_auth("webhook_verification")
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

    from src.utils.security_utils import redact_secret, sanitize_user_input

    # Sanitize inputs to prevent injection attacks
    mode = sanitize_user_input(mode, max_length=50) if mode else None
    challenge = sanitize_user_input(challenge, max_length=200) if challenge else None
    verify_token = (
        sanitize_user_input(verify_token, max_length=200) if verify_token else None
    )

    logger.info(
        f"🔐 Webhook verification request: mode={mode}, token={redact_secret(verify_token)}"
    )

    # Verify the request is legitimate
    # Use constant-time comparison to prevent timing attacks
    if mode == "subscribe" and verify_token and WEBHOOK_VERIFY_TOKEN:
        # Constant-time comparison for security
        import hmac

        token_match = hmac.compare_digest(verify_token, WEBHOOK_VERIFY_TOKEN)
        if token_match:
            logger.info("✅ Webhook verification successful!")
            # Strava requires exact format: {"hub.challenge": "<challenge>"}
            # Sanitize challenge before returning
            if challenge:
                from flask import jsonify

                return jsonify({"hub.challenge": challenge}), 200
            else:
                logger.warning("❌ Webhook verification failed - missing challenge")
                return error_response(
                    message="Verification failed",
                    status_code=400,
                    error_code="WEBHOOK_VERIFICATION_FAILED",
                )

    logger.warning("❌ Webhook verification failed - invalid token or mode")
    return error_response(
        message="Verification failed",
        status_code=403,
        error_code="WEBHOOK_VERIFICATION_FAILED",
    )


@webhook_bp.route("/strava", methods=["POST"])
@rate_limit_auth("webhook")
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
            return validation_error_response(
                message="No data provided",
                field="body",
            )

        # Validate webhook event data
        validated_event_data, error = validate_webhook_event(event_data)
        if error:
            logger.warning(
                f"⚠️ Invalid webhook event data: {error[0].json.get('error')}"
            )
            return error

        # Use validated data
        event_data = validated_event_data
        object_type = event_data.get("object_type")
        object_id = event_data.get("object_id")
        aspect_type = event_data.get("aspect_type")
        owner_id = event_data.get("owner_id")

        logger.info(
            f"📬 Webhook received: {object_type}.{aspect_type} "
            f"(object_id={object_id}, owner_id={owner_id})"
        )

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
            return internal_error_response(
                message="Database error",
                log_error=e,
            )
        finally:
            session.close()

        # Process asynchronously (don't block Strava's webhook)
        from src.utils.strava_helpers import run_background_job

        def process_webhook_job(session, event_id):
            """Process webhook event in background thread"""
            process_webhook_event(session, event_id)

        run_background_job(process_webhook_job, event_id)

        # Respond immediately to Strava (they want fast 200 OK)
        return success_response(
            data={"event_id": event_id},
            message="Webhook event received",
        )

    except Exception as e:
        logger.error(f"❌ Webhook handling error: {e}", exc_info=True)
        # Still return 200 to avoid Strava retrying (webhook requirement)
        # But use standardized response format
        return success_response(
            data={"status": "error", "message": str(e)},
            message="Webhook received but processing failed",
        )


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

        return success_response(
            data={
                "verify_token_configured": bool(WEBHOOK_VERIFY_TOKEN),
                "stats": status_counts,
                "recent_events": [event.to_dict() for event in recent_events],
            },
            message="Webhook status",
        )

    except Exception as e:
        logger.error(f"❌ Status check failed: {e}", exc_info=True)
        return internal_error_response(
            message="Failed to fetch webhook status",
            log_error=e,
        )
    finally:
        session.close()
