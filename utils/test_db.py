# test_db.py

from db import get_conn

print("▶️ Attempting to connect to the database…")
conn = get_conn()
print("✅ Connection established!")
conn.close()
print("✅ Connection closed cleanly.")
