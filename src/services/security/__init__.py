"""
Security Services Package
=========================

This package provides centralized security services for the application.

**MIGRATION IN PROGRESS** - This is a new structure being gradually populated.
Existing security utilities in `src/utils/` continue to work unchanged.

Current Status:
--------------
- ✅ Directory structure created
- ⏳ Migration in progress
- 📝 See README.md for migration plan

Architecture:
-------------
- rate_limiting/     - Rate limiting services (Strava, Auth, OpenAI)
- authentication/    - Authentication services (JWT, OAuth)
- authorization/     - Authorization services (roles, ownership)
- external_apis/     - External API security (OpenAI, etc.)
- input_validation/  - Request validation, sanitization
- audit_monitoring/  - Security event logging, monitoring
- encryption/        - Token encryption, key management
- request_security/  - Security headers, CORS, request validation
- cost_tracking/     - API cost tracking, budget management

Migration Strategy:
-------------------
1. Create new services in this package
2. Wrap existing utilities (backward compatible)
3. Gradually migrate routes to use new services
4. Eventually deprecate old utilities (future)

See MIGRATION_PLAN.md for detailed migration steps.
"""

# Placeholder for future exports
# As services are migrated, they will be exported here

__all__ = [
    # Future exports will be added here
    # Example:
    # "RateLimitingService",
    # "OpenAISecurityService",
]
