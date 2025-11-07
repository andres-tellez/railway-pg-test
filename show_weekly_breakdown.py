"""
Show week-by-week breakdown of mileage.
"""

import sys
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(".env.local")
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)

sys.path.insert(0, "src")

from src.db.db_session import get_db
from src.services.training_plan.data_collection_service import DataCollectionService
from src.services.training_plan.calculations.week_utils import (
    get_complete_weeks,
    calculate_week_mileage,
    format_week_range,
)

USER_ID = "ddc21831-1b01-4cfc-82db-7632ab2cfba1"

db = next(get_db())

try:
    # Fetch data
    raw_data = DataCollectionService.collect_all_data(
        session=db, user_id=USER_ID, plan_request={}, activity_weeks=12
    )

    # Get complete weeks
    weekly_data = get_complete_weeks(raw_data["strava_activities"], max_weeks=12)

    print("\n" + "=" * 80)
    print("  YOUR WEEKLY MILEAGE BREAKDOWN (Last 12 Complete Weeks)")
    print("=" * 80)

    # Sort by week (most recent first)
    sorted_weeks = sorted(weekly_data.items(), reverse=True)

    prev_mileage = None
    for i, (week_id, activities) in enumerate(sorted_weeks, 1):
        week_mileage = calculate_week_mileage(activities)
        week_range = format_week_range(week_id)
        num_runs = len(activities)

        # Calculate change from previous week
        change_str = ""
        if prev_mileage is not None and prev_mileage > 0:
            change_percent = ((week_mileage - prev_mileage) / prev_mileage) * 100
            if change_percent > 0:
                change_str = f" (+{change_percent:.1f}%)"
            else:
                change_str = f" ({change_percent:.1f}%)"
        elif prev_mileage == 0 and week_mileage > 0:
            change_str = " (from 0 miles)"

        print(f"\n{i}. Week {week_id} ({week_range})")
        print(f"   Mileage: {week_mileage} miles{change_str}")
        print(f"   Runs: {num_runs}")

        # Show individual runs
        for activity in activities:
            date = activity.get("date", "N/A")
            distance = activity.get("distance", 0)
            print(f"     - {date}: {distance:.1f} miles")

        prev_mileage = week_mileage

    print("\n" + "=" * 80)

    # Calculate overall stats
    all_mileages = [
        calculate_week_mileage(activities) for activities in weekly_data.values()
    ]
    avg_mileage = sum(all_mileages) / len(all_mileages) if all_mileages else 0
    max_mileage = max(all_mileages) if all_mileages else 0
    min_mileage = min(all_mileages) if all_mileages else 0

    print(f"\nOVERALL STATS:")
    print(f"  Average: {avg_mileage:.1f} miles/week")
    print(f"  Max: {max_mileage:.1f} miles/week")
    print(f"  Min: {min_mileage:.1f} miles/week")
    print(f"  Total Weeks: {len(weekly_data)}")

finally:
    db.close()
