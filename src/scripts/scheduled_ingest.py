# src/scripts/scheduled_ingest.py

from src.db.db_session import get_session
from src.services.ingestion_orchestrator_service import (
    run_full_ingestion_and_enrichment,
)
from src.services.token_service import refresh_access_token, refresh_token_if_expired
from sqlalchemy import text


if __name__ == "__main__":
    session = get_session()

    # ⚠️ Hardcoding athlete_id means we lose user context.
    # Let's resolve both athlete_id + user_id instead.
    mapping_row = session.execute(
        text(
            "SELECT user_id, athlete_id FROM public.user_athletes WHERE athlete_id = :aid"
        ),
        {"aid": 347085},  # <-- replace with config/env later if needed
    ).fetchone()

    if not mapping_row:
        print("❌ No mapping found for athlete 347085")
        exit(1)

    user_id = mapping_row.user_id
    athlete_id = mapping_row.athlete_id

    # 🔁 Ensure valid token
    refresh_access_token(session, athlete_id)
    session.commit()
    session.expire_all()

    # ✅ Optional fallback
    refresh_token_if_expired(session, athlete_id)

    # ✅ Now run ingestion with both user_id + athlete_id
    result = run_full_ingestion_and_enrichment(
        session, athlete_id, user_id=user_id, lookback_days=1
    )
    print(f"✅ Ingestion complete: {result}")

    session.close()
