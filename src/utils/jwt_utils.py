import jwt
from functools import wraps
from flask import request, jsonify, current_app

import src.utils.config as config


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # ✅ Internal service key override
        internal_key = request.headers.get("X-Internal-Key")

        if internal_key and config.INTERNAL_API_KEY and internal_key == config.INTERNAL_API_KEY:
            request.user = {
                "user_id": "internal",
                "is_internal": True  # ✅ Enable admin privileges
            }
            return f(*args, **kwargs)

        # 🔐 Fallback to regular Bearer token auth
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.lower().startswith("bearer "):
            return jsonify({"error": "Authorization header missing"}), 401

        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, config.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("sub")
            if not user_id:
                return jsonify({"error": "Token missing subject (sub)"}), 401

            request.user = {
                "user_id": user_id,
                "is_internal": user_id == "internal"
            }
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        return f(*args, **kwargs)
    return decorated


def decode_token(token: str) -> dict:
    """Decode JWT without expiration check (for internal inspection)."""
    try:
        return jwt.decode(token, config.SECRET_KEY, algorithms=["HS256"], options={"verify_exp": False})
    except jwt.DecodeError:
        raise ValueError("Invalid token format")
