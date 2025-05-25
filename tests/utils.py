# tests/utils.py

import jwt
import datetime

def generate_test_token(username, secret_key, expires_in=3600):
    """
    Generate a JWT for testing with 'sub' claim matching the production token structure.

    Args:
        username (str): Username or identifier to embed in the token as 'sub'.
        secret_key (str): Secret key used for signing.
        expires_in (int): Token expiration in seconds (default: 1 hour).

    Returns:
        str: Encoded JWT token.
    """
    payload = {
        "sub": username,  # Must match what login_user() uses
        "exp": datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")
