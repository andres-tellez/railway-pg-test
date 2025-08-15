# src/utils/auth0_jwt.py
import os
import time
import threading
from functools import wraps
from typing import Any, Dict, Optional, Tuple

import requests
from flask import request, jsonify, g
from jose import jwt, JWTError

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")  # e.g. dev-xxxxx.us.auth0.com
API_AUDIENCE = os.getenv("AUTH0_AUDIENCE") or os.getenv(
    "AUTH0_API_AUDIENCE"
)  # e.g. https://api.smartcoach.dev
ALGORITHMS = ["RS256"]
JWKS_URL = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json" if AUTH0_DOMAIN else None
JWKS_TTL_SEC = 60 * 10  # 10 minutes cache

# Simple in-memory JWKS cache (kid -> rsa_key)
_jwks_cache_lock = threading.Lock()
_jwks_cache: Dict[str, Tuple[Dict[str, Any], float]] = {}  # {kid: (rsa_key, expiry_ts)}
_jwks_set_expiry: float = 0.0  # when the whole JWKS set should be refetched


def _fetch_jwks() -> Dict[str, Any]:
    if not JWKS_URL:
        raise RuntimeError("AUTH0_DOMAIN not configured (JWKS URL cannot be built).")
    resp = requests.get(JWKS_URL, timeout=5)
    resp.raise_for_status()
    return resp.json()


def _get_rsa_key_for_kid(kid: str) -> Optional[Dict[str, Any]]:
    global _jwks_set_expiry
    now = time.time()

    with _jwks_cache_lock:
        # Refresh the whole JWKS set if expired or cache empty
        if now >= _jwks_set_expiry or not _jwks_cache:
            jwks = _fetch_jwks()
            keys = jwks.get("keys", [])
            _jwks_cache.clear()
            for k in keys:
                _jwks_cache[k.get("kid")] = (
                    {
                        "kty": k.get("kty"),
                        "kid": k.get("kid"),
                        "use": k.get("use"),
                        "n": k.get("n"),
                        "e": k.get("e"),
                    },
                    now + JWKS_TTL_SEC,
                )
            _jwks_set_expiry = now + JWKS_TTL_SEC

        # Return valid cached key if available
        item = _jwks_cache.get(kid)
        if item and now < item[1]:
            return item[0]

        # If specific kid missing/expired, force refresh once more
        jwks = _fetch_jwks()
        keys = jwks.get("keys", [])
        for k in keys:
            if k.get("kid") == kid:
                rsa_key = {
                    "kty": k.get("kty"),
                    "kid": k.get("kid"),
                    "use": k.get("use"),
                    "n": k.get("n"),
                    "e": k.get("e"),
                }
                _jwks_cache[kid] = (rsa_key, now + JWKS_TTL_SEC)
                return rsa_key

    return None


def _error(status: int, message: str):
    return jsonify({"error": message}), status


def requires_auth(f):
    """Decorator for RS256/JWKS Auth0 validation."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        # --- DEV BYPASS: set AUTH_BYPASS=1 in your local env to skip JWT entirely ---
        if os.getenv("AUTH_BYPASS") == "1":
            g.current_user = {
                "sub": "auth0|dev-bypass",
                "scope": None,
                "permissions": [],
            }
            return f(*args, **kwargs)

        # Extract Bearer token
        auth_header = request.headers.get("Authorization", "")
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return _error(401, "Missing or invalid Authorization header")

        token = parts[1]

        # Validate presence of required config
        if not AUTH0_DOMAIN or not API_AUDIENCE:
            return _error(500, "Auth0 not configured (domain/audience)")

        # Get unverified header to find the kid
        try:
            unverified = jwt.get_unverified_header(token)
            kid = unverified.get("kid")
        except JWTError:
            return _error(401, "Invalid token header")

        if not kid:
            return _error(401, "Missing kid in token header")

        rsa_key = _get_rsa_key_for_kid(kid)
        if not rsa_key:
            return _error(401, "Unable to find matching JWKS key")

        try:
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=ALGORITHMS,
                audience=API_AUDIENCE,
                issuer=f"https://{AUTH0_DOMAIN}/",
                options={
                    "verify_aud": True,
                    "verify_iss": True,
                    "verify_exp": True,
                },
            )
        except JWTError as e:
            return _error(401, f"Token verification failed: {str(e)}")

        # Success → attach user to request context
        # (use flask.g to avoid mutating the request object)
        g.current_user = {
            "sub": payload.get("sub"),
            "scope": payload.get("scope"),
            "permissions": payload.get("permissions"),
            "raw": payload,
        }
        return f(*args, **kwargs)

    return wrapper
