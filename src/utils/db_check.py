# db_check.py

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
print("📡 Testing DATABASE_URL:", DATABASE_URL)

# Create engine and attempt connection
engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))  # ✅ Use text() for SQLAlchemy 2.0+
        print("✅ DB connection succeeded:", result.fetchone())
except Exception as e:
    print("❌ DB connection failed:", str(e))
