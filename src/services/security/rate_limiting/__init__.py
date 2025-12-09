"""
Rate Limiting Services
======================

Future home for unified rate limiting services.

Planned Services:
-----------------
- UnifiedRateLimitingService - Consolidates all rate limiters
- StravaRateLimitingService - Strava API rate limiting
- AuthRateLimitingService - Authentication endpoint rate limiting
- OpenAIRateLimitingService - OpenAI API rate limiting

Current Status:
--------------
- Directory created
- Ready for migration

Current Rate Limiters:
----------------------
- src/utils/rate_limiter.py (Strava API)
- src/utils/auth_rate_limiter.py (Auth endpoints)

Migration Plan:
--------------
See ../MIGRATION_PLAN.md
"""

__all__ = [
    # Future exports
]
