"""Investigate why some activities have NULL values in local database."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment
load_dotenv(Path('.env.local'), override=False)

prod_url = os.getenv('PROD_DATABASE_URL')
local_url = os.getenv('DATABASE_URL')

if not prod_url or not local_url:
    print("❌ Database URLs not set")
    sys.exit(1)

prod_engine = create_engine(prod_url)
local_engine = create_engine(local_url)

prod_conn = prod_engine.connect()
local_conn = local_engine.connect()

# Get production activity IDs
result = prod_conn.execute(
    text('SELECT activity_id FROM activities WHERE athlete_id = 347085 ORDER BY activity_id')
)
prod_ids = {r[0] for r in result}

# Get local activities
result = local_conn.execute(
    text('SELECT activity_id, average_speed, max_speed, suffer_score, average_heartrate, max_heartrate, calories FROM activities WHERE athlete_id = 347085 ORDER BY activity_id')
)
local_data = [(r[0], r[1], r[2], r[3], r[4], r[5], r[6]) for r in result]

print(f"Production activity IDs: {len(prod_ids)}")
print(f"Local activity IDs: {len(local_data)}")

# Find activities with NULLs
null_activities = [a for a in local_data if a[1] is None or a[2] is None or a[3] is None]
print(f"\nActivities with NULLs in local: {len(null_activities)}")

null_ids = {a[0] for a in null_activities}
in_prod = null_ids & prod_ids
not_in_prod = null_ids - prod_ids

print(f"\nNULL activities that ARE in production: {len(in_prod)}")
if in_prod:
    print(f"  Activity IDs: {sorted(list(in_prod))[:10]}")
    # Check production values for these
    for act_id in sorted(list(in_prod))[:5]:
        result = prod_conn.execute(
            text('SELECT activity_id, average_speed, max_speed, suffer_score, average_heartrate, max_heartrate, calories FROM activities WHERE activity_id = :id'),
            {"id": act_id}
        )
        prod_row = result.fetchone()
        if prod_row:
            print(f"    Production Activity {prod_row[0]}: speed={prod_row[1]}, max_speed={prod_row[2]}, suffer={prod_row[3]}, hr={prod_row[4]}, max_hr={prod_row[5]}, calories={prod_row[6]}")

print(f"\nNULL activities that are NOT in production: {len(not_in_prod)}")
if not_in_prod:
    print(f"  These are extra local activities: {sorted(list(not_in_prod))[:10]}")
    # Check when these were created
    for act_id in sorted(list(not_in_prod))[:5]:
        result = local_conn.execute(
            text('SELECT activity_id, start_date, name FROM activities WHERE activity_id = :id'),
            {"id": act_id}
        )
        local_row = result.fetchone()
        if local_row:
            print(f"    Local Activity {local_row[0]}: date={local_row[1]}, name={local_row[2]}")

# Check if production has any NULLs
print("\n\nChecking production for NULLs:")
result = prod_conn.execute(
    text('SELECT COUNT(*) FROM activities WHERE athlete_id = 347085 AND (average_speed IS NULL OR max_speed IS NULL OR suffer_score IS NULL)')
)
prod_null_count = result.fetchone()[0]
print(f"  Production activities with NULLs: {prod_null_count}")

# Check specific activities that should have been migrated
print("\n\nComparing specific activities:")
sample_prod_ids = sorted(list(prod_ids))[:5]
for act_id in sample_prod_ids:
    result = prod_conn.execute(
        text('SELECT activity_id, average_speed, max_speed, suffer_score FROM activities WHERE activity_id = :id'),
        {"id": act_id}
    )
    prod_row = result.fetchone()
    
    result = local_conn.execute(
        text('SELECT activity_id, average_speed, max_speed, suffer_score FROM activities WHERE activity_id = :id'),
        {"id": act_id}
    )
    local_row = result.fetchone()
    
    if prod_row and local_row:
        match = (prod_row[1] == local_row[1] and prod_row[2] == local_row[2] and prod_row[3] == local_row[3])
        print(f"  Activity {act_id}: {'✅ Match' if match else '❌ Mismatch'}")
        print(f"    Prod: speed={prod_row[1]}, max_speed={prod_row[2]}, suffer={prod_row[3]}")
        print(f"    Local: speed={local_row[1]}, max_speed={local_row[2]}, suffer={local_row[3]}")

prod_conn.close()
local_conn.close()

