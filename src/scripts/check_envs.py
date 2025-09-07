import os

print("DB present:", bool(os.getenv("DATABASE_URL")))
print("CLIENT_ID present:", bool(os.getenv("STRAVA_CLIENT_ID")))
print("CLIENT_SECRET present:", bool(os.getenv("STRAVA_CLIENT_SECRET")))
