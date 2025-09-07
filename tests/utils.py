import base64
import json


def generate_fake_jwt(sub: str = "auth0|test-user") -> str:
    """
    Generate a minimal unsigned JWT-like string for testing only.
    This bypasses RS256 and is used in tests with monkeypatched verify_and_decode.
    """
    header = (
        base64.urlsafe_b64encode(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
        .decode()
        .rstrip("=")
    )
    payload = (
        base64.urlsafe_b64encode(json.dumps({"sub": sub}).encode()).decode().rstrip("=")
    )
    return f"{header}.{payload}."
