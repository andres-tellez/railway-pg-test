"""
OpenAI Rate Limiter
===================

Rate limiting for OpenAI API calls to prevent abuse and protect costs.

This module provides per-user rate limiting for OpenAI API calls:
- 10 requests per minute per user
- Sliding window tracking
- Clear error messages with retry times

Note:
-----
This is separate from authentication rate limiting (auth_rate_limiter.py) which
handles HTTP requests. This handles OpenAI API call rate limiting per user.
"""

import time
from collections import defaultdict, deque
from typing import Tuple
import logging

logger = logging.getLogger(__name__)

# Rate limit configuration
REQUESTS_PER_MINUTE = 10
WINDOW_SECONDS = 60  # 1 minute

# In-memory storage (per user_id)
_rate_limit_storage: dict[str, deque] = defaultdict(lambda: deque())


def _cleanup_old_requests(user_id: str):
    """Remove request timestamps outside the 1-minute window."""
    now = time.time()
    cutoff = now - WINDOW_SECONDS

    requests_list = _rate_limit_storage[user_id]
    while requests_list and requests_list[0] < cutoff:
        requests_list.popleft()


def can_make_request(user_id: str) -> Tuple[bool, float]:
    """
    Check if user can make an OpenAI API request.

    Args:
        user_id: User identifier (string UUID)

    Returns:
        Tuple of (is_allowed, retry_after_seconds)
        - is_allowed: True if request is allowed, False if rate limit exceeded
        - retry_after_seconds: Seconds to wait before retrying (0 if allowed)
    """
    # Clean up old requests
    _cleanup_old_requests(user_id)

    # Get current request count
    requests_list = _rate_limit_storage[user_id]
    current_count = len(requests_list)

    if current_count >= REQUESTS_PER_MINUTE:
        # Calculate retry after time (when oldest request expires)
        oldest_request = requests_list[0]
        retry_after = (oldest_request + WINDOW_SECONDS) - time.time()
        retry_after = max(0, retry_after)

        logger.warning(
            f"OpenAI rate limit exceeded for user {user_id}. "
            f"Current: {current_count}/{REQUESTS_PER_MINUTE}, retry after {retry_after:.1f}s"
        )
        return False, retry_after

    return True, 0.0


def record_request(user_id: str):
    """
    Record that an OpenAI API request was made.

    Args:
        user_id: User identifier (string UUID)
    """
    now = time.time()
    _rate_limit_storage[user_id].append(now)
    _cleanup_old_requests(user_id)


def get_user_stats(user_id: str) -> dict:
    """
    Get rate limit statistics for a user.

    Args:
        user_id: User identifier (string UUID)

    Returns:
        Dictionary with rate limit statistics:
        - request_count: Current number of requests in window
        - limit: Maximum requests allowed
        - remaining: Remaining requests in window
        - oldest_request: Timestamp of oldest request (or None)
    """
    _cleanup_old_requests(user_id)
    requests_list = _rate_limit_storage[user_id]

    return {
        "request_count": len(requests_list),
        "limit": REQUESTS_PER_MINUTE,
        "remaining": max(0, REQUESTS_PER_MINUTE - len(requests_list)),
        "oldest_request": requests_list[0] if requests_list else None,
    }


def reset_rate_limits(user_id: str = None):
    """
    Reset rate limits for testing or manual cleanup.

    Args:
        user_id: Specific user to reset, or None to reset all users
    """
    global _rate_limit_storage
    if user_id:
        _rate_limit_storage.pop(user_id, None)
        logger.info(f"OpenAI rate limits reset for user {user_id}")
    else:
        _rate_limit_storage.clear()
        logger.info("OpenAI rate limits reset for all users")
