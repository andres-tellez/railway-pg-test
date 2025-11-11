#!/usr/bin/env python3
"""
Retry processing stuck webhook events.

This script will:
1. Find all PENDING or PROCESSING webhook events
2. Retry processing them
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables (prioritize .env.prod)
if os.path.exists(".env.prod"):
    load_dotenv(".env.prod")
elif os.path.exists(".env.local"):
    load_dotenv(".env.local")

from src.db.db_session import get_session
from src.db.models.webhook_events import WebhookEvent, WebhookEventStatus
from src.services.webhook_processor_service import process_webhook_event
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def retry_stuck_events():
    """Retry processing stuck webhook events."""
    session = get_session()

    try:
        # Find all PENDING or PROCESSING events
        stuck_events = (
            session.query(WebhookEvent)
            .filter(
                WebhookEvent.status.in_(
                    [WebhookEventStatus.PENDING, WebhookEventStatus.PROCESSING]
                )
            )
            .order_by(WebhookEvent.received_at.asc())
            .all()
        )

        if not stuck_events:
            print("✅ No stuck webhook events found")
            return

        print(f"Found {len(stuck_events)} stuck webhook event(s):")
        for event in stuck_events:
            print(
                f"  - Event {event.id}: {event.object_type}.{event.aspect_type} "
                f"(object_id={event.object_id}, status={event.status.value}, "
                f"received_at={event.received_at})"
            )

        print("\nRetrying processing...")

        for event in stuck_events:
            print(f"\n🔄 Retrying event {event.id}...")
            try:
                # Reset status to PENDING if it's PROCESSING (might be stuck)
                if event.status == WebhookEventStatus.PROCESSING:
                    event.status = WebhookEventStatus.PENDING
                    event.processed_at = None
                    session.commit()
                    print(f"   Reset status from PROCESSING to PENDING")

                # Process the event
                success = process_webhook_event(session, event.id)

                if success:
                    print(f"   ✅ Successfully processed event {event.id}")
                else:
                    print(f"   ❌ Failed to process event {event.id}")

            except Exception as e:
                logger.exception(f"Error retrying event {event.id}: {e}")
                print(f"   ❌ Exception: {e}")

        # Show final status
        print("\n📊 Final status:")
        final_status = (
            session.query(WebhookEvent.status, func.count(WebhookEvent.id))
            .group_by(WebhookEvent.status)
            .all()
        )
        for status, count in final_status:
            print(f"   {status.value}: {count}")

    finally:
        session.close()


if __name__ == "__main__":
    from sqlalchemy import func

    retry_stuck_events()
