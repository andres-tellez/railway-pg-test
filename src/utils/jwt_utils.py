import jwt
from functools import wraps
from flask import request, jsonify, current_app

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # ✅ Internal service key override
        internal_key = request.headers.get("X-Internal-Key")
        expected_key = current_app.config.get("INTERNAL_API_KEY")

        if internal_key and expected_key and internal_key == expected_key:
            request.user = {
                "user_id": "internal",
                "is_internal": True  # ✅ FIX: enable admin privileges
            }

            
            
            
            return f(*args, **kwargs)

        # 🔐 Fallback to regular Bearer token auth
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.lower().startswith("bearer "):
            return jsonify({"error": "Authorization header missing"}), 401

        token = auth_header.split(" ")[1]
        try:
            secret = current_app.config["SECRET_KEY"]
            payload = jwt.decode(token, secret, algorithms=["HS256"])

            user_id = payload.get("sub")
            if not user_id:
                return jsonify({"error": "Token missing subject (sub)"}), 401

            request.user = {"user_id": user_id}
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        return f(*args, **kwargs)
    return decorated


def decode_token(token: str, secret: str) -> dict:
    """Decode JWT without expiration check (for internal inspection)."""
    try:
        return jwt.decode(token, secret, algorithms=["HS256"], options={"verify_exp": False})
    except jwt.DecodeError:
        raise ValueError("Invalid token format")
