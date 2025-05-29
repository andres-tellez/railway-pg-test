# src/scripts/insert_test_token.py

import time
import jwt
from src.db.base_model import get_session
from src.db.models.tokens import Token


def insert_dummy_token(athlete_id=347085):
    session = get_session()

    # Must match your .env's SECRET_KEY
    secret = "supersecretkey"

    # Token expires in 1 hour
    expires_at = int(time.time()) + 3600
    jwt_token = jwt.encode({"exp": expires_at}, secret, algorithm="HS256")

    token = session.query(Token).filter_by(athlete_id=athlete_id).first()
    if not token:
        token = Token(athlete_id=athlete_id)
        session.add(token)

    token.access_token = jwt_token
    token.refresh_token = jwt_token
    token.expires_at = expires_at

    session.commit()
    print(f"✅ Dummy token inserted for athlete {athlete_id}")

if __name__ == "__main__":
    insert_dummy_token()
