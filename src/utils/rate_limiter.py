"""
Rate Limiter Utility
====================

Strava API Rate Limiting Utility
=================================

Tracks and enforces Strava API rate limits:
- 100 requests per 15 minutes (short-term limit)
- 1000 requests per day (long-term limit)

This utility ensures we never exceed these limits when syncing multiple athletes.

Note:
-----
This is a utility module (not a service) because it provides pure rate limiting
functionality without business logic. It's used by services to manage API calls.
"""

import time
from datetime import datetime, timedelta
from typing import Optional
from collections import deque
import logging

logger = logging.getLogger(__name__)

# Strava API rate limits
MAX_REQUESTS_PER_15_MIN = 100
MAX_REQUESTS_PER_DAY = 1000

# Safety margin (use 90% of limit to avoid hitting it)
SAFETY_MARGIN = 0.9
SAFE_REQUESTS_PER_15_MIN = int(MAX_REQUESTS_PER_15_MIN * SAFETY_MARGIN)  # 90
SAFE_REQUESTS_PER_DAY = int(MAX_REQUESTS_PER_DAY * SAFETY_MARGIN)  # 900


class RateLimiter:
    """
    Tracks API request timestamps and calculates when next request can be made.

    Uses sliding window approach:
    - Maintains a deque of request timestamps for last 15 minutes
    - Maintains a deque of request timestamps for last 24 hours
    - Calculates delay needed before next request
    """

    def __init__(self):
        # Deques store timestamps of API requests
        # Sliding window: only keep timestamps within the window
        self._requests_15min: deque = deque()  # Requests in last 15 minutes
        self._requests_24h: deque = deque()  # Requests in last 24 hours
        self._lock = None  # Thread lock (if needed for multi-threading)

    def can_make_request(self) -> bool:
        """
        Check if we can make a request now without exceeding limits.

        Returns:
            True if we're under both limits, False otherwise
        """
        now = time.time()
        self._cleanup_old_requests(now)

        # Check 15-minute limit
        if len(self._requests_15min) >= SAFE_REQUESTS_PER_15_MIN:
            return False

        # Check 24-hour limit
        if len(self._requests_24h) >= SAFE_REQUESTS_PER_DAY:
            return False

        return True

    def get_wait_time(self) -> float:
        """
        Calculate how long to wait before making next request.

        Returns:
            Seconds to wait (0 if no wait needed)
        """
        now = time.time()
        self._cleanup_old_requests(now)

        wait_times = []

        # Check 15-minute limit
        if len(self._requests_15min) >= SAFE_REQUESTS_PER_15_MIN:
            # Wait until oldest request in window expires
            oldest_15min = self._requests_15min[0]
            wait_15min = (oldest_15min + (15 * 60)) - now
            wait_times.append(max(0, wait_15min))

        # Check 24-hour limit
        if len(self._requests_24h) >= SAFE_REQUESTS_PER_DAY:
            # Wait until oldest request in window expires
            oldest_24h = self._requests_24h[0]
            wait_24h = (oldest_24h + (24 * 60 * 60)) - now
            wait_times.append(max(0, wait_24h))

        return max(wait_times) if wait_times else 0.0

    def record_request(self):
        """
        Record that an API request was made.

        Call this immediately after making a Strava API request.
        """
        now = time.time()
        self._requests_15min.append(now)
        self._requests_24h.append(now)
        self._cleanup_old_requests(now)

    def get_stats(self) -> dict:
        """
        Get current rate limit statistics.

        Returns:
            Dictionary with current usage and limits
        """
        now = time.time()
        self._cleanup_old_requests(now)

        return {
            "requests_15min": len(self._requests_15min),
            "limit_15min": SAFE_REQUESTS_PER_15_MIN,
            "remaining_15min": SAFE_REQUESTS_PER_15_MIN - len(self._requests_15min),
            "requests_24h": len(self._requests_24h),
            "limit_24h": SAFE_REQUESTS_PER_DAY,
            "remaining_24h": SAFE_REQUESTS_PER_DAY - len(self._requests_24h),
            "can_make_request": self.can_make_request(),
            "wait_time_seconds": self.get_wait_time(),
        }

    def _cleanup_old_requests(self, now: float):
        """
        Remove request timestamps outside the sliding windows.

        Args:
            now: Current timestamp
        """
        # Remove requests older than 15 minutes
        cutoff_15min = now - (15 * 60)
        while self._requests_15min and self._requests_15min[0] < cutoff_15min:
            self._requests_15min.popleft()

        # Remove requests older than 24 hours
        cutoff_24h = now - (24 * 60 * 60)
        while self._requests_24h and self._requests_24h[0] < cutoff_24h:
            self._requests_24h.popleft()

    def wait_if_needed(self):
        """
        Wait if necessary before making next request.

        This is a convenience method that:
        1. Checks if we can make a request
        2. If not, calculates wait time
        3. Waits and logs the wait
        """
        if not self.can_make_request():
            wait_time = self.get_wait_time()
            if wait_time > 0:
                logger.info(
                    f"⏳ Rate limit: waiting {wait_time:.1f}s before next request "
                    f"(15min: {len(self._requests_15min)}/{SAFE_REQUESTS_PER_15_MIN}, "
                    f"24h: {len(self._requests_24h)}/{SAFE_REQUESTS_PER_DAY})"
                )
                time.sleep(wait_time)
                # Cleanup after wait
                self._cleanup_old_requests(time.time())


# Global rate limiter instance (shared across all sync operations)
_global_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """
    Get the global rate limiter instance.

    Returns:
        RateLimiter instance (singleton)
    """
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimiter()
    return _global_rate_limiter


def reset_rate_limiter():
    """
    Reset the global rate limiter (useful for testing).
    """
    global _global_rate_limiter
    _global_rate_limiter = None
