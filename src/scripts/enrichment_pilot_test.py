# src/scripts/enrichment_pilot_test.py

from src.db.db_session import get_session
from src.services.activity_sync import sync_full_history, ensure_fresh_access_token
from src.services.enrichment_sync import run_enrichment_batch
from src.env_loader import *  # load .env adjustments

athlete_id = 347085  # Developer test athlete

session = get_session()

try:
    # ✅ Step 1 — Fetch valid access token (auto-refresh if needed)
    access_token = ensure_fresh_access_token(session, athlete_id)

    # ✅ Step 2 — Sync only 5 activities (last ~180 days window)
    synced_count = sync_full_history(
        session=session,
        athlete_id=athlete_id,
        lookback_days=180,  # last ~6 months
        max_activities=5
    )

    print(f"✅ Backfill sync complete — {synced_count} activities synced.")

    # ✅ Step 3 — Run enrichment on those 5 activities
    enriched_count = run_enrichment_batch(session, athlete_id, batch_size=5)
    print(f"✅ Enrichment complete — {enriched_count} activities enriched.")

except Exception as e:
    print(f"❌ Pilot test failed: {e}")

finally:
    session.close()