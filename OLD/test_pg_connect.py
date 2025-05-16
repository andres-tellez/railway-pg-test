# psycopg2_test.py

import psycopg2
import psycopg2.extensions

print("🔍 Testing psycopg2 connection with sslmode=disable...")

try:
    conn = psycopg2.connect(
        dbname="railway",
        user="postgres",
        password="loDSeqezwlOuChBqyXinGOUeAnEzGnUz",
        host="shinkansen.proxy.rlwy.net",
        port=32375,
        sslmode="disable",  # <-- TEMPORARY for debugging only
    )
    print("✅ psycopg2 connection succeeded!")
    conn.close()
except Exception as e:
    print(f"❌ psycopg2 connection failed: {e}")
