# src/utils/auth0_jwt.py
import os
import time
import threading
import traceback
from functools import wraps
from typing import Any, Dict, Optional, Tuple

import requests
from flask import request, jsonify, g
from src.utils import config  # ⬅️ import config

AUTH0_DOMAIN = config.AUTH0_DOMAIN  # ⬅️ use config
API_AUDIENCE = config.AUTH0_AUDIENCE  # ⬅️ use config
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


DEBUG_AUTH = os.getenv("DEBUG_AUTH") == "1"


def requires_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if DEBUG_AUTH:
            print(
                f"[requires_auth] Authorization present={bool(auth)} len={len(auth)}",
                flush=True,
            )

        if not auth.startswith("Bearer "):
            if DEBUG_AUTH:
                print(
                    "[requires_auth] Missing/invalid Authorization header", flush=True
                )
            return jsonify({"error": "unauthorized", "reason": "no_bearer"}), 401

        token = auth.split(" ", 1)[1]
        try:
            # your existing JWKS fetch + jwt.decode(.. audience=AUTH0_AUDIENCE, issuer=..)
            claims = verify_and_decode(token)  # <-- whatever you already do
            g.current_user = claims
            if DEBUG_AUTH:
                aud = claims.get("aud")
                sub = claims.get("sub")
                iss = claims.get("iss")
                print(f"[requires_auth] OK sub={sub} aud={aud} iss={iss}", flush=True)
            return fn(*args, **kwargs)
        except Exception as e:
            if DEBUG_AUTH:
                traceback.print_exc()
                print(f"[requires_auth] 401 reason: {e}", flush=True)
            return jsonify({"error": "unauthorized", "reason": str(e)}), 401

    return wrapper
