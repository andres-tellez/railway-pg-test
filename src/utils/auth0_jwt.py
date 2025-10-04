# src/utils/auth0_jwt.py
import os
import time
import threading
import traceback
from functools import wraps
from typing import Any, Dict, Optional, Tuple

import requests
from flask import request, jsonify, g, current_app
from src.utils.config import config
from jose import jwt

# src/utils/auth0_jwt.py
from src.db.dao.user_identity_dao import resolve_user_id_from_auth_provider


AUTH0_DOMAIN = config.AUTH0_DOMAIN
API_AUDIENCE = config.AUTH0_AUDIENCE
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


def verify_and_decode(token: str) -> dict:
    unverified_header = jwt.get_unverified_header(token)
    rsa_key = _get_rsa_key_for_kid(unverified_header["kid"])
    if rsa_key is None:
        raise Exception("Unable to find appropriate key")

    # 🔍 Debug: Log expected vs actual audience
    print(f"🔍 JWT Debug - Expected audience: {API_AUDIENCE}", flush=True)
    print(f"🔍 JWT Debug - Expected issuer: https://{AUTH0_DOMAIN}/", flush=True)

    try:
        # Try to decode without audience validation first to see what we get
        unverified_payload = jwt.decode(token, rsa_key, options={"verify_aud": False})
        print(
            f"🔍 JWT Debug - Token audience: {unverified_payload.get('aud')}",
            flush=True,
        )
        print(
            f"🔍 JWT Debug - Token issuer: {unverified_payload.get('iss')}", flush=True
        )
    except Exception as e:
        print(f"🔍 JWT Debug - Could not decode unverified payload: {e}", flush=True)

    return jwt.decode(
        token,
        rsa_key,
        algorithms=ALGORITHMS,
        audience=API_AUDIENCE,  # must be a string
        issuer=f"https://{AUTH0_DOMAIN}/",
    )


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
            # Verify JWT
            claims = verify_and_decode(token)
            g.current_user = claims

            sub = claims.get("sub")
            if not sub:
                return jsonify({"error": "unauthorized", "reason": "no_sub"}), 401

            # 🔍 DEBUG: Log claims before resolving
            if DEBUG_AUTH:
                print("🔍 Decoded JWT claims:")
                for k, v in claims.items():
                    print(f"  {k}: {v}", flush=True)

            # 🔑 Resolve internal UUID from identity table
            internal_id = resolve_user_id_from_auth_provider(
                sub, claims, create_if_missing=True
            )

            if not internal_id:
                return (
                    jsonify({"error": "unauthorized", "reason": "no_internal_user_id"}),
                    401,
                )

            g.user_id = str(internal_id)

            if DEBUG_AUTH:
                aud = claims.get("aud")
                iss = claims.get("iss")
                print(
                    f"[requires_auth] ✅ OK sub={sub} internal_id={internal_id} aud={aud} iss={iss}",
                    flush=True,
                )

            return fn(*args, **kwargs)

        except Exception as e:
            if DEBUG_AUTH:
                traceback.print_exc()
                print(f"[requires_auth] ❌ 401 reason: {e}", flush=True)
            return jsonify({"error": "unauthorized", "reason": str(e)}), 401

    return wrapper
