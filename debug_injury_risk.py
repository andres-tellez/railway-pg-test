"""
Debug injury risk calculation.
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
)

USER_ID = "ddc21831-1b01-4cfc-82db-7632ab2cfba1"

db = next(get_db())

try:
    raw_data = DataCollectionService.collect_all_data(
        session=db, user_id=USER_ID, plan_request={}, activity_weeks=12
    )

    weekly_data = get_complete_weeks(raw_data["strava_activities"], max_weeks=12)

    # Calculate weekly mileages in chronological order
    weekly_mileages = []
    for week_id in sorted(weekly_data.keys()):
        week_mileage = calculate_week_mileage(weekly_data[week_id])
        weekly_mileages.append((week_id, week_mileage))

    print("All 12 weeks (oldest to newest):")
    for i, (week_id, mileage) in enumerate(weekly_mileages, 1):
        print(f"  {i}. {week_id}: {mileage} miles")

    # Get last 6 weeks
    recent_mileages = [m[1] for m in weekly_mileages[-6:]]
    recent_weeks = [m[0] for m in weekly_mileages[-6:]]

    print("\nLast 6 weeks (for injury risk analysis):")
    for i, (week_id, mileage) in enumerate(zip(recent_weeks, recent_mileages), 1):
        print(f"  {i}. {week_id}: {mileage} miles")

    print("\nWeek-to-week changes:")
    MIN_BASE_MILEAGE = 5.0
    for i in range(1, len(recent_mileages)):
        prev_week = recent_mileages[i - 1]
        current_week = recent_mileages[i]

        if prev_week < MIN_BASE_MILEAGE:
            print(
                f"  {recent_weeks[i-1]} ({prev_week}) -> {recent_weeks[i]} ({current_week}): SKIPPED (prev < 5)"
            )
            continue

        if current_week < MIN_BASE_MILEAGE:
            print(
                f"  {recent_weeks[i-1]} ({prev_week}) -> {recent_weeks[i]} ({current_week}): SKIPPED (current < 5)"
            )
            continue

        increase_percent = ((current_week - prev_week) / prev_week) * 100
        flag = ""
        if increase_percent > 20:
            flag = " *** FLAGGED (>20%)"
        elif increase_percent > 15:
            flag = " ** WARNING (>15%)"

        print(
            f"  {recent_weeks[i-1]} ({prev_week}) -> {recent_weeks[i]} ({current_week}): {increase_percent:+.1f}%{flag}"
        )

finally:
    db.close()
