from functools import wraps
from flask import request, abort, g
import jwt  # or your existing JWT package
from jwt import PyJWKClient
from os import getenv
import requests


# ✅ VERIFY_JWT FUNCTION
def verify_jwt(token: str):
    try:
        jwks_url = f"https://{getenv('AUTH0_DOMAIN')}/.well-known/jwks.json"
        jwks_client = PyJWKClient(jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(token).key

        payload = jwt.decode(
            token,
            signing_key,
            algorithms=[getenv("AUTH0_ALGORITHMS")],
            audience=getenv("AUTH0_AUDIENCE"),
            issuer=getenv("AUTH0_ISSUER"),
        )

        return {
            "internal_id": payload.get("sub"),
            **payload,
        }
    except Exception as e:
        print(f"❌ JWT verification failed: {e}")
        return None


# ✅ REQUIRES_AUTH DECORATOR
def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", None)

        if not auth_header:
            abort(401, "Authorization header is expected")

        parts = auth_header.split()

        if parts[0].lower() != "bearer":
            abort(401, "Authorization header must start with Bearer")
        elif len(parts) == 1:
            abort(401, "Token not found")
        elif len(parts) > 2:
            abort(401, "Authorization header must be Bearer token")

        token = parts[1]
        user = verify_jwt(token)
        if not user:
            abort(401, "Invalid token")

        g.user = user
        return f(*args, **kwargs)

    return decorated
