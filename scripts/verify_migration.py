#!/usr/bin/env python3
"""
Quick verification script to check migration status.

Compares record counts between production and local databases.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


def get_table_counts(session, table_name):
    """Get count of records in a table."""
    try:
        result = session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        return result.fetchone()[0]
    except Exception as e:
        return f"Error: {e}"


def main():
    """Main verification function."""
    # Load environment
    env_local = Path(".env.local")
    env_prod = Path(".env.prod")

    if env_local.exists():
        load_dotenv(env_local, override=False)

    if env_prod.exists():
        load_dotenv(env_prod, override=False)

    prod_db_url = os.getenv("PROD_DATABASE_URL") or os.getenv("DATABASE_URL")
    local_db_url = os.getenv("DATABASE_URL")

    if not prod_db_url or not local_db_url:
        print("❌ Database URLs not set")
        return 1

    print("=" * 60)
    print("🔍 Migration Verification")
    print("=" * 60)

    try:
        prod_engine = create_engine(prod_db_url, echo=False)
        local_engine = create_engine(local_db_url, echo=False)
        prod_session = sessionmaker(bind=prod_engine)()
        local_session = sessionmaker(bind=local_engine)()

        tables = [
            "user_identity",
            "user_athletes",
            "user_profile",
            "activities",
            "splits",
            "plans",
            "plan_workouts",
            "weekly_metrics",
            "weekly_decision_log",
            "strava_sync_status",
            "conversations",
        ]

        print(f"\n{'Table':<25} {'Production':<15} {'Local':<15} {'Status'}")
        print("-" * 70)

        for table in tables:
            prod_count = get_table_counts(prod_session, table)
            local_count = get_table_counts(local_session, table)

            if isinstance(prod_count, str) or isinstance(local_count, str):
                status = "⚠️  Error"
            elif prod_count == local_count:
                status = "✅ Match"
            elif local_count > prod_count:
                status = "⚠️  More in local"
            else:
                status = "❌ Missing data"

            print(f"{table:<25} {str(prod_count):<15} {str(local_count):<15} {status}")

        # Check user/athlete mapping
        print("\n" + "=" * 60)
        print("📊 User/Athlete Mapping")
        print("=" * 60)

        prod_user = prod_session.execute(
            text("SELECT user_id, athlete_id FROM user_athletes LIMIT 1")
        ).fetchone()

        local_user = local_session.execute(
            text("SELECT user_id, athlete_id FROM user_athletes LIMIT 1")
        ).fetchone()

        if prod_user and local_user:
            print(f"Production: user_id={prod_user[0]}, athlete_id={prod_user[1]}")
            print(f"Local:      user_id={local_user[0]}, athlete_id={local_user[1]}")
        else:
            print("⚠️  Could not retrieve user/athlete info")

        prod_session.close()
        local_session.close()
        prod_engine.dispose()
        local_engine.dispose()

        print("\n✅ Verification complete")
        return 0

    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
