#!/usr/bin/env python3
"""
Run the Strava Premium Status migration SQL script.

This script executes the SQL migration to add has_strava_premium and
strava_premium_checked_at columns to the user_athletes table.

Usage:
    python scripts/run_migration_strava_premium.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Load environment
env_local = Path(".env.local")
if env_local.exists():
    load_dotenv(env_local, override=False)
else:
    load_dotenv(override=False)

database_url = os.getenv("DATABASE_URL")
if not database_url:
    print("❌ DATABASE_URL not set")
    print("   Please set DATABASE_URL in .env.local or environment variables")
    sys.exit(1)

# Read the SQL migration file
migration_file = project_root / "scripts" / "migrate_add_strava_premium_status.sql"
if not migration_file.exists():
    print(f"❌ Migration file not found: {migration_file}")
    sys.exit(1)

print("=" * 60)
print("🔄 Running Strava Premium Status Migration")
print("=" * 60)
print(f"Database: {database_url.split('@')[1] if '@' in database_url else 'hidden'}")
print(f"Migration file: {migration_file.name}")
print()

try:
    # Read SQL content
    with open(migration_file, "r", encoding="utf-8") as f:
        sql_content = f.read()

    # Create engine and execute
    engine = create_engine(database_url)
    conn = engine.connect()

    print("📋 Executing migration SQL...")
    print("-" * 60)

    # Execute the SQL (it contains DO blocks which are safe to run multiple times)
    conn.execute(text(sql_content))
    conn.commit()

    print("-" * 60)
    print("✅ Migration executed successfully!")

    # Verify the columns were added
    print("\n🔍 Verifying columns exist...")
    result = conn.execute(
        text(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'user_athletes'
            AND column_name IN ('has_strava_premium', 'strava_premium_checked_at')
            ORDER BY column_name
        """
        )
    )

    columns = result.fetchall()
    if len(columns) == 2:
        print("✅ Both columns found:")
        for col_name, data_type, is_nullable in columns:
            print(f"   - {col_name}: {data_type} (nullable: {is_nullable})")
    elif len(columns) == 1:
        print("⚠️  Only one column found:")
        for col_name, data_type, is_nullable in columns:
            print(f"   - {col_name}: {data_type} (nullable: {is_nullable})")
        print("   Check the migration output above for errors")
    else:
        print("⚠️  Columns not found - check the migration output above")

    conn.close()
    engine.dispose()

    print("\n" + "=" * 60)
    print("✅ Migration complete!")
    print("=" * 60)

except Exception as e:
    print(f"\n❌ Error running migration: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
