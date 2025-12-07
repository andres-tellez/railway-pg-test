# Security Services Package

**Status:** 🚧 Migration in Progress
**Created:** [Date]
**Purpose:** Centralized security service layer

## Overview

This package provides a centralized location for all security-related services. It's being gradually populated through a safe, incremental migration from `src/utils/` security utilities.

## Current State

### ✅ Created
- Directory structure
- Package initialization
- Migration documentation

### ✅ Implemented
- **OpenAI Rate Limiter** (`external_apis/openai_rate_limiter.py`)
  - Per-user rate limiting: 10 requests/minute
  - Integrated into conversation endpoint
  - Sliding window tracking
  - Standardized error responses

### ⏳ In Progress
- Cost tracking service (Step 2)
- Service migration planning

### 📋 Planned
- Rate limiting service consolidation
- Authentication service migration
- Authorization service migration
- External API security services
- Input validation services
- Audit monitoring services
- Encryption services
- Request security services
- Cost tracking services

## Complete Directory Structure

```
security/
├── rate_limiting/      # Rate limiting for all APIs
├── authentication/     # JWT, OAuth authentication
├── authorization/      # Role-based access control
├── external_apis/      # OpenAI, Strava API security
├── input_validation/   # Request validation, sanitization
├── audit_monitoring/  # Security event logging, monitoring
├── encryption/         # Token encryption, key management
├── request_security/   # Security headers, CORS, request validation
└── cost_tracking/      # API cost tracking, budget management
```

## Security Areas Coverage

| Area | Directory | Status | Priority |
|------|-----------|--------|----------|
| Rate Limiting | `rate_limiting/` | Planned | Medium |
| Authentication | `authentication/` | Planned | Medium |
| Authorization | `authorization/` | Planned | Medium |
| External APIs | `external_apis/` | ✅ **Implemented** (Step 1: Rate Limiting) | **HIGH** (OpenAI) |
| Input Validation | `input_validation/` | Planned | Medium |
| Audit Monitoring | `audit_monitoring/` | Planned | Low |
| Encryption | `encryption/` | Planned | Low |
| Request Security | `request_security/` | Planned | Low |
| Cost Tracking | `cost_tracking/` | Planned | **HIGH** (OpenAI) |

## Migration Strategy

See `MIGRATION_PLAN.md` for detailed step-by-step migration instructions.

## Principles

1. **Backward Compatibility** - Existing code continues to work
2. **Incremental Migration** - Move services one at a time
3. **Zero Breaking Changes** - No existing functionality breaks
4. **Test First** - Test each migration step independently

## Related Files

### Current Security Utilities (src/utils/)
- `auth0_jwt.py` - JWT validation
- `auth_rate_limiter.py` - Auth endpoint rate limiting
- `rate_limiter.py` - Strava API rate limiting
- `authorization.py` - Authorization decorators
- `security_utils.py` - Security utilities
- `token_encryption.py` - Token encryption
- `audit_logger.py` - Audit logging
- `oauth_state_manager.py` - OAuth state management

### Implemented Services (this package)
- ✅ `external_apis/openai_rate_limiter.py` - OpenAI API rate limiting (10 req/min per user)

### Future Services (this package)
- `rate_limiting/unified_rate_limiter.py` - Unified rate limiting
- `authentication/jwt_service.py` - JWT service
- `external_apis/` - Cost tracking, circuit breaker (future)
- `input_validation/request_validation_service.py` - Request validation
- `audit_monitoring/security_monitoring_service.py` - Security monitoring
- `cost_tracking/cost_tracking_service.py` - Cost tracking

## Notes

- This is a **migration target**, not a replacement
- Existing utilities remain functional
- New code should use services from this package
- Old code can be migrated gradually
