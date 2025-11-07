"""
Clean Database Script
====================

Deletes all data from all tables to prepare for fresh testing.

⚠️  WARNING: This will delete ALL data from the database!
Use only in development/staging environments.

Usage:
    python scripts/clean_database.py

Note:
    Tables are deleted in order to respect foreign key constraints.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.db.db_session import get_session
from src.db.models.activities import Activity
from src.db.models.user_identity import UserIdentity
from src.db.models.user_profile import UserProfile
from src.db.models.user_athletes import UserAthleteLink
from src.db.models.user_auth_providers import UserAuthProvider
from src.db.models.tokens import Token
from src.db.models.plans import Plan
from src.db.models.plans import PlanWorkout
from src.db.models.splits import Split
from src.db.models.conversations import Conversation, ConversationMessage
from src.db.models.webhook_events import WebhookEvent
from src.db.models.auth_audit_log import AuthAuditLog
from src.db.models.weekly_metrics import WeeklyMetrics
from src.db.models.weekly_decision_log import WeeklyDecisionLog


def clean_database():
    """Delete all data from all tables."""
    session = get_session()

    try:
        print("🗑️  Starting database cleanup...")

        # Delete in correct order (respecting foreign key constraints)
        # Start with child tables, then parent tables

        # Activities and related data
        print("  Deleting splits...")
        deleted = session.query(Split).delete()
        print(f"    ✅ Deleted {deleted} splits")

        print("  Deleting activities...")
        deleted = session.query(Activity).delete()
        print(f"    ✅ Deleted {deleted} activities")

        # Plan related data
        print("  Deleting plan workouts...")
        deleted = session.query(PlanWorkout).delete()
        print(f"    ✅ Deleted {deleted} plan workouts")

        print("  Deleting plans...")
        deleted = session.query(Plan).delete()
        print(f"    ✅ Deleted {deleted} plans")

        # Conversation related data
        print("  Deleting conversation messages...")
        deleted = session.query(ConversationMessage).delete()
        print(f"    ✅ Deleted {deleted} conversation messages")

        print("  Deleting conversations...")
        deleted = session.query(Conversation).delete()
        print(f"    ✅ Deleted {deleted} conversations")

        # Webhook events
        print("  Deleting webhook events...")
        deleted = session.query(WebhookEvent).delete()
        print(f"    ✅ Deleted {deleted} webhook events")

        # Weekly metrics and decision logs
        print("  Deleting weekly decision logs...")
        deleted = session.query(WeeklyDecisionLog).delete()
        print(f"    ✅ Deleted {deleted} weekly decision logs")

        print("  Deleting weekly metrics...")
        deleted = session.query(WeeklyMetrics).delete()
        print(f"    ✅ Deleted {deleted} weekly metrics")

        # Audit logs
        print("  Deleting auth audit logs...")
        deleted = session.query(AuthAuditLog).delete()
        print(f"    ✅ Deleted {deleted} auth audit logs")

        # User related data
        print("  Deleting tokens...")
        deleted = session.query(Token).delete()
        print(f"    ✅ Deleted {deleted} tokens")

        print("  Deleting user-athlete links...")
        deleted = session.query(UserAthleteLink).delete()
        print(f"    ✅ Deleted {deleted} user-athlete links")

        print("  Deleting user profiles...")
        deleted = session.query(UserProfile).delete()
        print(f"    ✅ Deleted {deleted} user profiles")

        print("  Deleting user auth providers...")
        deleted = session.query(UserAuthProvider).delete()
        print(f"    ✅ Deleted {deleted} user auth providers")

        print("  Deleting user identities...")
        deleted = session.query(UserIdentity).delete()
        print(f"    ✅ Deleted {deleted} user identities")

        # Commit all deletions
        session.commit()
        print("\n✅ Database cleaned successfully!")
        print("   All tables are now empty and ready for fresh testing.")

    except Exception as e:
        session.rollback()
        print(f"\n❌ Error cleaning database: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    print("=" * 60)
    print("DATABASE CLEANUP SCRIPT")
    print("=" * 60)
    print("\n⚠️  WARNING: This will delete ALL data from the database!")
    print("   Use only in development/staging environments.\n")

    response = input("Are you sure you want to continue? (yes/no): ")
    if response.lower() != "yes":
        print("❌ Cancelled.")
        sys.exit(0)

    clean_database()
