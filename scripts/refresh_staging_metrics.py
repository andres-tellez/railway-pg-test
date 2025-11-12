#!/usr/bin/env python3
"""
Refresh materialized views in staging environment.

Usage:
    python scripts/refresh_staging_metrics.py
    
Or set STAGING_DATABASE_URL environment variable:
    $env:STAGING_DATABASE_URL="postgresql://..."; python scripts/refresh_staging_metrics.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment
env_staging = Path(".env.staging")
if env_staging.exists():
    load_dotenv(env_staging, override=False)
    print(f"✅ Loaded .env.staging")

# Get staging database URL
staging_db_url = os.getenv("STAGING_DATABASE_URL") or os.getenv("DATABASE_URL")

if not staging_db_url:
    print("❌ STAGING_DATABASE_URL or DATABASE_URL not set")
    print("   Set STAGING_DATABASE_URL for staging database")
    sys.exit(1)

print("=" * 60)
print("🔄 Refreshing Staging Materialized Views")
print("=" * 60)
print(f"Database: {staging_db_url[:50]}...")

try:
    engine = create_engine(staging_db_url, echo=False)
    conn = engine.connect()
    
    print("\n1. Checking if views exist...")
    result = conn.execute(text("""
        SELECT matviewname 
        FROM pg_matviews 
        WHERE matviewname IN ('mv_athlete_metrics', 'mv_longest_runs')
    """))
    views = [row[0] for row in result.fetchall()]
    print(f"   Found views: {views}")
    
    if 'mv_athlete_metrics' not in views:
        print("   ⚠️  mv_athlete_metrics does not exist")
    if 'mv_longest_runs' not in views:
        print("   ⚠️  mv_longest_runs does not exist")
    
    print("\n2. Refreshing mv_athlete_metrics...")
    conn.execute(text("REFRESH MATERIALIZED VIEW mv_athlete_metrics"))
    conn.commit()
    print("   ✅ Refreshed")
    
    print("\n3. Refreshing mv_longest_runs...")
    conn.execute(text("REFRESH MATERIALIZED VIEW mv_longest_runs"))
    conn.commit()
    print("   ✅ Refreshed")
    
    print("\n4. Checking data for staging athlete_id...")
    # Check what athlete_ids exist in staging
    result = conn.execute(text("SELECT DISTINCT athlete_id FROM mv_athlete_metrics LIMIT 5"))
    athlete_ids = [row[0] for row in result.fetchall()]
    print(f"   Athlete IDs in mv_athlete_metrics: {athlete_ids}")
    
    result = conn.execute(text("SELECT DISTINCT athlete_id FROM activities LIMIT 5"))
    activity_athlete_ids = [row[0] for row in result.fetchall()]
    print(f"   Athlete IDs in activities: {activity_athlete_ids}")
    
    print("\n" + "=" * 60)
    print("✅ Staging materialized views refreshed!")
    print("=" * 60)
    
    conn.close()
    engine.dispose()
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

