# src/utils/jwt_utils.py
"""
Auth utils for JWT validation.

✅ RS256 Auth0 JWT validation is delegated to src.utils.auth0_jwt
"""

from functools import wraps
from flask import request, jsonify, g
from src.utils.auth0_jwt import verify_and_decode


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # 🔐 Validate Auth0 Bearer token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.lower().startswith("bearer "):
            return jsonify({"error": "Authorization header missing"}), 401

        token = auth_header.split(" ")[1]
        print(f"[🔍 DEBUG] Received token: {token!r}")
        try:
            claims = verify_and_decode(token)
            g.current_user = claims
        except Exception as e:
            return jsonify({"error": f"Invalid token: {str(e)}"}), 401

        return f(*args, **kwargs)

    return decorated


def decode_token(token: str) -> dict:
    """
    Decode JWT for internal inspection (no expiration check).
    ✅ Now delegates to verify_and_decode (Auth0 RS256).
    """
    try:
        return verify_and_decode(token)
    except Exception as e:
        raise ValueError(f"Invalid token format: {str(e)}")
