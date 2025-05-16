from dotenv import load_dotenv
import os, psycopg2

load_dotenv()  # <-- this line loads .env into os.environ

url = os.getenv("DATABASE_URL")
print("Connecting to:", url)
conn = psycopg2.connect(url, connect_timeout=5)
print("✅ Connected successfully!")
conn.close()
