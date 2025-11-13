#!/usr/bin/env python
"""Simple script to sync today's activities"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# Load staging environment
env_staging_path = Path(".env.staging")
if env_staging_path.exists():
    load_dotenv(env_staging_path, override=True)
    print(f"✅ Loaded staging environment from {env_staging_path}")
else:
    print("❌ .env.staging not found!")
    sys.exit(1)

# Import the service
from src.services.ingestion_orchestrator_service import (
    run_full_ingestion_and_enrichment,
)


def main():
    # You'll need to replace these with your actual IDs
    athlete_id = int(input("Enter your athlete_id: "))
    user_id = input("Enter your user_id (UUID): ")

    # Set up time range for today
    today = datetime.utcnow().date()
    start_of_day = datetime.combine(today, datetime.min.time())
    end_of_day = datetime.combine(today, datetime.max.time())

    print(f"\n🔄 Syncing activities for today ({today})...")
    print(f"📅 Time range: {start_of_day} to {end_of_day}")

    # Call the service directly
    result = run_full_ingestion_and_enrichment(
        _unused_session=None,  # The function gets its own session
        athlete_id=athlete_id,
        user_id=user_id,
        after=int(start_of_day.timestamp()),
        before=int(end_of_day.timestamp()),
        max_activities=10,
    )

    print(f"\n✅ Sync complete!")
    print(f"📊 Result: {result}")


if __name__ == "__main__":
    main()

