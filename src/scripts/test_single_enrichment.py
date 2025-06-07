# src/scripts/test_single_enrichment.py

# it can be run like this:  python -m src.scripts.test_single_enrichment --athlete_id 347085 --activity_id 14663194187


import os
import argparse
import src.env_loader  # ✅ This remains

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.services.strava_client import StravaClient

# Load environment variables
DATABASE_URL = os.getenv("DATABASE_URL")

# Set up DB session
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

# Argument parsing
parser = argparse.ArgumentParser(description="Run single enrichment test")
parser.add_argument("--athlete_id", type=int, required=True, help="Athlete ID")
parser.add_argument("--activity_id", type=int, required=True, help="Activity ID")
args = parser.parse_args()

athlete_id = args.athlete_id
activity_id = args.activity_id

client = StravaClient(session, athlete_id)

zones_data = client.get_hr_zones(activity_id)

if not zones_data:
    print("❌ No HR zone data returned.")
else:
    print("✅ Successfully fetched HR zone data:")
    print(zones_data)
