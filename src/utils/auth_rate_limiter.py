"""
Authentication Rate Limiter
===========================

Rate limiting utilities for authentication endpoints to prevent abuse.

This module provides rate limiting decorators specifically for auth endpoints:
- Login attempts
- OAuth callbacks
- Token refresh requests

Rate Limits:
-----------
- Login: 10 requests per 5 minutes per IP
- OAuth callbacks (Strava): 25 requests per 5 minutes per IP (separate bucket from login)
- Token refresh: 30 requests per 15 minutes per IP
- Webhook events: 100 requests per minute per IP (allows bursty webhook traffic)
- Webhook verification: 10 requests per 5 minutes per IP (verification is rare)
- General auth endpoints: 20 requests per 5 minutes per IP

Note:
-----
This is separate from the Strava API rate limiter (rate_limiter.py) which
handles external API calls. This handles incoming HTTP requests to our auth endpoints.
"""

import functools
import time
from collections import defaultdict, deque
from typing import Callable
from flask import request
import logging

logger = logging.getLogger(__name__)

# Rate limit configurations
RATE_LIMITS = {
    "login": {"requests": 10, "window_seconds": 300},  # 10 per 5 minutes
    "oauth_callback": {
        "requests": 25,
        "window_seconds": 300,
    },  # 25 per 5 minutes (retries + redirects)
    "token_refresh": {"requests": 30, "window_seconds": 900},  # 30 per 15 minutes
    "webhook": {
        "requests": 100,
        "window_seconds": 60,
    },  # 100 per minute (webhooks can be bursty)
    "webhook_verification": {
        "requests": 10,
        "window_seconds": 300,
    },  # 10 per 5 minutes (verification is rare)
    "general": {"requests": 20, "window_seconds": 300},  # 20 per 5 minutes
}

# In-memory storage (per IP + limit type so login vs oauth_callback don't share one bucket)
_rate_limit_storage: dict[str, deque] = defaultdict(lambda: deque())


def _get_client_identifier() -> str:
    """
    Get unique identifier for rate limiting.

    Uses IP address from request headers (X-Forwarded-For for proxies, or remote_addr).
    """
    # Check for forwarded IP (from proxies/load balancers)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take first IP if multiple (client is first)
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.remote_addr or "unknown"

    return client_ip


def _storage_key(identifier: str, limit_type: str) -> str:
    return f"{identifier}\x1f{limit_type}"


def _cleanup_old_requests(storage_key: str, window_seconds: int):
    """Remove request timestamps outside the rate limit window."""
    now = time.time()
    cutoff = now - window_seconds

    requests_list = _rate_limit_storage[storage_key]
    while requests_list and requests_list[0] < cutoff:
        requests_list.popleft()


def _check_rate_limit(identifier: str, limit_type: str) -> tuple[bool, float]:
    """
    Check if request is within rate limit.

    Args:
        identifier: Client identifier (IP address)
        limit_type: Type of rate limit ("login", "oauth_callback", "token_refresh", "general")

    Returns:
        Tuple of (is_allowed, retry_after_seconds)
    """
    limits = RATE_LIMITS.get(limit_type, RATE_LIMITS["general"])
    max_requests = limits["requests"]
    window_seconds = limits["window_seconds"]

    storage_key = _storage_key(identifier, limit_type)

    # Clean up old requests
    _cleanup_old_requests(storage_key, window_seconds)

    # Get current request count
    requests_list = _rate_limit_storage[storage_key]
    current_count = len(requests_list)

    if current_count >= max_requests:
        # Calculate retry after time
        oldest_request = requests_list[0]
        retry_after = (oldest_request + window_seconds) - time.time()
        retry_after = max(0, retry_after)
        return False, retry_after

    return True, 0.0


def _record_request(identifier: str, limit_type: str):
    """Record that a request was made."""
    now = time.time()
    _rate_limit_storage[_storage_key(identifier, limit_type)].append(now)


def rate_limit_auth(limit_type: str = "general"):
    """
    Decorator to rate limit authentication endpoints.

    Args:
        limit_type: Type of rate limit ("login", "oauth_callback", "token_refresh", "general")

    Usage:
        @rate_limit_auth("login")
        def login_endpoint():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            identifier = _get_client_identifier()
            is_allowed, retry_after = _check_rate_limit(identifier, limit_type)

            if not is_allowed:
                logger.warning(
                    f"Rate limit exceeded for {limit_type} from {identifier}. "
                    f"Retry after {retry_after:.1f} seconds"
                )
                # Use standardized error response format
                from src.utils.response_utils import error_response

                return error_response(
                    message=f"Too many requests. Please try again in {int(retry_after)} seconds.",
                    status_code=429,
                    error_code="RATE_LIMIT_EXCEEDED",
                    details={
                        "retry_after_seconds": int(retry_after),
                        "limit_type": limit_type,
                    },
                )

            # Record the request
            _record_request(identifier, limit_type)

            # Call the original function
            return func(*args, **kwargs)

        return wrapper

    return decorator


def reset_rate_limits(identifier: str = None):
    """
    Reset rate limits for testing or manual cleanup.

    Args:
        identifier: Specific client identifier to reset, or None to reset all
    """
    global _rate_limit_storage
    if identifier:
        prefix = f"{identifier}\x1f"
        for k in list(_rate_limit_storage.keys()):
            if k == identifier or k.startswith(prefix):
                _rate_limit_storage.pop(k, None)
    else:
        _rate_limit_storage.clear()
    logger.info(f"Rate limits reset for {identifier or 'all clients'}")


def get_rate_limit_stats(identifier: str = None) -> dict:
    """
    Get rate limit statistics for debugging.

    Args:
        identifier: Client identifier, or None for all clients

    Returns:
        Dictionary with rate limit statistics
    """
    stats: dict = {}
    if identifier:
        prefix = f"{identifier}\x1f"
        for k, requests_list in _rate_limit_storage.items():
            if k == identifier or k.startswith(prefix):
                stats[k] = {
                    "request_count": len(requests_list),
                    "oldest_request": requests_list[0] if requests_list else None,
                }
    else:
        for k, requests_list in _rate_limit_storage.items():
            stats[k] = {
                "request_count": len(requests_list),
                "oldest_request": requests_list[0] if requests_list else None,
            }

    return stats
