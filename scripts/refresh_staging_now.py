#!/usr/bin/env python3
"""
Refresh staging materialized views using provided database URL.
"""

import sys
from sqlalchemy import create_engine, text

staging_url = "postgresql://postgres:pgWuvwQULlbaPfHfbsOHhtiNBEyXBSZD@postgres-517f41c4.railway.internal:5432/railway"

print("=" * 60)
print("🔄 Refreshing Staging Materialized Views")
print("=" * 60)

try:
    engine = create_engine(staging_url, echo=False)
    conn = engine.connect()
    
    print("\n1. Refreshing mv_athlete_metrics...")
    conn.execute(text("REFRESH MATERIALIZED VIEW mv_athlete_metrics"))
    conn.commit()
    print("   ✅ Refreshed")
    
    print("\n2. Refreshing mv_longest_runs...")
    conn.execute(text("REFRESH MATERIALIZED VIEW mv_longest_runs"))
    conn.commit()
    print("   ✅ Refreshed")
    
    print("\n3. Verifying...")
    result = conn.execute(text("SELECT COUNT(*) FROM mv_athlete_metrics"))
    count = result.fetchone()[0]
    print(f"   Rows in mv_athlete_metrics: {count}")
    
    print("\n" + "=" * 60)
    print("✅ Staging materialized views refreshed!")
    print("=" * 60)
    
    conn.close()
    engine.dispose()
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\n⚠️  This might be an internal Railway URL that requires VPN/tunnel.")
    print("   Alternative: Use the admin endpoint:")
    print("   POST https://api.smartcoach.dev/admin/refresh-metrics")
    import traceback
    traceback.print_exc()
    sys.exit(1)

