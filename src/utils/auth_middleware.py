# src/utils/auth_middleware.py

from functools import wraps
from flask import request, abort
from jose.exceptions import JWTError
from src.utils.auth_helpers import decode_auth_token


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization", None)
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

        if not token:
            abort(401)

        try:
            payload = decode_auth_token(token)
            # Optionally, you can attach payload to Flask's g if needed
        except JWTError:
            abort(401)

        return f(*args, **kwargs)

    return decorated
