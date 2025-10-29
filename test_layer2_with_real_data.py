"""
Test Layer 2 with real user data to validate calculations.

This script will:
1. Fetch YOUR real data from the database (Layer 1)
2. Calculate insights (Layer 2)
3. Display results in a readable format
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
    print("[OK] Loaded .env.local\n")
else:
    print("[WARNING] .env.local not found, using default environment\n")

# Add src to path
sys.path.insert(0, "src")

from src.db.db_session import get_db
from src.services.training_plan.data_collection_service import DataCollectionService
from src.services.training_plan.insights_calculation_service import (
    InsightsCalculationService,
)


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_subsection(title):
    """Print a formatted subsection header."""
    print(f"\n--- {title} ---")


def main():
    # Your user ID (we'll need to get this from the database)
    # For now, let's use a placeholder - we'll update this
    user_id = input("Enter your user_id (UUID): ").strip()

    if not user_id:
        print(" No user_id provided. Exiting.")
        return

    print(f"\n[*] Fetching data for user: {user_id}")

    # Get database session
    db = next(get_db())

    try:
        # ============================================================
        # LAYER 1: Data Collection
        # ============================================================
        print_section("LAYER 1: Data Collection")

        # Fetch data for last 4 weeks (1 month)
        raw_data = DataCollectionService.collect_all_data(
            session=db,
            user_id=user_id,
            plan_request={
                "race_date": "2026-04-15",
                "primary_goal": "Just Finish",
                "marathon_experience": "First",
            },
            activity_weeks=4,  # Last 4 weeks (1 month)
        )

        print(f"\n Data collected successfully!")
        print(f"   - Activities found: {len(raw_data['strava_activities'])}")
        print(f"   - Time period: Last 4 weeks")
        print(f"   - User profile: {raw_data['user_profile'].get('age_group', 'N/A')}")

        # Show raw activities
        print_subsection("Your Recent Activities (Last 4 Weeks)")
        if raw_data["strava_activities"]:
            for i, activity in enumerate(
                raw_data["strava_activities"][:10], 1
            ):  # Show first 10
                date = activity.get("date", "N/A")
                distance = activity.get("distance", 0)
                pace_seconds = (
                    activity.get("moving_time", 0) / distance if distance > 0 else 0
                )
                pace_minutes = int(pace_seconds // 60)
                pace_seconds_remainder = int(pace_seconds % 60)

                print(
                    f"   {i}. {date}: {distance:.1f} miles @ {pace_minutes}:{pace_seconds_remainder:02d}/mile"
                )

            if len(raw_data["strava_activities"]) > 10:
                print(
                    f"   ... and {len(raw_data['strava_activities']) - 10} more activities"
                )
        else:
            print("     No activities found in the last 4 weeks")

        # ============================================================
        # LAYER 2: Insights Calculation
        # ============================================================
        print_section("LAYER 2: Insights Calculation")

        insights = InsightsCalculationService.calculate_all_insights(raw_data)

        print("\n Insights calculated successfully!")

        # ------------------------------------------------------------
        # Current Fitness
        # ------------------------------------------------------------
        print_subsection("1. Current Fitness Metrics")
        fitness = insights["current_fitness"]
        print(f"    Weekly Mileage (last 7 days): {fitness['weekly_mileage']} miles")
        print(f"    Longest Run (last 4 weeks): {fitness['longest_run']} miles")
        print(f"     Average Pace (last 4 weeks): {fitness['average_pace']}")
        print(f"    Fitness Trend: {fitness['fitness_trend']}")

        # ------------------------------------------------------------
        # Training Patterns
        # ------------------------------------------------------------
        print_subsection("2. Training Pattern Analysis")
        patterns = insights["training_patterns"]
        print(f"    Consistency Score: {patterns['consistency_score']}/100")
        print(f"    Consistency Level: {patterns['consistency_level']}")
        print(f"    Training Frequency: {patterns['training_frequency']} runs/week")
        print(f"    Frequency Level: {patterns['frequency_level']}")
        print(f"    Volume Pattern: {patterns['volume_patterns']['pattern']}")
        print(f"    Volume Trend: {patterns['volume_patterns']['trend']}")
        print(f"    Training Regularity: {patterns['training_regularity']}")

        # ------------------------------------------------------------
        # Safety Assessment
        # ------------------------------------------------------------
        print_subsection("3. Safety Risk Assessment")
        safety = insights["safety_assessment"]
        print(f"     Overall Risk Level: {safety['overall_risk_level']}")
        print(
            f"    Injury Risk: {safety['injury_risk']['level']} (score: {safety['injury_risk']['score']})"
        )
        print(f"      Factors: {', '.join(safety['injury_risk']['factors'])}")
        print(
            f"    Overtraining Risk: {safety['overtraining_risk']['level']} (score: {safety['overtraining_risk']['score']})"
        )
        print(f"      Factors: {', '.join(safety['overtraining_risk']['factors'])}")
        print(
            f"    Progression Risk: {safety['progression_risk']['level']} (score: {safety['progression_risk']['score']})"
        )
        print(f"      Factors: {', '.join(safety['progression_risk']['factors'])}")

        print(f"\n    Safety Recommendations:")
        for rec in safety["safety_recommendations"]:
            print(f"       {rec}")

        # ------------------------------------------------------------
        # Training Recommendations
        # ------------------------------------------------------------
        print_subsection("4. Training Recommendations")
        recs = insights["recommendations"]
        print(
            f"    Starting Mileage: {recs['starting_mileage']['weekly_mileage']} miles/week"
        )
        print(f"      Confidence: {recs['starting_mileage']['confidence']}")
        print(f"      Rationale: {recs['starting_mileage']['rationale']}")

        print(
            f"\n    Progression Rate: {recs['progression_rate']['rate_percent']}% per week"
        )
        print(f"      Confidence: {recs['progression_rate']['confidence']}")
        print(f"      Rationale: {recs['progression_rate']['rationale']}")

        print(f"\n    Focus Areas:")
        for area in recs["focus_areas"]:
            print(f"       {area}")

        print(
            f"\n    Training Frequency: {recs['training_frequency']['runs_per_week']} runs/week"
        )
        print(f"      Confidence: {recs['training_frequency']['confidence']}")
        print(f"      Rationale: {recs['training_frequency']['rationale']}")

        print(f"\n    Long Run Distance: {recs['long_run_distance']['distance']} miles")
        print(f"      Rationale: {recs['long_run_distance']['rationale']}")

        # ============================================================
        # Summary
        # ============================================================
        print_section("SUMMARY: What GPT Will See")

        print(
            f"""
This runner is {patterns['consistency_level'].lower()} (score: {patterns['consistency_score']}),
currently running {fitness['weekly_mileage']} miles/week with a {fitness['fitness_trend'].lower()} trend.

Their longest recent run was {fitness['longest_run']} miles at an average pace of {fitness['average_pace']}.

Safety assessment shows {safety['overall_risk_level'].lower()} risk overall.

RECOMMENDATION: Start marathon training at {recs['starting_mileage']['weekly_mileage']} miles/week,
progressing at {recs['progression_rate']['rate_percent']}% per week, with {recs['training_frequency']['runs_per_week']} runs/week.

Focus areas: {', '.join(recs['focus_areas'])}
        """
        )

        # ============================================================
        # Save to file
        # ============================================================
        print_section("Saving Results")

        output_file = f"layer2_insights_{user_id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, "w") as f:
            json.dump(insights, f, indent=2)

        print(f"\n Full insights saved to: {output_file}")

    except ValueError as e:
        print(f"\n Error: {e}")
        print("\nMake sure:")
        print("  1. The user_id is correct")
        print("  2. The user has a profile in the database")
        print("  3. You're connected to the correct database")

    except Exception as e:
        print(f"\n Unexpected error: {e}")
        import traceback

        traceback.print_exc()

    finally:
        db.close()


if __name__ == "__main__":
    main()
