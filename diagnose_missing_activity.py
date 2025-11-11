#!/usr/bin/env python3
"""
Diagnostic script to investigate why a run activity wasn't captured.

Usage:
    # Using email (connects to database from .env.local or DATABASE_URL)
    python diagnose_missing_activity.py andres.tellez@gmail.com

    # Using athlete_id
    python diagnose_missing_activity.py 347085

    # With production database URL
    python diagnose_missing_activity.py "postgres://..." andres.tellez@gmail.com

    # Or set PROD_DATABASE_URL environment variable
    export PROD_DATABASE_URL="postgres://..."
    python diagnose_missing_activity.py andres.tellez@gmail.com

Environment:
    - Checks .env.prod first (if exists)
    - Then .env.local (if exists)
    - Then system DATABASE_URL
    - Or use PROD_DATABASE_URL for production
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
# Priority: command line arg > .env.prod > .env.local > system env
env_path = Path(__file__).parent / ".env.local"
if env_path.exists():
    load_dotenv(env_path)

# Check for production env file
prod_env_path = Path(__file__).parent / ".env.prod"
if prod_env_path.exists():
    load_dotenv(prod_env_path, override=True)

# Allow DATABASE_URL override via command line or environment
if len(sys.argv) > 1 and sys.argv[1].startswith("postgres://"):
    # First arg is database URL
    os.environ["DATABASE_URL"] = sys.argv[1]
    sys.argv = [sys.argv[0]] + sys.argv[2:]
elif os.getenv("PROD_DATABASE_URL"):
    # Use production database URL if set
    os.environ["DATABASE_URL"] = os.getenv("PROD_DATABASE_URL")

from src.db.db_session import get_session
from src.db.models.webhook_events import WebhookEvent, WebhookEventStatus
from src.db.models.user_athletes import UserAthleteLink
from src.db.models.activities import Activity
from src.db.models.tokens import Token
from src.db.models.strava_sync_status import StravaSyncStatus
from sqlalchemy import func, desc


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def check_webhook_events(session, athlete_id, hours_back=24):
    """Check recent webhook events for this athlete."""
    print_section("1. RECENT WEBHOOK EVENTS")

    cutoff = datetime.utcnow() - timedelta(hours=hours_back)

    events = (
        session.query(WebhookEvent)
        .filter(WebhookEvent.owner_id == athlete_id, WebhookEvent.received_at >= cutoff)
        .order_by(desc(WebhookEvent.received_at))
        .all()
    )

    if not events:
        print(
            f"❌ No webhook events found for athlete {athlete_id} in last {hours_back} hours"
        )
        print("   This suggests:")
        print("   - Webhook subscription may not be active")
        print("   - Strava didn't send webhook for this activity")
        print("   - Network/firewall blocking webhook endpoint")
        return False

    print(f"✅ Found {len(events)} webhook event(s) in last {hours_back} hours:\n")

    for event in events:
        status_emoji = {
            WebhookEventStatus.PENDING: "⏳",
            WebhookEventStatus.PROCESSING: "🔄",
            WebhookEventStatus.PROCESSED: "✅",
            WebhookEventStatus.FAILED: "❌",
            WebhookEventStatus.IGNORED: "🚫",
        }.get(event.status, "❓")

        print(f"  {status_emoji} Event ID: {event.id}")
        print(f"     Type: {event.object_type}.{event.aspect_type}")
        print(f"     Object ID: {event.object_id}")
        print(f"     Status: {event.status.value if event.status else 'None'}")
        print(f"     Received: {event.received_at}")

        if event.status == WebhookEventStatus.FAILED:
            print(f"     ❌ ERROR: {event.error_message}")
            print(f"     Retry count: {event.retry_count}")

        if event.processed_at:
            print(f"     Processed: {event.processed_at}")

        print()

    return True


def check_user_athlete_link(session, athlete_id, user_id=None):
    """Check if athlete is linked to a user."""
    print_section("2. USER-ATHLETE LINKAGE")

    # Show all existing links for context
    all_links = session.query(UserAthleteLink).all()
    print(f"Total user-athlete links in database: {len(all_links)}\n")

    if all_links:
        print("Existing links:")
        from src.db.models.user_identity import UserIdentity

        for l in all_links:
            user_check = (
                session.query(UserIdentity).filter_by(user_id=l.user_id).first()
            )
            email_display = user_check.email if user_check else "unknown"
            print(
                f"   User: {l.user_id[:8]}... ({email_display}) → Athlete: {l.athlete_id}"
            )
        print()

    if user_id:
        link = session.query(UserAthleteLink).filter_by(user_id=user_id).first()
    else:
        link = session.query(UserAthleteLink).filter_by(athlete_id=athlete_id).first()

    if not link:
        print(f"❌ No user-athlete link found!")
        if athlete_id:
            print(f"   Athlete ID: {athlete_id}")
        if user_id:
            print(f"   User ID: {user_id}")
        print("\n   This is CRITICAL - webhook processing requires this link.")
        print("   Solution: Reconnect Strava account via OAuth flow.")
        return False

    print(f"✅ User-Athlete link found:")
    print(f"   User ID: {link.user_id}")
    print(f"   Athlete ID: {link.athlete_id}")
    print(f"   Created: {link.created_at}")

    return link.user_id


def check_token_status(session, athlete_id):
    """Check Strava token status."""
    print_section("3. STRAVA TOKEN STATUS")

    token = session.query(Token).filter_by(athlete_id=athlete_id).first()

    if not token:
        print(f"❌ No token found for athlete {athlete_id}")
        print("   This will prevent fetching activities from Strava.")
        print("   Solution: Reconnect Strava account via OAuth flow.")
        return False

    now = datetime.utcnow().timestamp()
    expires_at = token.expires_at

    if token.is_revoked():
        print(f"❌ Token is REVOKED (revoked_at: {token.revoked_at})")
        print("   Solution: Reconnect Strava account via OAuth flow.")
        return False

    if expires_at <= now:
        print(f"⚠️  Token is EXPIRED")
        print(f"   Expires at: {datetime.fromtimestamp(expires_at)}")
        print(f"   Current time: {datetime.fromtimestamp(now)}")
        print(
            "   Note: Token refresh should happen automatically, but may have failed."
        )
        print("   Solution: Try manual sync or reconnect Strava account.")
        return False

    expires_in = expires_at - now
    expires_in_hours = expires_in / 3600

    print(f"✅ Token is valid")
    print(f"   Expires in: {expires_in_hours:.1f} hours ({expires_in/60:.0f} minutes)")
    print(f"   Expires at: {datetime.fromtimestamp(expires_at)}")

    return True


def check_recent_activities(session, athlete_id, hours_back=24):
    """Check for recent activities in database."""
    print_section("4. RECENT ACTIVITIES IN DATABASE")

    cutoff = datetime.utcnow() - timedelta(hours=hours_back)

    activities = (
        session.query(Activity)
        .filter(Activity.athlete_id == athlete_id, Activity.start_date >= cutoff)
        .order_by(desc(Activity.start_date))
        .all()
    )

    if not activities:
        print(
            f"❌ No activities found for athlete {athlete_id} in last {hours_back} hours"
        )
        return False

    print(f"✅ Found {len(activities)} activity/ies in last {hours_back} hours:\n")

    for act in activities:
        enriched = act.average_speed is not None and act.average_heartrate is not None
        enriched_emoji = "✅" if enriched else "⚠️"

        print(f"  {enriched_emoji} Activity ID: {act.activity_id}")
        print(f"     Name: {act.name}")
        print(f"     Date: {act.start_date}")
        print(
            f"     Distance: {act.distance}m ({act.conv_distance if act.conv_distance else 'N/A'} miles)"
        )
        print(
            f"     Enriched: {'Yes' if enriched else 'No (missing HR zones/metrics)'}"
        )
        print()

    return True


def check_sync_status(session, user_id, athlete_id):
    """Check recent sync status."""
    print_section("5. RECENT SYNC STATUS")

    syncs = (
        session.query(StravaSyncStatus)
        .filter(
            StravaSyncStatus.user_id == str(user_id),
            StravaSyncStatus.athlete_id == athlete_id,
        )
        .order_by(desc(StravaSyncStatus.started_at))
        .limit(5)
        .all()
    )

    if not syncs:
        print("No sync status records found (may be normal if syncs are infrequent)")
        return

    print(f"Found {len(syncs)} recent sync record(s):\n")

    for sync in syncs:
        status_emoji = {
            "pending": "⏳",
            "processing": "🔄",
            "completed": "✅",
            "failed": "❌",
        }.get(sync.status, "❓")

        print(f"  {status_emoji} Status: {sync.status}")
        print(f"     Started: {sync.started_at}")
        print(f"     Progress: {sync.progress}%")
        print(f"     Step: {sync.step}")

        if sync.detail:
            print(f"     Detail: {sync.detail}")

        if sync.error_code:
            print(f"     ❌ Error Code: {sync.error_code}")

        if sync.completed_at:
            print(f"     Completed: {sync.completed_at}")

        print()


def get_athlete_id_from_user(session, user_id):
    """Get athlete_id from user_id."""
    link = session.query(UserAthleteLink).filter_by(user_id=user_id).first()
    return link.athlete_id if link else None


def get_user_id_from_email(session, email):
    """Get user_id from email."""
    from src.db.models.user_identity import UserIdentity

    user = session.query(UserIdentity).filter_by(email=email).first()
    return str(user.user_id) if user else None


def main():
    """Main diagnostic function."""
    session = get_session()

    try:
        # Parse arguments
        athlete_id = None
        user_email = None

        if len(sys.argv) > 1:
            try:
                athlete_id = int(sys.argv[1])
            except ValueError:
                user_email = sys.argv[1]

        if len(sys.argv) > 2:
            user_email = sys.argv[2]

        # Try to detect from environment or prompt
        if not athlete_id and not user_email:
            user_email = os.getenv("USER_EMAIL")
            if not user_email:
                print("Please provide athlete_id or user_email as argument")
                print(
                    "Usage: python diagnose_missing_activity.py [athlete_id] [user_email]"
                )
                return

        user_id = None
        if user_email:
            user_id = get_user_id_from_email(session, user_email)
            if not user_id:
                print(f"❌ User not found with email: {user_email}")
                return
            print(f"Found user: {user_email} (user_id: {user_id})")
            athlete_id = get_athlete_id_from_user(session, user_id)
            if not athlete_id:
                print(f"❌ No athlete linked to user {user_email}")
                return

        if not athlete_id:
            print("❌ Could not determine athlete_id")
            return

        print(f"\n🔍 Diagnosing missing activity for athlete_id: {athlete_id}")
        if user_id:
            print(f"   User ID: {user_id}")

        # Run diagnostics
        has_webhooks = check_webhook_events(session, athlete_id)
        user_id = check_user_athlete_link(session, athlete_id, user_id)
        has_token = check_token_status(session, athlete_id)
        has_activities = check_recent_activities(session, athlete_id)

        if user_id:
            check_sync_status(session, user_id, athlete_id)

        # Summary
        print_section("SUMMARY & RECOMMENDATIONS")

        if not has_webhooks:
            print("❌ No webhook events received")
            print("   → Check webhook subscription status")
            print("   → Verify webhook endpoint is accessible")
            print("   → Check Strava webhook subscription in Strava Developer Portal")

        if not user_id:
            print("❌ Missing user-athlete link")
            print("   → Reconnect Strava account via OAuth")

        if not has_token:
            print("❌ Missing or invalid token")
            print("   → Reconnect Strava account via OAuth")

        if not has_activities:
            print("⚠️  No recent activities found")
            print("   → Activity may not have been synced yet")
            print("   → Try manual sync: POST /admin/trigger-ingest/<athlete_id>")
            print(
                f"   → Or fetch specific activity: POST /admin/fetch-activity/<activity_id>?athlete_id={athlete_id}"
            )

        if has_webhooks and user_id and has_token and not has_activities:
            print("✅ Infrastructure looks good, but activity missing")
            print("   → Check webhook event error messages above")
            print("   → Activity may have been filtered (not a Run type)")
            print("   → Try manual fetch with activity_id from Strava")

    except Exception as e:
        print(f"❌ Error during diagnosis: {e}")
        import traceback

        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    main()
