#!/usr/bin/env python3
"""
check_webhook_health.py

Quick health check for webhook processing.
Run this daily to ensure webhooks are working properly.

Usage:
    python -m src.scripts.check_webhook_health
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta
from sqlalchemy import text

# Load environment variables
env_local_path = Path(".env.local")
if env_local_path.exists():
    load_dotenv(".env.local")
else:
    load_dotenv(".env.staging")

from src.db.db_session import get_session


def check_webhook_health():
    """Check webhook health and report any issues"""

    session = get_session()

    try:
        print("=" * 60)
        print("WEBHOOK HEALTH CHECK")
        print("=" * 60)
        print(f"Timestamp: {datetime.utcnow().isoformat()}")
        print()

        # Check 1: Overall stats
        print("[1] Overall Statistics")
        print("-" * 60)

        stats = session.execute(text("""
            SELECT
                status,
                COUNT(*) as count
            FROM webhook_events
            GROUP BY status
            ORDER BY status
        """)).fetchall()

        if not stats:
            print("[WARN] No webhook events found in database!")
            print("   - Check if webhook subscription is active")
            print("   - Check if Strava is sending events")
        else:
            for row in stats:
                status_emoji = {
                    'completed': '[OK]',
                    'failed': '[FAIL]',
                    'pending': '[WAIT]',
                    'ignored': '[SKIP]',
                    'processing': '[PROC]'
                }.get(row.status, '[?]')
                print(f"   {status_emoji} {row.status:12s}: {row.count:4d} events")

        print()

        # Check 2: Recent failures (last 24 hours)
        print("[2] Recent Failures (Last 24 Hours)")
        print("-" * 60)

        failures = session.execute(text("""
            SELECT
                id,
                object_type,
                object_id,
                error_message,
                retry_count,
                received_at
            FROM webhook_events
            WHERE status = 'failed'
              AND received_at > NOW() - INTERVAL '24 hours'
            ORDER BY received_at DESC
            LIMIT 10
        """)).fetchall()

        if not failures:
            print("   [OK] No failures in last 24 hours")
        else:
            print(f"   [FAIL] {len(failures)} failures found:")
            for f in failures:
                print(f"      Event #{f.id}: {f.object_type} {f.object_id}")
                print(f"         Error: {f.error_message}")
                print(f"         Retries: {f.retry_count}")
                print(f"         Time: {f.received_at}")
                print()

        print()

        # Check 3: Pending events (stuck?)
        print("[3] Pending Events (Possibly Stuck)")
        print("-" * 60)

        pending = session.execute(text("""
            SELECT
                id,
                object_type,
                object_id,
                received_at,
                EXTRACT(EPOCH FROM (NOW() - received_at))/60 as age_minutes
            FROM webhook_events
            WHERE status = 'pending'
            ORDER BY received_at
            LIMIT 10
        """)).fetchall()

        if not pending:
            print("   [OK] No pending events")
        else:
            stuck = [p for p in pending if p.age_minutes > 5]
            if stuck:
                print(f"   [WARN] {len(stuck)} events stuck in pending state:")
                for p in stuck:
                    print(f"      Event #{p.id}: {p.object_type} {p.object_id}")
                    print(f"         Age: {int(p.age_minutes)} minutes")
            else:
                print(f"   [OK] {len(pending)} pending events (all recent)")

        print()

        # Check 4: Recent activity (last hour)
        print("[4] Recent Activity (Last Hour)")
        print("-" * 60)

        recent = session.execute(text("""
            SELECT COUNT(*) as count
            FROM webhook_events
            WHERE received_at > NOW() - INTERVAL '1 hour'
        """)).fetchone()

        if recent.count == 0:
            print("   [WARN] No webhook events in last hour")
            print("   - This might be normal if no runs were recorded")
            print("   - Check Railway logs for incoming webhook POSTs")
        else:
            print(f"   [OK] {recent.count} events received in last hour")

        print()

        # Check 5: Success rate (last 7 days)
        print("[5] Success Rate (Last 7 Days)")
        print("-" * 60)

        success_rate = session.execute(text("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
            FROM webhook_events
            WHERE received_at > NOW() - INTERVAL '7 days'
              AND status IN ('completed', 'failed')
        """)).fetchone()

        if success_rate.total == 0:
            print("   [WARN] No events to calculate success rate")
        else:
            rate = (success_rate.completed / success_rate.total) * 100

            if rate >= 95:
                print(f"   [OK] Success rate: {rate:.1f}% ({success_rate.completed}/{success_rate.total})")
            elif rate >= 80:
                print(f"   [WARN] Success rate: {rate:.1f}% ({success_rate.completed}/{success_rate.total})")
            else:
                print(f"   [FAIL] Success rate: {rate:.1f}% ({success_rate.completed}/{success_rate.total})")
                print("      Consider investigating failures!")

        print()
        print("=" * 60)
        print()

        # Summary recommendation
        failed_count = sum(row.count for row in stats if row.status == 'failed') if stats else 0
        pending_count = sum(row.count for row in stats if row.status == 'pending') if stats else 0

        if not stats:
            print("[ACTION REQUIRED] No webhook events found!")
            print("   -> Verify webhook subscription is active")
            return False
        elif failed_count > 10:
            print("[ACTION RECOMMENDED] Multiple failures detected")
            print("   -> Check Railway logs for errors")
            print("   -> Verify Strava tokens are valid")
            return False
        elif len([p for p in pending if p.age_minutes > 5]) > 0 if pending else False:
            print("[ACTION RECOMMENDED] Events stuck in pending")
            print("   -> Check if background processing is working")
            return False
        else:
            print("[SUCCESS] Webhook system is healthy!")
            return True

    except Exception as e:
        print(f"[ERROR] Health check failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        session.close()


if __name__ == "__main__":
    import sys
    success = check_webhook_health()
    sys.exit(0 if success else 1)
