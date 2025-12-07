"""
External API Security Services
===============================

Future home for external API security services.

Planned Services:
-----------------
- OpenAISecurityService - OpenAI rate limiting, cost tracking, circuit breaker
- StravaSecurityService - Strava API security (if needed)
- GeneralAPISecurityService - Generic API security patterns

Current Status:
--------------
- ✅ OpenAI Rate Limiter implemented (Step 1)
- ⏳ Cost tracking (Step 2 - planned)
- ⏳ Circuit breaker (future)

Priority:
---------
- OpenAISecurityService (HIGH) - Rate limiting implemented

Migration Plan:
--------------
See ../MIGRATION_PLAN.md
"""

# Export OpenAI rate limiter functions
from src.services.security.external_apis.openai_rate_limiter import (
    can_make_request,
    record_request,
    get_user_stats,
    reset_rate_limits,
)

__all__ = [
    "can_make_request",
    "record_request",
    "get_user_stats",
    "reset_rate_limits",
]
