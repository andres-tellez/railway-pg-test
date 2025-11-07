"""
Quick test of Layer 2 with your real data.
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
env_path = Path(".env.local")
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)

sys.path.insert(0, "src")

from src.db.db_session import get_db
from src.services.training_plan.data_collection_service import DataCollectionService
from src.services.training_plan.insights_calculation_service import (
    InsightsCalculationService,
)

# Your user ID
USER_ID = "ddc21831-1b01-4cfc-82db-7632ab2cfba1"

print("=" * 80)
print("  LAYER 2 TEST WITH YOUR DATA")
print("=" * 80)

db = next(get_db())

try:
    # Fetch data for last 12 weeks
    print(f"\n[1] Fetching data for last 12 weeks...")
    raw_data = DataCollectionService.collect_all_data(
        session=db,
        user_id=USER_ID,
        plan_request={
            "race_date": "2026-04-15",
            "primary_goal": "Just Finish",
            "marathon_experience": "First",
        },
        activity_weeks=12,
    )

    print(f"    Activities found: {len(raw_data['strava_activities'])}")

    # Calculate insights
    print(f"\n[2] Calculating insights...")
    insights = InsightsCalculationService.calculate_all_insights(raw_data)

    # Display results
    print("\n" + "=" * 80)
    print("  RESULTS")
    print("=" * 80)

    fitness = insights["current_fitness"]
    print(f"\n[CURRENT FITNESS]")
    print(f"  Weekly Mileage: {fitness['weekly_mileage']} miles (last complete week)")
    print(f"  Longest Run: {fitness['longest_run']} miles")
    print(f"  Average Pace: {fitness['average_pace']}")
    print(f"  Fitness Trend: {fitness['fitness_trend']}")

    metadata = insights["metadata"]
    print(f"\n[DATA QUALITY]")
    print(f"  Activities Analyzed: {metadata['activities_analyzed']}")
    print(f"  Weeks Analyzed: {metadata['weeks_analyzed']}")
    print(f"  Data Quality: {metadata['data_quality']}")

    recs = insights["recommendations"]
    print(f"\n[TRAINING PLAN RECOMMENDATIONS]")
    print(
        f"  Starting Mileage: {recs['starting_mileage']['weekly_mileage']} miles/week"
    )
    print(
        f"  Ready for Marathon: {recs['starting_mileage'].get('ready_for_marathon', 'N/A')}"
    )
    print(f"  Progression Rate: {recs['progression_rate']['rate_percent']}% per week")
    print(
        f"  Training Frequency: {recs['training_frequency']['runs_per_week']} runs/week"
    )
    print(f"  Long Run: {recs['long_run_distance']['distance']} miles")
    print(f"  Focus Areas: {', '.join(recs['focus_areas'])}")

    # Save full results
    output_file = f"my_insights_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(insights, f, indent=2)

    print(f"\n[SAVED] Full insights saved to: {output_file}")
    print("\n" + "=" * 80)

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback

    traceback.print_exc()

finally:
    db.close()
