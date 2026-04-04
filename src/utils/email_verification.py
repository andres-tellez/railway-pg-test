"""Helpers for interpreting OIDC / Auth0 email_verified claims."""

from typing import Any


def is_email_verified_claim(val: Any) -> bool:
    """
    Only explicit verification counts for cross-provider user merge (avoid account takeover).

    Auth0 / OIDC usually sends a boolean; some stacks use strings.
    """
    if val is True:
        return True
    if val is False or val is None:
        return False
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes")
    return False
