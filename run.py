import sys
from pathlib import Path
from dotenv import load_dotenv

import src.utils.config as config

print("📦 Starting run.py...", flush=True)

# 🔐 Load .env explicitly (important in Docker or if run manually)
load_dotenv()

# Ensure the project root is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Auto-rewrite DATABASE_URL for local if necessary
if config.IS_LOCAL and config.DATABASE_URL and 'postgres@postgres:' in config.DATABASE_URL:
    patched_db_url = config.DATABASE_URL.replace('postgres@postgres:', 'postgres@localhost:')
    os.environ['DATABASE_URL'] = patched_db_url
    print(f"🔧 DATABASE_URL rewritten for local: {patched_db_url}", flush=True)
else:
    print(f"✅ DATABASE_URL used as-is: {config.DATABASE_URL}", flush=True)

# Attempt to create the app and log failure explicitly
try:
    from src.app import create_app
    app = create_app()  # 🔑 Gunicorn will reference this: "run:app"
    print("✅ App created via create_app()", flush=True)
except Exception as e:
    print("🔥 App creation failed:", e, flush=True)
    import traceback
    traceback.print_exc()
    raise  # Re-raise so Railway crash logs capture the stack

# Check that templates folder is visible to Flask
template_dir = Path(__file__).parent / "templates"
if not template_dir.exists():
    print(f"❌ Template folder not found: {template_dir}")
else:
    print(f"📂 Template folder contents: {[f.name for f in template_dir.glob('*')]}")

# If run directly, use Flask dev server
if __name__ == "__main__":
    port = config.PORT

    # 🔍 Full environment debug
    config_db_url = app.config.get("DATABASE_URL") or config.DATABASE_URL
    print("🔍 ENV DATABASE_URL =", config.DATABASE_URL, flush=True)
    print("🔍 CONFIG DATABASE_URL =", config_db_url, flush=True)

    if not config_db_url:
        print("❗ DATABASE_URL not set — exiting", flush=True)
        sys.exit(1)

    try:
        from psycopg2 import connect
        print(f"🔌 Attempting psycopg2.connect() to: {config_db_url}", flush=True)
        sanitized_url = config_db_url.replace("postgresql+psycopg2://", "postgresql://")
        conn = connect(sanitized_url)
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            cur.fetchone()
        print("✅ DB test query succeeded!", flush=True)
    except Exception as e:
        print("⚠️ DB test query failed:", e, flush=True)
        import traceback
        traceback.print_exc()

    print(f"🚀 Starting app locally on 0.0.0.0:{port}", flush=True)
    app.run(host="0.0.0.0", port=port, debug=True)
