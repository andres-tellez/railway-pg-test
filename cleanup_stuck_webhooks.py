#!/usr/bin/env python3
"""
Clean up stuck webhook events by marking them as IGNORED or FAILED.

This script will:
1. Find all PENDING or PROCESSING webhook events older than a certain time
2. Mark them as IGNORED (for old events) or FAILED (for processing events)
"""

import os
import sys
import argparse
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# Load environment variables (prioritize .env.prod)
if os.path.exists(".env.prod"):
    load_dotenv(".env.prod")
elif os.path.exists(".env.local"):
    load_dotenv(".env.local")

# Allow overriding DATABASE_URL via command line
parser_pre = argparse.ArgumentParser(add_help=False)
parser_pre.add_argument("--database-url", help="Database URL to use")
args_pre, _ = parser_pre.parse_known_args()

if args_pre.database_url:
    os.environ["DATABASE_URL"] = args_pre.database_url
    print(f"Using database URL from --database-url argument")
elif os.getenv("PROD_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.getenv("PROD_DATABASE_URL")
    print(f"Using database URL from PROD_DATABASE_URL environment variable")

from src.db.db_session import get_session
from src.db.models.webhook_events import WebhookEvent, WebhookEventStatus
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def cleanup_stuck_events(older_than_hours=1, mark_as="IGNORED"):
    """
    Clean up stuck webhook events.

    Args:
        older_than_hours: Only clean events older than this many hours
        mark_as: What status to mark them as ("IGNORED" or "FAILED")
    """
    session = get_session()

    try:
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)

        # Find all PENDING or PROCESSING events older than cutoff
        stuck_events = (
            session.query(WebhookEvent)
            .filter(
                WebhookEvent.status.in_(
                    [WebhookEventStatus.PENDING, WebhookEventStatus.PROCESSING]
                )
            )
            .filter(WebhookEvent.received_at < cutoff_time)
            .order_by(WebhookEvent.received_at.asc())
            .all()
        )

        if not stuck_events:
            print(
                f"✅ No stuck webhook events found (older than {older_than_hours} hours)"
            )
            return

        print(
            f"Found {len(stuck_events)} stuck webhook event(s) older than {older_than_hours} hours:"
        )
        for event in stuck_events:
            age = datetime.now(timezone.utc) - event.received_at.replace(
                tzinfo=timezone.utc
            )
            print(
                f"  - Event {event.id}: {event.object_type}.{event.aspect_type} "
                f"(object_id={event.object_id}, status={event.status.value}, "
                f"age={age}, received_at={event.received_at})"
            )

        # Confirm action
        print(f"\n⚠️  Will mark these as {mark_as}")
        response = input("Continue? (yes/no): ").strip().lower()

        if response != "yes":
            print("Cancelled")
            return

        # Mark events
        target_status = (
            WebhookEventStatus.IGNORED
            if mark_as == "IGNORED"
            else WebhookEventStatus.FAILED
        )

        for event in stuck_events:
            old_status = event.status.value
            event.status = target_status
            event.error_message = (
                f"Stuck in {old_status} status, cleaned up automatically"
            )
            event.processed_at = datetime.utcnow()
            print(f"   Marked event {event.id} as {target_status.value}")

        session.commit()
        print(
            f"\n✅ Successfully marked {len(stuck_events)} event(s) as {target_status.value}"
        )

        # Show final status
        print("\n📊 Current webhook event status:")
        from sqlalchemy import func

        final_status = (
            session.query(WebhookEvent.status, func.count(WebhookEvent.id))
            .group_by(WebhookEvent.status)
            .all()
        )
        for status, count in final_status:
            print(f"   {status.value}: {count}")

    except Exception as e:
        logger.exception(f"Error cleaning up stuck events: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean up stuck webhook events")
    parser.add_argument(
        "--database-url", help="Database URL to use (overrides environment variables)"
    )
    parser.add_argument(
        "--older-than-hours",
        type=int,
        default=1,
        help="Only clean events older than this many hours (default: 1)",
    )
    parser.add_argument(
        "--mark-as",
        choices=["IGNORED", "FAILED"],
        default="IGNORED",
        help="What status to mark stuck events as (default: IGNORED)",
    )

    args = parser.parse_args()
    cleanup_stuck_events(args.older_than_hours, args.mark_as)
