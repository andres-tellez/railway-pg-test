import os
import psycopg2

# Grab DATABASE_URL from your environment
db_url = os.environ.get("DATABASE_URL")
if not db_url:
    raise RuntimeError("DATABASE_URL is not set")

# Connect and drop the table
conn = psycopg2.connect(db_url, sslmode="require")
cur = conn.cursor()
cur.execute("DROP TABLE IF EXISTS mile_splits;")
conn.commit()

# List tables to confirm
cur.execute("""
    SELECT table_name 
      FROM information_schema.tables 
     WHERE table_schema='public';
""")
tables = [row[0] for row in cur.fetchall()]
print("Remaining tables in Postgres:", tables)

cur.close()
conn.close()
