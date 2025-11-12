"""Compare staging and production metrics data to find discrepancies."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import json

# Load environment
load_dotenv(Path('.env.local'), override=False)

prod_url = os.getenv('PROD_DATABASE_URL')
staging_url = os.getenv('STAGING_DATABASE_URL')

if not prod_url:
    print("❌ PROD_DATABASE_URL not set")
    sys.exit(1)

if not staging_url:
    print("❌ STAGING_DATABASE_URL not set")
    print("   Set it with: $env:STAGING_DATABASE_URL='postgresql://...'")
    sys.exit(1)

prod_engine = create_engine(prod_url)
staging_engine = create_engine(staging_url)

prod_conn = prod_engine.connect()
staging_conn = staging_engine.connect()

# Find athlete_id 347085 in both environments
athlete_id = 347085

print("=" * 60)
print(f"Comparing data for athlete_id {athlete_id}")
print("=" * 60)

# 1. Check activities count
print("\n1. ACTIVITIES:")
result = prod_conn.execute(
    text('SELECT COUNT(*) FROM activities WHERE athlete_id = :id'),
    {"id": athlete_id}
)
prod_activities = result.fetchone()[0]

result = staging_conn.execute(
    text('SELECT COUNT(*) FROM activities WHERE athlete_id = :id'),
    {"id": athlete_id}
)
staging_activities = result.fetchone()[0]

print(f"  Production: {prod_activities} activities")
print(f"  Staging: {staging_activities} activities")
if prod_activities != staging_activities:
    print(f"  ⚠️  MISMATCH: {abs(prod_activities - staging_activities)} activities difference")

# 2. Check materialized view data
print("\n2. MATERIALIZED VIEW (mv_athlete_metrics):")
result = prod_conn.execute(
    text('SELECT * FROM mv_athlete_metrics WHERE athlete_id = :id'),
    {"id": athlete_id}
)
prod_mv = result.fetchone()

result = staging_conn.execute(
    text('SELECT * FROM mv_athlete_metrics WHERE athlete_id = :id'),
    {"id": athlete_id}
)
staging_mv = result.fetchone()

if prod_mv and staging_mv:
    print("\n  Dashboard Metrics:")
    print(f"    Production - Current Distance: {prod_mv.current_distance}, Previous: {prod_mv.previous_distance}")
    print(f"    Staging - Current Distance: {staging_mv.current_distance}, Previous: {staging_mv.previous_distance}")
    
    print(f"\n    Production - Current Runs: {prod_mv.current_runs}, Previous: {prod_mv.previous_runs}")
    print(f"    Staging - Current Runs: {staging_mv.current_runs}, Previous: {staging_mv.previous_runs}")
    
    print(f"\n    Production - Current Pace: {prod_mv.current_avg_speed}, Previous: {prod_mv.previous_avg_speed}")
    print(f"    Staging - Current Pace: {staging_mv.current_avg_speed}, Previous: {staging_mv.previous_avg_speed}")
    
    # Compare weekly_data
    prod_weekly = prod_mv.weekly_data if prod_mv.weekly_data else []
    staging_weekly = staging_mv.weekly_data if staging_mv.weekly_data else []
    
    print(f"\n  Weekly Data:")
    print(f"    Production: {len(prod_weekly)} weeks")
    print(f"    Staging: {len(staging_weekly)} weeks")
    
    if len(prod_weekly) != len(staging_weekly):
        print(f"    ⚠️  MISMATCH: Different number of weeks")
    
    # Compare first few weeks
    print("\n  First 3 weeks comparison:")
    for i in range(min(3, len(prod_weekly), len(staging_weekly))):
        prod_week = prod_weekly[i]
        staging_week = staging_weekly[i] if i < len(staging_weekly) else None
        
        prod_dist = prod_week.get('distance', 0) if isinstance(prod_week, dict) else 0
        staging_dist = staging_week.get('distance', 0) if staging_week and isinstance(staging_week, dict) else 0
        
        prod_week_str = prod_week.get('week', 'N/A') if isinstance(prod_week, dict) else 'N/A'
        staging_week_str = staging_week.get('week', 'N/A') if staging_week and isinstance(staging_week, dict) else 'N/A'
        
        match = "✅" if abs(prod_dist - staging_dist) < 0.01 else "❌"
        print(f"    Week {i+1}: {match}")
        print(f"      Production: {prod_week_str} - {prod_dist} miles, {prod_week.get('runs', 0) if isinstance(prod_week, dict) else 0} runs")
        if staging_week:
            print(f"      Staging: {staging_week_str} - {staging_dist} miles, {staging_week.get('runs', 0) if isinstance(staging_week, dict) else 0} runs")
        else:
            print(f"      Staging: No data")
            
elif prod_mv and not staging_mv:
    print("  ⚠️  Production has data, staging does not")
elif staging_mv and not prod_mv:
    print("  ⚠️  Staging has data, production does not")
else:
    print("  ⚠️  No data in either environment")

# 3. Check actual activity data for recent weeks
print("\n3. RECENT ACTIVITIES (last 5):")
result = prod_conn.execute(
    text("""
        SELECT activity_id, start_date, conv_distance, average_speed
        FROM activities 
        WHERE athlete_id = :id 
        ORDER BY start_date DESC 
        LIMIT 5
    """),
    {"id": athlete_id}
)
prod_recent = result.fetchall()

result = staging_conn.execute(
    text("""
        SELECT activity_id, start_date, conv_distance, average_speed
        FROM activities 
        WHERE athlete_id = :id 
        ORDER BY start_date DESC 
        LIMIT 5
    """),
    {"id": athlete_id}
)
staging_recent = result.fetchall()

print("  Production recent activities:")
for act in prod_recent:
    print(f"    {act[0]}: {act[1]} - {act[2]} miles, speed={act[3]}")

print("\n  Staging recent activities:")
for act in staging_recent:
    print(f"    {act[0]}: {act[1]} - {act[2]} miles, speed={act[3]}")

# 4. Check if materialized view needs refresh
print("\n4. MATERIALIZED VIEW REFRESH STATUS:")
print("  ⚠️  If data differs, staging materialized view may need refresh")
print("  Run: python scripts/refresh_staging_metrics.py")

prod_conn.close()
staging_conn.close()

