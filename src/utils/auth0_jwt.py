# src/utils/auth0_jwt.py
import os
import time
import threading
import traceback
import logging
from functools import wraps
from typing import Any, Dict, Optional, Tuple

import requests
from flask import request, jsonify, g, current_app
from src.utils.config import config
from jose import jwt

# src/utils/auth0_jwt.py
from src.db.dao.user_identity_dao import resolve_user_id_from_auth_provider

logger = logging.getLogger(__name__)


AUTH0_DOMAIN = config.AUTH0_DOMAIN
API_AUDIENCE = config.AUTH0_AUDIENCE
AUX_AUDIENCE = os.getenv("AUTH0_ID_TOKEN_AUDIENCE") or os.getenv("AUTH0_CLIENT_ID")
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


def verify_and_decode(token: str, audience: str | None = None) -> dict:
    print("verify_and_decode: extracting unverified header", flush=True)
    unverified_header = jwt.get_unverified_header(token)
    print(
        f"verify_and_decode: retrieving JWKS for kid={unverified_header.get('kid')}",
        flush=True,
    )
    rsa_key = _get_rsa_key_for_kid(unverified_header["kid"])
    print(
        f"verify_and_decode: JWKS retrieval {'succeeded' if rsa_key else 'failed'}",
        flush=True,
    )
    if rsa_key is None:
        raise Exception("Unable to find appropriate key")

    expected_audience = audience or API_AUDIENCE
    # Allow comma-separated audiences in env var
    if expected_audience and "," in expected_audience:
        expected_audience = [
            part.strip() for part in expected_audience.split(",") if part.strip()
        ]

    print("verify_and_decode: decoding JWT", flush=True)
    return jwt.decode(
        token,
        rsa_key,
        algorithms=ALGORITHMS,
        audience=expected_audience,  # must be a string or list
        issuer=f"https://{AUTH0_DOMAIN}/",
        options={"leeway": int(os.getenv("AUTH0_EXP_LEEWAY", "120"))},
    )


def requires_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        # Only log presence, never log length or content (security best practice)
        logger.debug(f"[requires_auth] {request.path} - Authorization header present")
        if DEBUG_AUTH:
            logger.debug(f"[requires_auth] Authorization header present")
            # NEVER log token length or content

        if not auth.startswith("Bearer "):
            logger.warning(
                f"[requires_auth] {request.path} - Missing/invalid Authorization header"
            )
            if DEBUG_AUTH:
                logger.debug("[requires_auth] Missing/invalid Authorization header")
            return jsonify({"error": "unauthorized", "reason": "no_bearer"}), 401

        token = auth.split(" ", 1)[1]
        try:
            # Verify JWT
            claims = verify_and_decode(token)
            g.current_user = claims

            sub = claims.get("sub")
            if not sub:
                logger.warning(f"[requires_auth] Missing sub claim in token")
                return jsonify({"error": "unauthorized", "reason": "no_sub"}), 401

            # 🔍 DEBUG: Log only non-sensitive claims (never log email, name, picture, or full token)
            if DEBUG_AUTH:
                # Only log safe, non-sensitive fields
                safe_fields = ["sub", "aud", "iss", "exp", "iat", "azp"]
                safe_claims = {k: v for k, v in claims.items() if k in safe_fields}
                logger.debug(f"🔍 Decoded JWT claims (safe): {safe_claims}")
                # NEVER log: email, email_verified, name, picture, or full token content

            # 🔑 Resolve internal UUID from identity table
            internal_id = resolve_user_id_from_auth_provider(
                sub, claims, create_if_missing=True
            )

            if not internal_id:
                logger.warning(
                    f"[requires_auth] Could not resolve internal user_id for sub={sub}"
                )
                return (
                    jsonify({"error": "unauthorized", "reason": "no_internal_user_id"}),
                    401,
                )

            g.user_id = str(internal_id)

            if DEBUG_AUTH:
                aud = claims.get("aud")
                iss = claims.get("iss")
                logger.debug(
                    f"[requires_auth] ✅ OK sub={sub} internal_id={internal_id} aud={aud} iss={iss}"
                )

            return fn(*args, **kwargs)

        except Exception as e:
            # Log full error details server-side only (for debugging)
            if DEBUG_AUTH:
                logger.exception(f"[requires_auth] ❌ Authentication failed: {e}")
            else:
                logger.warning(
                    f"[requires_auth] ❌ Authentication failed: {e}", exc_info=True
                )

            # Return generic error to client (don't leak internal details)
            return jsonify({"error": "unauthorized", "reason": "invalid_token"}), 401

    return wrapper
