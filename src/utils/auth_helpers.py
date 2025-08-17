# src/utils/auth_middleware.py

from functools import wraps
from flask import request, abort
from jose import jwt, JWTError
import requests
import os

ALGORITHMS = ["RS256"]


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization", None)
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0] == "Bearer":
                token = parts[1]
        if not token:
            abort(401, "Missing Bearer token in Authorization header")

        # Load environment vars at runtime
        auth0_domain = os.getenv("AUTH0_DOMAIN")
        api_audience = os.getenv("AUTH0_AUDIENCE")

        if not auth0_domain or not api_audience:
            abort(500, "Auth0 environment not configured")

        try:
            jwks_url = f"https://{auth0_domain}/.well-known/jwks.json"
            jwks = requests.get(jwks_url).json()
            unverified_header = jwt.get_unverified_header(token)

            rsa_key = {}
            for key in jwks["keys"]:
                if key["kid"] == unverified_header.get("kid"):
                    rsa_key = {
                        "kty": key["kty"],
                        "kid": key["kid"],
                        "use": key["use"],
                        "n": key["n"],
                        "e": key["e"],
                    }
                    break

            if not rsa_key:
                abort(401, "Unable to find appropriate key")

            jwt.decode(
                token,
                rsa_key,
                algorithms=ALGORITHMS,
                audience=api_audience,
                issuer=f"https://{auth0_domain}/",
            )

        except JWTError as e:
            abort(401, f"Token verification failed: {str(e)}")
        except Exception as e:
            abort(500, f"Unexpected error: {str(e)}")

        return f(*args, **kwargs)

    return decorated
