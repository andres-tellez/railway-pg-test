"""
Security Utilities
==================

Security-related utility functions for sanitizing data, preventing information leakage,
and improving overall security posture.

Key Functions:
- Redaction: redact_token, redact_secret, redact_dict, redact_url, redact_headers, redact_connection_string
- Sanitization: sanitize_error_message, sanitize_user_input, sanitize_exception_details
- Validation: is_safe_string, get_safe_error_message
"""

import re
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ============================================================================
# Redaction Functions (for logging)
# ============================================================================


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


# ============================================================================
# Sanitization Functions (for error messages and user input)
# ============================================================================

# Patterns for detecting sensitive information
SENSITIVE_PATTERNS = [
    r"password\s*[:=]\s*\S+",  # password: xxx
    r"token\s*[:=]\s*\S+",  # token: xxx
    r"secret\s*[:=]\s*\S+",  # secret: xxx
    r"api[_-]?key\s*[:=]\s*\S+",  # api_key: xxx
    r"access[_-]?token\s*[:=]\s*\S+",  # access_token: xxx
    r"refresh[_-]?token\s*[:=]\s*\S+",  # refresh_token: xxx
    r"authorization\s*[:=]\s*\S+",  # authorization: xxx
    r"bearer\s+\S+",  # bearer xxx
    r"/[a-zA-Z0-9_/]+\.(py|js|ts|sql|env|key|pem)",  # file paths
    r"database[_-]?url\s*[:=]\s*\S+",  # database_url: xxx
    r"connection[_-]?string\s*[:=]\s*\S+",  # connection_string: xxx
]

# Safe error messages for common errors
SAFE_ERROR_MESSAGES = {
    "database": "A database error occurred. Please try again later.",
    "network": "A network error occurred. Please check your connection and try again.",
    "authentication": "Authentication failed. Please check your credentials.",
    "authorization": "You don't have permission to perform this action.",
    "validation": "Invalid input provided. Please check your request.",
    "not_found": "The requested resource was not found.",
    "rate_limit": "Too many requests. Please try again later.",
    "internal": "An internal error occurred. Please try again later.",
}


def sanitize_error_message(error: Exception, context: str = "general") -> str:
    """
    Sanitize error messages to prevent information leakage.

    Removes:
    - File paths
    - Database connection strings
    - API keys and tokens
    - Internal implementation details

    Args:
        error: The exception object
        context: Context where error occurred (e.g., "oauth", "webhook", "ingestion")

    Returns:
        Sanitized error message safe for user-facing responses
    """
    error_str = str(error)
    error_type = type(error).__name__

    # Check if it's a known safe error type
    if (
        error_type in ["ValidationError", "ValueError"]
        and "validation" in context.lower()
    ):
        # For validation errors, return a generic message
        return SAFE_ERROR_MESSAGES.get("validation", "Invalid input provided.")

    # Remove sensitive patterns
    sanitized = error_str
    for pattern in SENSITIVE_PATTERNS:
        sanitized = re.sub(pattern, "[REDACTED]", sanitized, flags=re.IGNORECASE)

    # Remove file paths (keep only filename)
    sanitized = re.sub(r"/[^\s]+/", "[PATH]/", sanitized)
    sanitized = re.sub(r"[A-Z]:\\[^\s]+\\", "[PATH]\\", sanitized)  # Windows paths

    # Remove stack trace indicators
    sanitized = re.sub(
        r"Traceback.*?File.*?line \d+", "[STACK_TRACE]", sanitized, flags=re.DOTALL
    )

    # If sanitization removed too much, use generic message
    if len(sanitized) < 10 or "[REDACTED]" in sanitized:
        # Use context-specific safe message
        if "oauth" in context.lower() or "token" in context.lower():
            return SAFE_ERROR_MESSAGES.get("authentication", "Authentication failed.")
        elif "webhook" in context.lower():
            return SAFE_ERROR_MESSAGES.get("internal", "Webhook processing failed.")
        elif "ingestion" in context.lower() or "sync" in context.lower():
            return SAFE_ERROR_MESSAGES.get("internal", "Data synchronization failed.")
        elif "database" in error_str.lower() or "sql" in error_str.lower():
            return SAFE_ERROR_MESSAGES.get("database", "A database error occurred.")
        else:
            return SAFE_ERROR_MESSAGES.get("internal", "An error occurred.")

    return sanitized


def sanitize_user_input(input_str: str, max_length: int = 1000) -> str:
    """
    Sanitize user-provided input to prevent injection attacks.

    Args:
        input_str: User input string
        max_length: Maximum allowed length

    Returns:
        Sanitized input string
    """
    if not isinstance(input_str, str):
        return str(input_str)[:max_length]

    # Remove null bytes
    sanitized = input_str.replace("\x00", "")

    # Truncate to max length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]

    # Remove control characters (except newline, tab, carriage return)
    sanitized = re.sub(r"[\x00-\x08\x0B-\x1F\x7F]", "", sanitized)

    return sanitized


def is_safe_string(input_str: str, allowed_chars: Optional[str] = None) -> bool:
    """
    Check if string contains only safe characters.

    Args:
        input_str: String to check
        allowed_chars: Optional regex pattern for allowed characters

    Returns:
        True if string is safe, False otherwise
    """
    if not isinstance(input_str, str):
        return False

    # Default: alphanumeric, spaces, common punctuation
    if allowed_chars is None:
        allowed_chars = r"^[a-zA-Z0-9\s\-_.,!?@#$%&*()+=\[\]{}|\\:;\"'<>/]+$"

    return bool(re.match(allowed_chars, input_str))


def sanitize_exception_details(details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize exception details dictionary to remove sensitive information.

    Args:
        details: Exception details dictionary

    Returns:
        Sanitized details dictionary
    """
    if not isinstance(details, dict):
        return {}

    sanitized = {}
    sensitive_keys = [
        "password",
        "token",
        "secret",
        "api_key",
        "access_token",
        "refresh_token",
        "authorization",
        "database_url",
        "connection_string",
        "file_path",
        "stack_trace",
        "traceback",
    ]

    for key, value in details.items():
        key_lower = key.lower()

        # Skip sensitive keys
        if any(sensitive in key_lower for sensitive in sensitive_keys):
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, str):
            # Sanitize string values
            sanitized[key] = sanitize_error_message(Exception(value))
        elif isinstance(value, dict):
            # Recursively sanitize nested dictionaries
            sanitized[key] = sanitize_exception_details(value)
        else:
            sanitized[key] = value

    return sanitized


def get_safe_error_message(error: Exception, context: str = "general") -> str:
    """
    Get a safe, user-friendly error message for an exception.

    This is a convenience function that combines sanitization with
    context-aware message selection.

    Args:
        error: The exception object
        context: Context where error occurred

    Returns:
        Safe error message for user-facing responses
    """
    error_type = type(error).__name__
    error_str = str(error).lower()

    # Map error types to safe messages
    if "database" in error_str or "sql" in error_str or "connection" in error_str:
        return SAFE_ERROR_MESSAGES.get("database", "A database error occurred.")

    if "network" in error_str or "connection" in error_str or "timeout" in error_str:
        return SAFE_ERROR_MESSAGES.get("network", "A network error occurred.")

    if "auth" in error_str or "token" in error_str or "unauthorized" in error_str:
        return SAFE_ERROR_MESSAGES.get("authentication", "Authentication failed.")

    if "permission" in error_str or "forbidden" in error_str:
        return SAFE_ERROR_MESSAGES.get("authorization", "Permission denied.")

    if "validation" in error_str or "invalid" in error_str:
        return SAFE_ERROR_MESSAGES.get("validation", "Invalid input provided.")

    if "not found" in error_str or "404" in error_str:
        return SAFE_ERROR_MESSAGES.get("not_found", "Resource not found.")

    if "rate limit" in error_str or "429" in error_str:
        return SAFE_ERROR_MESSAGES.get("rate_limit", "Too many requests.")

    # Use sanitized error message as fallback
    return sanitize_error_message(error, context)
