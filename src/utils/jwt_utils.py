# src/utils/jwt_utils.py

import os
import jwt
from functools import wraps
from flask import request, jsonify, current_app

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", None)
        if not auth_header:
            return jsonify({"error": "Authorization header missing"}), 401

        parts = auth_header.split()

        if parts[0].lower() != "bearer" or len(parts) != 2:
            return jsonify({"error": "Invalid Authorization header format"}), 401

        token = parts[1]
        try:
            print(f"🔐 Decoding token with SECRET_KEY = {current_app.config['SECRET_KEY']}", flush=True)
            print(f"🔐 Token received: {token}", flush=True)

            payload = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])

            # 🛠 Fix: map "sub" to "user_id" for compatibility with route expectations
            user_id = payload.get("sub")
            if not user_id:
                return jsonify({"error": "Token missing subject (sub)"}), 401

            request.user = {"user_id": user_id}
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError as e:
            print(f"❌ JWT decode failed: {e}", flush=True)
            return jsonify({"error": "Invalid token"}), 401

        return f(*args, **kwargs)
    return decorated

def decode_token(token: str, secret: str) -> dict:
    """Decode JWT and return payload without verifying expiration (for internal inspection)."""
    try:
        return jwt.decode(token, secret, algorithms=["HS256"], options={"verify_exp": False})
    except jwt.DecodeError:
        raise ValueError("Invalid token format")
