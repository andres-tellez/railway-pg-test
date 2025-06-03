import os
from dotenv import load_dotenv

# Load .env variables automatically
load_dotenv()

# Pull current DATABASE_URL
env_db_url = os.environ.get("DATABASE_URL")
is_local = os.environ.get("IS_LOCAL", "false").lower() == "true"

# Defensive patching for Docker/Local cross-mode
if is_local and env_db_url:
    # Handle common Docker hostname cases
    if '@postgres:' in env_db_url:
        patched_db_url = env_db_url.replace('@postgres:', '@localhost:')
        os.environ['DATABASE_URL'] = patched_db_url
        print(f"🔧 DATABASE_URL rewritten for local Docker: {patched_db_url}")
    elif '@db:' in env_db_url:
        patched_db_url = env_db_url.replace('@db:', '@localhost:')
        os.environ['DATABASE_URL'] = patched_db_url
        print(f"🔧 DATABASE_URL rewritten for local Docker alias (db): {patched_db_url}")
    else:
        print("✅ No Docker hostname detected; DATABASE_URL left unchanged.")
else:
    print(f"✅ DATABASE_URL used as-is: {env_db_url}")
