"""Remove activities with NULL values that aren't in production."""

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
    text('SELECT activity_id FROM activities WHERE athlete_id = 347085')
)
prod_ids = {r[0] for r in result}

# Find local activities with NULLs that aren't in production
result = local_conn.execute(
    text("""
        SELECT activity_id 
        FROM activities 
        WHERE athlete_id = 347085 
        AND (average_speed IS NULL OR max_speed IS NULL OR suffer_score IS NULL)
    """)
)
null_activity_ids = [r[0] for r in result]

# Filter to only those not in production
to_delete = [aid for aid in null_activity_ids if aid not in prod_ids]

if not to_delete:
    print("✅ No NULL activities to clean up")
    prod_conn.close()
    local_conn.close()
    sys.exit(0)

print(f"Found {len(to_delete)} activities with NULLs that aren't in production")
print(f"Activity IDs to delete: {sorted(to_delete)}")

# Show details before deletion
print("\nActivities to be deleted:")
for act_id in sorted(to_delete)[:10]:
    result = local_conn.execute(
        text('SELECT activity_id, start_date, name, conv_distance FROM activities WHERE activity_id = :id'),
        {"id": act_id}
    )
    row = result.fetchone()
    if row:
        print(f"  Activity {row[0]}: {row[1]} - {row[2]} ({row[3]} miles)")

response = input(f"\nDelete {len(to_delete)} activities? (yes/no): ")
if response.lower() != 'yes':
    print("Cancelled")
    prod_conn.close()
    local_conn.close()
    sys.exit(0)

# Delete splits first (foreign key constraint)
print("\nDeleting splits...")
for act_id in to_delete:
    local_conn.execute(
        text('DELETE FROM splits WHERE activity_id = :id'),
        {"id": act_id}
    )
local_conn.commit()

# Delete activities
print("Deleting activities...")
for act_id in to_delete:
    local_conn.execute(
        text('DELETE FROM activities WHERE activity_id = :id'),
        {"id": act_id}
    )
local_conn.commit()

print(f"\n✅ Deleted {len(to_delete)} activities")

# Verify
result = local_conn.execute(
    text('SELECT COUNT(*) FROM activities WHERE athlete_id = 347085')
)
remaining = result.fetchone()[0]
print(f"Remaining activities for athlete 347085: {remaining}")

prod_conn.close()
local_conn.close()

