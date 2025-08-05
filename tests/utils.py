import jwt
import datetime


def generate_test_token(user_id, secret_key, expires_in=3600):
    payload = {
        "sub": user_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in),
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")
