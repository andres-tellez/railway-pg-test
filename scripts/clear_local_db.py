#!/usr/bin/env python3
"""
Clear all data from local database.

WARNING: This will delete ALL data from your local database!
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment
env_local = Path(".env.local")
if env_local.exists():
    load_dotenv(env_local, override=False)

database_url = os.getenv("DATABASE_URL")
if not database_url:
    print("❌ DATABASE_URL not set")
    sys.exit(1)

print("=" * 60)
print("⚠️  WARNING: This will DELETE ALL DATA from local database!")
print("=" * 60)
response = input("Are you sure? Type 'yes' to continue: ")
if response.lower() != "yes":
    print("Cancelled.")
    sys.exit(0)

try:
    engine = create_engine(database_url)
    conn = engine.connect()

    print("\n📋 Getting list of tables...")
    result = conn.execute(
        text(
            """
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename
    """
        )
    )
    tables = [row[0] for row in result.fetchall()]
    print(f"Found {len(tables)} tables")

    print("\n🗑️  Deleting data from all tables...")

    # Disable foreign key checks temporarily
    conn.execute(text("SET session_replication_role = replica"))

    deleted_count = 0
    for table in tables:
        try:
            conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
            print(f"  ✅ {table}")
            deleted_count += 1
        except Exception as e:
            print(f"  ⚠️  {table}: {e}")

    # Re-enable foreign key checks
    conn.execute(text("SET session_replication_role = DEFAULT"))
    conn.commit()

    print(f"\n✅ Deleted data from {deleted_count} tables")
    print("✅ Local database is now empty")

    conn.close()
    engine.dispose()

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
