#!/bin/bash

# Usage: ./scripts/sync_athlete.sh 347085

ATHLETE_ID=$1
LOOKBACK_DAYS=${2:-30}
BATCH_SIZE=${3:-10}

if [ -z "$ATHLETE_ID" ]; then
  echo "Usage: $0 <athlete_id> [lookback_days] [batch_size]"
  exit 1
fi

echo "Running full onboard_and_sync.py for athlete $ATHLETE_ID"
python -m src.scripts.onboard_and_sync --athlete_id "$ATHLETE_ID" --lookback_days "$LOOKBACK_DAYS" --batch_size "$BATCH_SIZE"
