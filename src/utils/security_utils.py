"""
security_utils.py

Security Utilities for Token and Secret Redaction
================================================

Provides utilities to safely log sensitive information without exposing secrets.
"""

import re
from typing import Any, Dict, Optional


def redact_token(token: Optional[str], show_length: bool = True) -> str:
    """
    Redact an access or refresh token for safe logging.

    Args:
        token: Token string to redact
        show_length: If True, show token length in redacted version

    Returns:
        Redacted token string (e.g., "abc123...xyz789" or "***REDACTED***")
    """
    if not token:
        return "***EMPTY***"

    if len(token) <= 8:
        return "***REDACTED***"

    # Show first 4 and last 4 characters, mask the middle
    first = token[:4]
    last = token[-4:]
    masked = "***" + ("*" * max(0, len(token) - 8))

    if show_length:
        return f"{first}{masked}{last} (length: {len(token)})"
    return f"{first}{masked}{last}"


def redact_secret(secret: Optional[str]) -> str:
    """
    Redact a secret (client secret, API key, etc.) for safe logging.

    Args:
        secret: Secret string to redact

    Returns:
        Redacted secret string (e.g., "abc1****d79c")
    """
    if not secret:
        return "***NOT SET***"

    if len(secret) <= 8:
        return "***REDACTED***"

    # Show first 4 and last 4 characters
    first = secret[:4]
    last = secret[-4:]
    masked = "*" * max(0, len(secret) - 8)

    return f"{first}{masked}{last}"


def redact_dict(
    d: Dict[str, Any], secret_keys: Optional[list] = None
) -> Dict[str, Any]:
    """
    Redact sensitive keys from a dictionary for safe logging.

    Args:
        d: Dictionary to redact
        secret_keys: List of keys to redact (defaults to common secret keys)

    Returns:
        Dictionary with redacted values
    """
    if secret_keys is None:
        secret_keys = [
            "access_token",
            "refresh_token",
            "client_secret",
            "client_id",  # Usually safe, but redact for consistency
            "code",  # OAuth code
            "password",
            "secret",
            "api_key",
            "token",
            "authorization",
            "bearer",
        ]

    redacted = {}
    for key, value in d.items():
        key_lower = key.lower()

        # Check if this key should be redacted
        should_redact = any(secret_key in key_lower for secret_key in secret_keys)

        if should_redact and isinstance(value, str):
            if "token" in key_lower or "code" in key_lower:
                redacted[key] = redact_token(value, show_length=False)
            else:
                redacted[key] = redact_secret(value)
        elif isinstance(value, dict):
            redacted[key] = redact_dict(value, secret_keys)
        else:
            redacted[key] = value

    return redacted


def redact_url(url: str) -> str:
    """
    Redact sensitive query parameters from URLs.

    Args:
        url: URL string that may contain sensitive parameters

    Returns:
        URL with sensitive parameters redacted
    """
    # Common sensitive URL parameters
    sensitive_params = [
        "token",
        "code",
        "secret",
        "key",
        "access_token",
        "refresh_token",
    ]

    # Simple redaction - replace sensitive param values
    for param in sensitive_params:
        pattern = rf"{param}=([^&]+)"
        url = re.sub(pattern, f"{param}=***REDACTED***", url, flags=re.IGNORECASE)

    return url


def redact_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """
    Redact sensitive headers (like Authorization) for safe logging.

    Args:
        headers: Headers dictionary

    Returns:
        Headers with sensitive values redacted
    """
    redacted = {}
    for key, value in headers.items():
        key_lower = key.lower()

        if key_lower in ["authorization", "x-api-key", "x-auth-token"]:
            if isinstance(value, str) and value.startswith("Bearer "):
                token = value[7:]  # Remove "Bearer " prefix
                redacted[key] = f"Bearer {redact_token(token, show_length=False)}"
            else:
                redacted[key] = redact_secret(value)
        else:
            redacted[key] = value

    return redacted


def redact_connection_string(connection_string: Optional[str]) -> str:
    """
    Redact passwords and sensitive parts from database connection strings.

    Examples:
        postgresql://user:password@host:port/db
        -> postgresql://user:***REDACTED***@host:port/db

    Args:
        connection_string: Database connection string (e.g., DATABASE_URL)

    Returns:
        Connection string with password redacted
    """
    if not connection_string:
        return "***NOT SET***"

    # Pattern: protocol://user:password@host:port/db
    # Match and redact password
    pattern = r"([^:]+://[^:]+:)([^@]+)(@.+)"
    match = re.search(pattern, connection_string)

    if match:
        prefix = match.group(1)
        password = match.group(2)
        suffix = match.group(3)
        redacted_password = "***REDACTED***"
        return f"{prefix}{redacted_password}{suffix}"

    # If no password pattern found, return as-is (might be safe format)
    return connection_string
