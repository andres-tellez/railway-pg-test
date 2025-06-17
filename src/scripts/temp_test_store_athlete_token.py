# src/scripts/temp_test_store_athlete_token.py

import sys
from src.db.db_session import get_session
from src.services.token_service import store_tokens_from_callback

def main():
    if len(sys.argv) != 2:
        print("Usage: python -m src.scripts.store_athlete_token <OAUTH_CODE>")
        return

    code = sys.argv[1]
    session = get_session()

    try:
        athlete_id = store_tokens_from_callback(code, session)
        print(f"✅ Athlete stored with ID: {athlete_id}")
    except Exception as e:
        print(f"🔥 Failed to store athlete: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    main()
