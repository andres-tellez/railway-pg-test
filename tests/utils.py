# tests/utils.py

import jwt
import datetime

def generate_test_token(user_id, secret_key, expires_in=3600):
    payload = {
        "sub": user_id,  # ✅ Must match the "sub" field expected in production
        "exp": datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")
