import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# ✅ Adjust path to include `app/` where `src/` resides
current_file = Path(__file__).resolve()
src_root = current_file.parents[2]  # .../app/
sys.path.insert(0, str(src_root))

# ✅ Load environment
load_dotenv(dotenv_path=src_root / ".env", override=True)

# ✅ Confirm environment loaded
print(f"[DEBUG] DATABASE_URL: {os.getenv('DATABASE_URL')}")

# ✅ Import logic
from src.db.db_session import get_session
from src.services.ingestion_orchestrator_service import run_full_ingestion_and_enrichment

# ✅ Main entry
if __name__ == "__main__":
    athlete_id = int(input("Enter athlete_id: "))
    session = get_session()
    result = run_full_ingestion_and_enrichment(session, athlete_id)
    print(result)
    session.close()
