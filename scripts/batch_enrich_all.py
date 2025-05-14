import os
import time
from pathlib import Path
from services.activity_enrichment import enrich_batch

API_KEY = os.getenv("CRON_SECRET_KEY")
LIMIT   = 25
OFFFILE = Path("offset.txt")

def load_offset():
    if OFFFILE.exists():
        return int(OFFFILE.read_text())
    return 0

def save_offset(offset):
    OFFFILE.write_text(str(offset))

def main():
    athlete_id = int(os.getenv("ATHLETE_ID"))
    offset = load_offset()

    while True:
        enriched, processed, offset, rate_limited = enrich_batch(
            athlete_id,
            API_KEY,
            LIMIT,
            offset,
            os.getenv("STRAVA_CLIENT_ID"),
            os.getenv("STRAVA_CLIENT_SECRET")
        )
        print(f"Batch: enriched {enriched}/{processed}, next_offset={offset}")
        save_offset(offset)

        if rate_limited or processed == 0:
            print("Stopping enrichment run.")
            break

        time.sleep(3)

if __name__ == "__main__":
    main()
