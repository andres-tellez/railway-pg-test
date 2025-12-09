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

# Export OpenAI cost tracker functions
from src.services.security.external_apis.openai_cost_tracker import (
    check_cost_limits,
    record_request_cost,
    get_user_cost_stats,
    get_global_cost_stats,
    reset_cost_tracking,
    MODEL_PRICING,  # Export pricing for use in other modules
    _calculate_cost,  # Export for smart_model_selector
)

# Export unified OpenAI service
from src.services.security.external_apis.openai_service import (
    OpenAIService,
    OpenAIResponse,
    RateLimitExceededError,
    CostLimitExceededError,
    get_openai_service,
)

__all__ = [
    # Rate limiter
    "can_make_request",
    "record_request",
    "get_user_stats",
    "reset_rate_limits",
    # Cost tracker
    "check_cost_limits",
    "record_request_cost",
    "get_user_cost_stats",
    "get_global_cost_stats",
    "reset_cost_tracking",
    "MODEL_PRICING",
    "_calculate_cost",
    # Unified service
    "OpenAIService",
    "OpenAIResponse",
    "RateLimitExceededError",
    "CostLimitExceededError",
    "get_openai_service",
]
