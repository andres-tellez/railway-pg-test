"""
Test Layer 3 - Prompt Builder with real data
"""

import os
import sys
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.abspath("."))

# Load environment variables
env_path = os.path.join(os.path.dirname(__file__), ".env.local")
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path, override=True)
    print(f"Loaded environment from {env_path}")

from src.db.db_session import get_session
from src.services.training_plan.data_collection_service import DataCollectionService
from src.services.training_plan.insights_calculation_service import (
    InsightsCalculationService,
)
from src.services.training_plan.prompt_builder_service import PromptBuilderService

# Your user ID
USER_ID = "ddc21831-1b01-4cfc-82db-7632ab2cfba1"

# Sample plan request
PLAN_REQUEST = {
    "plan_name": "My First Marathon",
    "race_date": "2025-06-15",  # ~30 weeks from now
    "race_distance": "Marathon",
    "race_name": "Sample Marathon",
    "race_location": "Boston, MA",
    "primary_goal": "Just Finish",
    "marathon_experience": "First",
    "target_time": None,
    "training_days": ["Monday", "Wednesday", "Friday", "Saturday"],
    "notes": "First marathon attempt, nervous but excited!",
}


def main():
    print("=" * 80)
    print("  LAYER 3 TEST: Prompt Builder")
    print("=" * 80)

    with get_session() as session:
        # Layer 1: Collect data
        print("\n[1] Collecting data from Layer 1...")
        raw_data = DataCollectionService.collect_all_data(
            session=session,
            user_id=USER_ID,
            plan_request=PLAN_REQUEST,
            activity_weeks=12,
        )

        print(f"    Activities: {len(raw_data['strava_activities'])}")
        print(f"    Profile: {raw_data['user_profile']['age_group']}")

        # Layer 2: Calculate insights
        print("\n[2] Calculating insights from Layer 2...")
        insights = InsightsCalculationService.calculate_all_insights(raw_data)

        # Layer 3: Build prompt
        print("\n[3] Building GPT prompt from Layer 3...")
        prompt = PromptBuilderService.build_complete_prompt(
            insights=insights,
            user_profile=raw_data["user_profile"],
            plan_request=PLAN_REQUEST,
        )

        # Display results
        print("\n" + "=" * 80)
        print("  PROMPT OUTPUT")
        print("=" * 80)

        print("\n[SYSTEM MESSAGE]")
        print("-" * 80)
        print(prompt["messages"][0]["content"])

        print("\n\n[USER MESSAGE]")
        print("-" * 80)
        print(prompt["messages"][1]["content"])

        print("\n\n[CONFIG]")
        print("-" * 80)
        print(json.dumps(prompt["config"], indent=2))

        print("\n\n[METADATA]")
        print("-" * 80)
        print(json.dumps(prompt["metadata"], indent=2))

        # Calculate token estimate
        total_chars = len(prompt["messages"][0]["content"]) + len(
            prompt["messages"][1]["content"]
        )
        estimated_tokens = total_chars // 4  # Rough estimate: 4 chars per token

        print("\n\n[STATS]")
        print("-" * 80)
        print(f"System message: {len(prompt['messages'][0]['content'])} characters")
        print(f"User message: {len(prompt['messages'][1]['content'])} characters")
        print(f"Total: {total_chars} characters")
        print(f"Estimated tokens: ~{estimated_tokens} tokens")

        # Save to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"layer3_prompt_{timestamp}.json"
        with open(filename, "w") as f:
            json.dump(prompt, f, indent=2)

        print(f"\n[SAVED] Full prompt saved to: {filename}")


if __name__ == "__main__":
    main()
