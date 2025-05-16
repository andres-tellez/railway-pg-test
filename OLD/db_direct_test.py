import psycopg2
from psycopg2 import OperationalError

params = {
    "host": "shinkansen.proxy.rlwy.net",
    "port": 32375,
    "dbname": "railway",
    "user": "postgres",
    "password": "loDSeqezwlOuChBqyXinGOUeAnEzGnUz",
    "sslmode": "require",
    "connect_timeout": 5,
}

print("Attempting direct connect with parameters:")
for k, v in params.items():
    if k == "password":
        v = "••••••••"
    print(f"  {k} = {v}")

try:
    conn = psycopg2.connect(**params)
    print("✅ Direct connection succeeded!")
    conn.close()
except OperationalError as e:
    print("❌ Direct connection failed:")
    print(e)
