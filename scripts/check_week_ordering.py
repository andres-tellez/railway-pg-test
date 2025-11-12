"""Check week ordering in materialized view and after reordering."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from datetime import datetime
from src.utils.date_helpers import get_current_week_start

load_dotenv(Path(".env.local"), override=False)

local_url = os.getenv("DATABASE_URL")
if not local_url:
    print("❌ DATABASE_URL not set")
    sys.exit(1)

engine = create_engine(local_url)
conn = engine.connect()

# Get weekly data from materialized view
result = conn.execute(
    text("SELECT weekly_data FROM mv_athlete_metrics WHERE athlete_id = 347085")
)
row = result.fetchone()

if not row or not row[0]:
    print("❌ No weekly data found")
    sys.exit(1)

weekly_data = row[0]
current_week_start = get_current_week_start()
current_week_str = current_week_start.isoformat()

print("=" * 60)
print("Week Ordering Analysis")
print("=" * 60)
print(f"\nToday: {datetime.now().date()}")
print(f"Current week start: {current_week_start} ({current_week_str})")
print(f"\nWeekly data from materialized view (first 5):")
for i, week in enumerate(weekly_data[:5]):
    week_date = week.get("week", "N/A")
    if isinstance(week_date, str):
        week_date = week_date[:10]
    is_current = week_date == current_week_str
    print(
        f"  {i+1}. {week_date} - {week.get('distance', 0)} miles {'(CURRENT WEEK)' if is_current else ''}"
    )

# Simulate the reordering logic
print("\n" + "=" * 60)
print("After reordering (simulated):")
print("=" * 60)

if weekly_data and len(weekly_data) > 1:
    first_week_date = weekly_data[0]["week"]
    if isinstance(first_week_date, str):
        first_week_date = first_week_date[:10]

    if first_week_date == current_week_str:
        print(
            f"⚠️  First week ({first_week_date}) IS current week - would be moved to end"
        )
        reordered = weekly_data[1:] + [weekly_data[0]]
    else:
        print(f"✅ First week ({first_week_date}) is NOT current week - no reordering")
        reordered = weekly_data

    print("\nReordered data (first 5):")
    for i, week in enumerate(reordered[:5]):
        week_date = week.get("week", "N/A")
        if isinstance(week_date, str):
            week_date = week_date[:10]
        is_current = week_date == current_week_str
        position = (
            "LEFT" if i == 0 else "RIGHT" if i == len(reordered) - 1 else "MIDDLE"
        )
        print(
            f"  {i+1}. {week_date} - {week.get('distance', 0)} miles {'(CURRENT WEEK)' if is_current else ''} [{position}]"
        )

conn.close()
