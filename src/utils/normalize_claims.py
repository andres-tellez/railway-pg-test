from typing import Dict, Any


def normalize_claims(claims: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize Auth0 claims so we always get plain keys.
    Falls back to custom namespace if standard OIDC keys aren't present.
    """
    return {
        "sub": claims.get("sub"),
        "email": claims.get("email") or claims.get("https://api.smartcoach.dev/email"),
        "name": (
            claims.get("name")
            or claims.get("https://api.smartcoach.dev/name")
            or "Anonymous User"
        ),
        "email_verified": claims.get("email_verified")
        or claims.get("https://api.smartcoach.dev/email_verified"),
        "picture": claims.get("picture")
        or claims.get("https://api.smartcoach.dev/picture"),
    }
